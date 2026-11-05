"""Offline HM3D clearance screening for Ranger+CR10 (GT navmesh; NOT for ApexNav).

################################
Recomputes navmesh at Habitat (0.18 m) vs Ranger half-width / circum radii and ranks
scenes by retained navigable area + usable ObjectNav starts. GT is never fed online.
################################
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import magnum as mn
import numpy as np
from PIL import Image, ImageDraw

from .ranger_footprint import (
    CHASSIS_CIRCUM_R,
    CHASSIS_HALF_L,
    CHASSIS_HALF_W,
    CHASSIS_WIDTH,
    footprint_report,
    oriented_rect_corners,
)


def _load_sim(scene_glb: str, gpu: int = 0):
    import habitat_sim

    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = scene_glb
    backend.enable_physics = False
    backend.gpu_device_id = gpu
    agent = habitat_sim.agent.AgentConfiguration()
    cfg = habitat_sim.Configuration(backend, [agent])
    return habitat_sim.Simulator(cfg)


def _nav_area(pf) -> float:
    try:
        a = pf.navigable_area
        return float(a() if callable(a) else a)
    except Exception:
        return float("nan")


def _recompute_navmesh(sim, agent_radius: float, agent_height: float = 1.5):
    import habitat_sim

    settings = habitat_sim.NavMeshSettings()
    settings.set_defaults()
    settings.agent_radius = float(agent_radius)
    settings.agent_height = float(agent_height)
    settings.include_static_objects = True
    ok = sim.recompute_navmesh(sim.pathfinder, settings)
    return bool(ok), _nav_area(sim.pathfinder)


def _sample_points(pf, n: int, seed: int = 0) -> np.ndarray:
    pts = []
    for _ in range(n * 5):
        if len(pts) >= n:
            break
        try:
            p = pf.get_random_navigable_point()
        except Exception:
            continue
        if p is None:
            continue
        pts.append([float(p[0]), float(p[1]), float(p[2])])
    return np.asarray(pts, dtype=np.float64) if pts else np.zeros((0, 3))


def _oriented_fit_rate(pf, pts: np.ndarray, n_yaw: int = 8) -> Dict[str, float]:
    if len(pts) == 0:
        return {"oriented_fit_frac": 0.0, "n_tests": 0}
    yaws = np.linspace(0, 2 * math.pi, n_yaw, endpoint=False)
    ok = tot = 0
    use = pts if len(pts) <= 60 else pts[np.linspace(0, len(pts) - 1, 60).astype(int)]
    for p in use:
        y0 = float(p[1])
        for yaw in yaws:
            tot += 1
            if not pf.is_navigable(mn.Vector3(float(p[0]), y0, float(p[2]))):
                continue
            corners = oriented_rect_corners(
                float(p[0]), float(p[2]), float(yaw), half_l=0.15, half_w=0.05
            )
            good = True
            for cx, cz in corners:
                if not pf.is_navigable(mn.Vector3(float(cx), y0, float(cz))):
                    good = False
                    break
            if good:
                ok += 1
    return {"oriented_fit_frac": float(ok / max(tot, 1)), "n_tests": int(tot)}


def _topdown_panel(pf, out_path: Path, title: str) -> None:
    try:
        top = pf.get_topdown_view(0.05, 0.0)
        arr = np.asarray(top)
        if arr.ndim == 2:
            img = (arr * 255).astype(np.uint8)
            rgb = np.stack([img, img, img], axis=-1)
        else:
            rgb = (arr[..., :3] * 255).astype(np.uint8)
        im = Image.fromarray(rgb)
        dr = ImageDraw.Draw(im)
        bar_px = max(1, int(CHASSIS_WIDTH / 0.05))
        dr.rectangle([10, 10, 10 + bar_px, 18], fill=(255, 64, 64))
        dr.text((10, 22), f"{title} chassis_w={CHASSIS_WIDTH:.2f}m", fill=(255, 255, 0))
        im.save(out_path)
    except Exception as e:
        out_path.with_suffix(".txt").write_text(f"topdown failed: {e}")


def _episode_starts(objnav_gz: Path, max_eps: int = 40) -> List[dict]:
    with gzip.open(objnav_gz, "rt") as f:
        data = json.load(f)
    out = []
    for ep in (data.get("episodes") or [])[:max_eps]:
        out.append(
            {
                "episode_id": ep.get("episode_id"),
                "object_category": ep.get("object_category"),
                "start_position": ep.get("start_position") or [0, 0, 0],
                "start_rotation": ep.get("start_rotation"),
            }
        )
    return out


def analyze_scene(
    scene_dir: Path,
    objnav_gz: Path,
    out_dir: Path,
    n_samples: int = 200,
    gpu: int = 0,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    glbs = list(scene_dir.glob("*.basis.glb"))
    if not glbs:
        return {"error": "no_glb", "scene_dir": str(scene_dir)}
    scene_glb = str(glbs[0])
    sid = scene_dir.name.split("-", 1)[-1]
    sim = _load_sim(scene_glb, gpu=gpu)
    try:
        if not sim.pathfinder.is_loaded:
            return {"scene_id": sid, "error": "navmesh_not_loaded"}

        radii = {
            "r018_habitat": 0.18,
            "r435_half_width": float(CHASSIS_HALF_W),
            "r485_half_width_margin": float(CHASSIS_HALF_W + 0.05),
            "r783_circum": float(CHASSIS_CIRCUM_R),
        }
        areas: Dict[str, Any] = {}
        for name, rad in radii.items():
            ok, area = _recompute_navmesh(sim, rad)
            areas[name] = {"agent_radius_m": rad, "recompute_ok": ok, "nav_area_m2": area}

        a018 = areas["r018_habitat"]["nav_area_m2"]
        a485 = areas["r485_half_width_margin"]["nav_area_m2"]
        a435 = areas["r435_half_width"]["nav_area_m2"]
        area_retain_485 = float(a485 / a018) if a018 == a018 and a018 and a018 > 1e-6 else 0.0
        area_retain_435 = float(a435 / a018) if a018 == a018 and a018 and a018 > 1e-6 else 0.0

        _recompute_navmesh(sim, CHASSIS_HALF_W + 0.05)
        pf = sim.pathfinder
        pts = _sample_points(pf, n_samples, seed=abs(hash(sid)) % (2**31))
        orient = _oriented_fit_rate(pf, pts)

        starts = []
        if objnav_gz.is_file():
            for ep in _episode_starts(objnav_gz):
                sp = ep["start_position"]
                p = mn.Vector3(float(sp[0]), float(sp[1]), float(sp[2]))
                try:
                    nav = bool(pf.is_navigable(p))
                    if not nav:
                        spn = pf.snap_point(p)
                        dist = float(
                            np.linalg.norm(
                                np.asarray([sp[0], sp[1], sp[2]], dtype=np.float64)
                                - np.asarray([spn[0], spn[1], spn[2]], dtype=np.float64)
                            )
                        )
                        nav_near = dist < 0.75 and bool(pf.is_navigable(spn))
                    else:
                        dist = 0.0
                        nav_near = True
                except Exception:
                    nav = nav_near = False
                    dist = float("nan")
                starts.append(
                    {
                        "episode_id": ep["episode_id"],
                        "category": ep["object_category"],
                        "navigable_at_r485": nav,
                        "snap_dist_m": dist,
                        "usable_start_r485": bool(nav_near),
                    }
                )

        panel = out_dir / f"{sid}_topdown_r485.png"
        _topdown_panel(pf, panel, f"{sid} r=0.485")
        _recompute_navmesh(sim, 0.18)
        _topdown_panel(sim.pathfinder, out_dir / f"{sid}_topdown_r018.png", f"{sid} r=0.18")

        start_pass = [s for s in starts if s.get("usable_start_r485")]
        score = (
            0.40 * min(area_retain_485, 1.0)
            + 0.25 * min((a485 / 50.0) if a485 == a485 else 0.0, 1.0)
            + 0.20 * orient.get("oriented_fit_frac", 0.0)
            + 0.15 * (len(start_pass) / max(len(starts), 1))
        )
        rep = {
            "scene_id": sid,
            "scene_glb": scene_glb,
            "footprint": footprint_report(),
            "navmesh_areas": areas,
            "area_retain_r485_vs_r018": area_retain_485,
            "area_retain_r435_vs_r018": area_retain_435,
            "oriented": orient,
            "episode_starts": starts,
            "n_starts_usable_r485": len(start_pass),
            "score": float(score),
            "panel_r485": str(panel),
            "method": "recompute_navmesh_multi_radius_gt_offline",
        }
        (out_dir / f"{sid}_clearance.json").write_text(json.dumps(rep, indent=2))
        return rep
    finally:
        sim.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--hm3d_val",
        default="/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val",
    )
    p.add_argument(
        "--objectnav_content",
        default="/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2/val/content",
    )
    p.add_argument(
        "--out_root",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/scene_clearance",
    )
    p.add_argument("--n_samples", type=int, default=150)
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument("--max_scenes", type=int, default=0)
    p.add_argument("--scene_ids", default="")
    args = p.parse_args(argv)

    hm3d = Path(args.hm3d_val)
    obj = Path(args.objectnav_content)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    want = {s.strip() for s in args.scene_ids.split(",") if s.strip()}
    scenes = []
    for d in sorted(hm3d.glob("*/")):
        sid = d.name.split("-", 1)[-1]
        gz = obj / f"{sid}.json.gz"
        if not gz.is_file():
            continue
        if want and sid not in want:
            continue
        scenes.append((d, gz))
    if args.max_scenes > 0:
        scenes = scenes[: args.max_scenes]

    inventory = {
        "hm3d_val_dirs": len(list(hm3d.glob("*/"))),
        "objectnav_v2_content_gz": len(list(obj.glob("*.json.gz"))),
        "analyzed": len(scenes),
        "mp3d_dirs": len(
            list(Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets/mp3d").glob("*"))
        ),
        "footprint": footprint_report(),
        "note": "GT multi-radius navmesh offline only; never fed to ApexNav.",
    }
    rows = []
    for d, gz in scenes:
        print(f"[clearance] {d.name}", flush=True)
        try:
            rep = analyze_scene(
                d, gz, out_root / "scenes", n_samples=args.n_samples, gpu=args.gpu
            )
        except Exception as e:
            rep = {"scene_id": d.name.split("-", 1)[-1], "error": str(e)}
        rows.append(rep)

    rows_ok = [r for r in rows if "score" in r]
    rows_ok.sort(key=lambda r: r["score"], reverse=True)
    ranking = []
    for r in rows_ok:
        a485 = r["navmesh_areas"]["r485_half_width_margin"]["nav_area_m2"]
        a018 = r["navmesh_areas"]["r018_habitat"]["nav_area_m2"]
        ranking.append(
            {
                "scene_id": r["scene_id"],
                "score": r["score"],
                "area_r018_m2": a018,
                "area_r485_m2": a485,
                "retain_r485": r["area_retain_r485_vs_r018"],
                "retain_r435": r["area_retain_r435_vs_r018"],
                "oriented_fit_frac": r["oriented"].get("oriented_fit_frac"),
                "n_starts_usable_r485": r.get("n_starts_usable_r485"),
            }
        )
    summary = {
        "inventory": inventory,
        "ranking": ranking,
        "top5_candidates": rows_ok[:5],
        "known_baselines": {
            "Dd4bFSTQ8gi": "prior open demo (yaw-fix)",
            "TEEsavR23oF": "prior narrow NO_PASSABLE",
        },
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))
    lines = [
        "# Scene clearance vs Ranger+CR10 (recomputed navmesh)",
        "",
        f"Chassis L×W = {2*CHASSIS_HALF_L:.3f}×{2*CHASSIS_HALF_W:.3f} m; "
        f"circum R={CHASSIS_CIRCUM_R:.3f} m. GT offline only.",
        "",
        "| rank | scene | score | area@0.18 | area@0.485 | retain485 | oriented | starts@0.485 |",
        "|------|-------|-------|-----------|------------|-----------|----------|--------------|",
    ]
    for i, r in enumerate(ranking, 1):
        lines.append(
            f"| {i} | {r['scene_id']} | {r['score']:.3f} | "
            f"{r['area_r018_m2']:.1f} | {r['area_r485_m2']:.1f} | "
            f"{r['retain_r485']:.2f} | {r['oriented_fit_frac']:.2f} | "
            f"{r['n_starts_usable_r485']} |"
        )
    (out_root / "ranking.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"top5": ranking[:5], "errors": [r for r in rows if "error" in r]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
