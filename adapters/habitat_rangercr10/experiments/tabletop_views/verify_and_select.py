#!/usr/bin/env python3
# ################################
# VLN adapt: independent render check + lock ≤3 instances / category
# ################################
"""Selection uses scene facts only (geometry, navigability, visibility).

No detector scores. Prefer cross-scene; keep clear + partial-occlusion cases.
Cup seed scenes: CrMo8WxCyVb, VBzV5z6i1WS.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import habitat_sim
import magnum as mn
import numpy as np
from PIL import Image, ImageDraw

_THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS))
sys.path.insert(0, str(_THIS.parents[1]))

from category_rules import CANONICAL, pair_id  # noqa: E402
from paths import (  # noqa: E402
    HM3D_DATASET_CFG,
    REPORT_CAPTURE,
    VERIFY_DATA,
    scene_basis_glb,
)


def _look_state(eye: np.ndarray, target: np.ndarray) -> habitat_sim.AgentState:
    T = mn.Matrix4.look_at(
        mn.Vector3(float(eye[0]), float(eye[1]), float(eye[2])),
        mn.Vector3(float(target[0]), float(target[1]), float(target[2])),
        mn.Vector3(0.0, 1.0, 0.0),
    )
    q = mn.Quaternion.from_matrix(mn.Matrix3x3(T.rotation()))
    st = habitat_sim.AgentState()
    st.position = eye.astype(np.float32)
    st.rotation = np.array(
        [q.vector.x, q.vector.y, q.vector.z, q.scalar], dtype=np.float32
    )
    return st


def _open_sim(scene_id: str, gpu: int):
    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = str(scene_basis_glb(scene_id))
    backend.scene_dataset_config_file = str(HM3D_DATASET_CFG)
    backend.enable_physics = False
    backend.gpu_device_id = int(gpu)
    specs = []
    for uuid, st in (
        ("rgb", habitat_sim.SensorType.COLOR),
        ("sem", habitat_sim.SensorType.SEMANTIC),
    ):
        s = habitat_sim.CameraSensorSpec()
        s.uuid = uuid
        s.sensor_type = st
        s.resolution = [480, 640]
        s.hfov = 79.0
        specs.append(s)
    agent = habitat_sim.agent.AgentConfiguration()
    agent.sensor_specifications = specs
    # ################################
    # Keep sensors at agent pose (default agent height would lift the camera).
    # ################################
    agent.height = 0.01
    agent.radius = 0.01
    return habitat_sim.Simulator(habitat_sim.Configuration(backend, [agent]))


def verify_instance(
    sim,
    row: dict,
    out_dir: Path,
) -> Dict[str, Any]:
    """Render overhead-ish + side views; measure mask pixels / navigability."""
    sid = int(row["semantic_id"])
    ctr = np.asarray(row["center_hab"], dtype=np.float64)
    pf = sim.pathfinder
    nav = {"has_navmesh": bool(pf is not None and pf.is_loaded)}
    nearby = []
    if nav["has_navmesh"]:
        for r in (0.8, 1.2, 1.6, 2.0, 2.5):
            for k in range(12):
                ang = 2 * math.pi * k / 12
                x = ctr[0] + r * math.cos(ang)
                z = ctr[2] + r * math.sin(ang)
                p = pf.snap_point(np.array([x, ctr[1], z], dtype=np.float32))
                if p is None:
                    continue
                if math.hypot(float(p[0]) - x, float(p[2]) - z) > 0.4:
                    continue
                if abs(float(p[1]) - ctr[1]) > 1.5 and abs(float(p[1]) + 0.9 - ctr[1]) > 1.8:
                    continue
                nearby.append(
                    {
                        "x": float(p[0]),
                        "y": float(p[1]),
                        "z": float(p[2]),
                        "dist_xz": math.hypot(ctr[0] - float(p[0]), ctr[2] - float(p[2])),
                    }
                )
    nav["n_nearby_snaps"] = len(nearby)
    nav["deployable_hint"] = len(nearby) >= 2

    views = []
    out_dir.mkdir(parents=True, exist_ok=True)

    def _render_at(eye: np.ndarray) -> Tuple[np.ndarray, np.ndarray, int]:
        st = _look_state(eye.astype(np.float32), ctr.astype(np.float32))
        sim.agents[0].set_state(st, infer_sensor_states=True)
        obs = sim.get_sensor_observations()
        rgb = obs["rgb"][..., :3]
        sem = obs["sem"]
        pix = int((sem == sid).sum())
        return rgb, (sem == sid).astype(np.uint8), pix

    # ################################
    # Try several eyes (nav floor+1.1 at ring angles + raised). Keep max-mask.
    # ################################
    eye_candidates: List[Tuple[str, np.ndarray]] = []
    for p in sorted(nearby, key=lambda q: abs(q["dist_xz"] - 1.5))[:8]:
        eye_candidates.append(
            (
                "side",
                np.array([p["x"], float(p["y"]) + 1.15, p["z"]], dtype=np.float64),
            )
        )
    # Prefer eyes at navigable floor + ~1.1 m (matches successful mug probes).
    floor_ref = float(nearby[0]["y"]) if nearby else float(ctr[1] - 0.9)
    for r in (1.3, 1.8, 2.4):
        for k in range(8):
            ang = 2 * math.pi * k / 8
            eye_candidates.append(
                (
                    "ring",
                    np.array(
                        [
                            ctr[0] + r * math.cos(ang),
                            floor_ref + 1.15,
                            ctr[2] + r * math.sin(ang),
                        ],
                        dtype=np.float64,
                    ),
                )
            )
    eye_candidates.append(
        (
            "high",
            np.array(
                [ctr[0] + 0.8, floor_ref + 1.8, ctr[2] + 0.8], dtype=np.float64
            ),
        )
    )

    best_by_name: Dict[str, dict] = {}
    for tag, eye in eye_candidates:
        name = "side" if tag in ("side", "ring") else "high"
        try:
            rgb, mask, pix = _render_at(eye)
        except Exception:
            continue
        prev = best_by_name.get(name)
        if prev is None or pix > prev["pixels"]:
            best_by_name[name] = {
                "name": name,
                "pixels": pix,
                "rgb_arr": rgb,
                "mask_arr": mask,
                "eye": eye.tolist(),
            }

    # Ensure both slots exist
    for name in ("side", "high"):
        if name not in best_by_name:
            rgb, mask, pix = _render_at(ctr + np.array([1.5, 0.6, 0.0]))
            best_by_name[name] = {
                "name": name,
                "pixels": pix,
                "rgb_arr": rgb,
                "mask_arr": mask,
                "eye": (ctr + np.array([1.5, 0.6, 0.0])).tolist(),
            }

    for name in ("side", "high"):
        slot = best_by_name[name]
        rgb = slot["rgb_arr"]
        mask = slot["mask_arr"]
        pix = int(slot["pixels"])
        ys, xs = np.where(mask > 0)
        occ = "invisible"
        if pix >= 80:
            fill = pix / float((ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1))
            occ = "partial" if fill < 0.35 else "clear"
        elif pix >= 20:
            occ = "partial"
        rgb_path = out_dir / f"{name}_rgb.png"
        mask_path = out_dir / f"{name}_mask.png"
        Image.fromarray(rgb).save(rgb_path)
        Image.fromarray(mask * 255).save(mask_path)
        ann = rgb.copy()
        if pix > 0:
            ann[mask > 0] = (
                0.55 * ann[mask > 0] + 0.45 * np.array([0, 255, 0])
            ).astype(np.uint8)
        Image.fromarray(ann).save(out_dir / f"{name}_annot.png")
        views.append(
            {
                "name": name,
                "pixels": pix,
                "occlusion_proxy": occ,
                "eye": slot["eye"],
                "rgb": str(rgb_path),
                "mask": str(mask_path),
            }
        )

    best_pix = max(v["pixels"] for v in views) if views else 0
    occlusions = {v["occlusion_proxy"] for v in views}
    tabletop_hint = bool(
        # object not floor-level giant; AABB height typically < 0.35 m for tableware
        float(row["sizes_hab"][1]) < 0.45
        and float(np.linalg.norm(row["sizes_hab"])) < 1.2
    )
    recognizable = best_pix >= 80 and ("clear" in occlusions or "partial" in occlusions)
    accept = bool(recognizable and nav["deployable_hint"] and tabletop_hint)
    reason_parts = []
    if not recognizable:
        reason_parts.append(f"low_visibility best_pix={best_pix}")
    if not nav["deployable_hint"]:
        reason_parts.append("few_nav_snaps_near_object")
    if not tabletop_hint:
        reason_parts.append("aabb_size_not_tableware_like")
    return {
        **row,
        "verify": {
            "accept_candidate": accept,
            "reason": "ok" if accept else ";".join(reason_parts) or "rejected",
            "best_pixels": best_pix,
            "occlusion_labels": sorted(occlusions),
            "nav": nav,
            "tabletop_hint": tabletop_hint,
            "views": views,
            "verify_dir": str(out_dir),
        },
    }


def select_locked(
    verified: List[dict],
    *,
    max_per_cat: int = 3,
) -> Tuple[List[dict], List[dict]]:
    """Greedy cross-scene selection; prefer clear then partial."""
    selected: List[dict] = []
    excluded: List[dict] = []
    by_cat: Dict[str, List[dict]] = defaultdict(list)
    for r in verified:
        by_cat[r["canonical"]].append(r)

    cup_prefer = ["CrMo8WxCyVb", "VBzV5z6i1WS"]

    for cat in CANONICAL:
        pool = [r for r in by_cat[cat] if r["verify"]["accept_candidate"]]
        # sort: prefer preferred scenes for cup, then clear occlusion, then pixels
        def key(r):
            pref = 0
            if cat == "cup" and r["scene_id"] in cup_prefer:
                pref = -cup_prefer.index(r["scene_id"])
            clear = 0 if "clear" in r["verify"]["occlusion_labels"] else 1
            partial = 0 if "partial" in r["verify"]["occlusion_labels"] else 1
            return (pref, clear, partial, -r["verify"]["best_pixels"])

        pool = sorted(pool, key=key)
        used_scenes = set()
        chosen = []
        # pass 1: unique scenes
        for r in pool:
            if r["scene_id"] in used_scenes:
                continue
            chosen.append(r)
            used_scenes.add(r["scene_id"])
            if len(chosen) >= max_per_cat:
                break
        # pass 2: fill
        if len(chosen) < max_per_cat:
            for r in pool:
                if r in chosen:
                    continue
                chosen.append(r)
                if len(chosen) >= max_per_cat:
                    break
        # mark
        chosen_keys = {r["instance_key"] for r in chosen}
        for r in by_cat[cat]:
            entry = {
                **r,
                "pair_id": pair_id(r["scene_id"], r["canonical"], r["semantic_id"]),
                "selection": {
                    "selected": r["instance_key"] in chosen_keys,
                    "category_slot": cat,
                },
            }
            if entry["selection"]["selected"]:
                # diversify occlusion tags when possible
                entry["selection"]["occlusion_case"] = (
                    "clear"
                    if "clear" in r["verify"]["occlusion_labels"]
                    else (
                        "partial"
                        if "partial" in r["verify"]["occlusion_labels"]
                        else "other"
                    )
                )
                selected.append(entry)
            else:
                entry["selection"]["exclude_reason"] = (
                    r["verify"]["reason"]
                    if not r["verify"]["accept_candidate"]
                    else "quota_or_scene_diversity"
                )
                excluded.append(entry)
    return selected, excluded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=REPORT_CAPTURE / "instance_catalog.json")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--max_per_cat", type=int, default=3)
    ap.add_argument(
        "--prefilter_scenes",
        nargs="*",
        default=None,
        help="optional scene whitelist to speed verify",
    )
    ap.add_argument("--limit_per_cat_verify", type=int, default=12)
    args = ap.parse_args()

    cat = json.loads(args.catalog.read_text())
    instances = cat["instances"]
    if args.prefilter_scenes:
        allow = set(args.prefilter_scenes)
        instances = [r for r in instances if r["scene_id"] in allow]

    # Cap verify work: for each category take diverse scenes first
    by_cat = defaultdict(list)
    for r in instances:
        by_cat[r["canonical"]].append(r)
    to_verify = []
    for c in CANONICAL:
        rows = by_cat[c]
        # cup: put preferred scenes first
        if c == "cup":
            pref = ["CrMo8WxCyVb", "VBzV5z6i1WS"]
            rows = sorted(
                rows,
                key=lambda r: (
                    pref.index(r["scene_id"]) if r["scene_id"] in pref else 99,
                    r["scene_id"],
                    r["semantic_id"],
                ),
            )
        else:
            rows = sorted(rows, key=lambda r: (r["scene_id"], r["semantic_id"]))
        # diversify scenes in verify budget
        picked = []
        seen = set()
        for r in rows:
            if r["scene_id"] not in seen:
                picked.append(r)
                seen.add(r["scene_id"])
            if len(picked) >= args.limit_per_cat_verify:
                break
        for r in rows:
            if len(picked) >= args.limit_per_cat_verify:
                break
            if r not in picked:
                picked.append(r)
        to_verify.extend(picked)

    verified: List[dict] = []
    by_scene: Dict[str, List[dict]] = defaultdict(list)
    for r in to_verify:
        by_scene[r["scene_id"]].append(r)

    for si, (scene_id, rows) in enumerate(sorted(by_scene.items())):
        print(f"verify scene [{si+1}/{len(by_scene)}] {scene_id} n={len(rows)}", flush=True)
        sim = _open_sim(scene_id, args.gpu)
        try:
            for r in rows:
                out_dir = VERIFY_DATA / scene_id / f"{r['canonical']}_{r['semantic_id']}"
                vr = verify_instance(sim, r, out_dir)
                verified.append(vr)
                print(
                    f"  {r['canonical']} {r['semantic_id']} "
                    f"accept={vr['verify']['accept_candidate']} "
                    f"pix={vr['verify']['best_pixels']} "
                    f"{vr['verify']['reason']}",
                    flush=True,
                )
        finally:
            try:
                sim.close()
            except Exception:
                pass

    selected, excluded = select_locked(verified, max_per_cat=args.max_per_cat)
    REPORT_CAPTURE.mkdir(parents=True, exist_ok=True)
    locked = {
        "protocol": "tabletop_views_pilot_v1",
        "selection_rule": (
            "scene-fact only; ≤3/cat; cross-scene; cup seeds CrMo8/VBzV; "
            "keep clear+partial; no detector scores"
        ),
        "n_verified": len(verified),
        "n_selected": len(selected),
        "n_excluded": len(excluded),
        "selected": selected,
        "excluded": excluded,
    }
    out = REPORT_CAPTURE / "locked_instances.json"
    out.write_text(json.dumps(locked, indent=2) + "\n")
    # human table
    lines = [
        "# Locked tabletop instances",
        "",
        f"Verified {len(verified)}; selected {len(selected)}.",
        "",
        "| pair_id | cat | scene | sem_id | label | occlusion | best_pix |",
        "|---------|-----|-------|--------|-------|-----------|----------|",
    ]
    for r in selected:
        lines.append(
            f"| `{r['pair_id']}` | {r['canonical']} | {r['scene_id']} | "
            f"{r['semantic_id']} | {r['label']} | "
            f"{r['selection']['occlusion_case']} | {r['verify']['best_pixels']} |"
        )
    lines += ["", "## Excluded (sample)", ""]
    for r in excluded[:40]:
        lines.append(
            f"- `{r['instance_key']}` ({r['label']}): {r['selection']['exclude_reason']}"
        )
    (REPORT_CAPTURE / "locked_instances.md").write_text("\n".join(lines) + "\n")
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
