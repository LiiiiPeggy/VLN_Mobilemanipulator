"""Habitat kinematic camera / arm view diagnostics (no PPO, no LocoManip edits).

Compares arm configs for D455 optical FK, self-occlusion proxy, and TURN_UP/DOWN.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .constants import (
    ARM_APEXNAV_INIT,
    ARM_APEXNAV_INIT_SEARCH,
    ARM_DEFAULT,
    ARM_DEFAULT_LEGACY,
    DEFAULT_OUT_DIR,
    DEFAULT_SCENE,
    LOCOMANIP_COMMIT,
    LOCOMANIP_HEAD_READ,
    MODE_KINEMATIC,
    URDF_HABITAT,
)
from .demo_compose import compose_frame
from .initial_camera_pose import optical_metrics, within_tolerances
from .kinematic_demo import DEFAULT_BASE_Y, RangerCr10KinematicEnv

# Alias for report clarity (same as ARM_DEFAULT / ARM_APEXNAV_INIT after 4.10 sync)
LOCOMANIP_ARM_DEFAULT_410 = ARM_DEFAULT

# ################################
# LOOK pitch: at LocoManip 4.10 default, joint5 has ~0 optical-pitch gain;
# joint2/3/4 ≈ 50 deg/rad. Use joint3 (index 2) with ±0.6 rad ≈ ±30°.
# ################################
LOOK_JOINT_INDEX = 2
LOOK_DELTA_RAD = 0.60


def _font(size: int = 18):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def depth_stats(depth_m: np.ndarray) -> Dict[str, Any]:
    d = np.asarray(depth_m, dtype=np.float64)
    if d.ndim == 3:
        d = d[..., 0]
    valid = np.isfinite(d) & (d > 1e-4) & (d < 20.0)
    near = valid & (d < 0.35)  # likely self / very close geometry
    mid = valid & (d >= 0.35) & (d < 3.0)
    far = valid & (d >= 3.0)
    n = float(d.size)
    return {
        "valid_frac": float(valid.mean()) if n else 0.0,
        "near_lt_0p35_frac": float(near.mean()) if n else 0.0,
        "mid_0p35_3_frac": float(mid.mean()) if n else 0.0,
        "far_ge_3_frac": float(far.mean()) if n else 0.0,
        "median_m": float(np.median(d[valid])) if valid.any() else None,
        "p10_m": float(np.percentile(d[valid], 10)) if valid.any() else None,
        "p90_m": float(np.percentile(d[valid], 90)) if valid.any() else None,
    }


def arm_above_chassis(env) -> Dict[str, Any]:
    """Check key arm links stay above base deck (Habitat Y)."""
    base_y = float(env.base_xyz[1])
    out = {}
    for name in ("cr10_Link1", "cr10_Link3", "cr10_Link6", "d455_link", "d455_depth_optical_frame"):
        if name not in env.link_ids:
            continue
        p = env.ao.get_link_scene_node(env.link_ids[name]).absolute_transformation().translation
        out[name] = {
            "y": float(p.y),
            "above_base_deck": float(p.y) > base_y - 0.05,
            "rel_base_y": float(p.y) - base_y,
        }
    return out


def capture_bundle(env, label: str) -> Dict[str, Any]:
    env.sync_agent_sensors()
    ee = env.observe_ee_only()
    third = env.observe_third_only()
    m = optical_metrics(env, env.base_yaw)
    tol = within_tolerances(m)
    ds = depth_stats(ee["ee_depth"])
    return {
        "label": label,
        "arm_q": env.arm_q.tolist(),
        "metrics": m,
        "tolerances": tol,
        "depth": ds,
        "contacts": int(env.contact_count()),
        "upright": env.upright_diagnostics(),
        "arm_clearance": arm_above_chassis(env),
        "ee_rgb": ee["ee_rgb"][..., :3].copy(),
        "ee_depth": np.asarray(ee["ee_depth"]).copy(),
        "third_rgb": third[..., :3].copy(),
    }


def depth_vis(depth_m: np.ndarray, max_m: float = 5.0) -> np.ndarray:
    d = np.asarray(depth_m, dtype=np.float32)
    if d.ndim == 3:
        d = d[..., 0]
    x = np.clip(d / max_m, 0, 1)
    g = (x * 255).astype(np.uint8)
    return np.stack([g, g, g], axis=-1)


def annotate(img: np.ndarray, lines: List[str]) -> np.ndarray:
    im = Image.fromarray(img[..., :3].astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(im, "RGBA")
    font = _font(16)
    draw.rectangle([0, 0, im.width, 22 + 18 * len(lines)], fill=(0, 0, 0, 150))
    for i, t in enumerate(lines):
        draw.text((8, 6 + 18 * i), t, fill=(255, 255, 255), font=font)
    return np.asarray(im)


def apply_look(env, direction: str) -> None:
    q = env.arm_q.copy()
    # ################################
    # Empirical @ L410: joint3 +0.6 → optical pitch ≈ +30° (look up / fwd.y>0).
    # ################################
    delta = LOOK_DELTA_RAD if direction == "UP" else -LOOK_DELTA_RAD
    i = LOOK_JOINT_INDEX
    q[i] = float(np.clip(q[i] + delta, -2.86, 2.86))
    env.set_arm_joints(q)


def run(out_dir: Path, scene: str, gpu: int) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    env = RangerCr10KinematicEnv(scene=scene, urdf=URDF_HABITAT, gpu_device_id=gpu)
    # ################################
    # Place inside HM3D navigable area (prior adapted spawn neighborhood), not void.
    # ################################
    place_xz = (0.0, -6.5)
    floor_y = 0.01338
    try:
        pf = env.sim.pathfinder
        if pf is not None and pf.is_loaded:
            snapped = pf.snap_point(
                np.array([place_xz[0], floor_y + 0.1, place_xz[1]], dtype=np.float32)
            )
            if snapped is not None:
                place_xz = (float(snapped[0]), float(snapped[2]))
                floor_y = float(snapped[1])
    except Exception:
        pass
    env.set_base_pose(
        place_xz[0], place_xz[1], 0.0, y=floor_y + DEFAULT_BASE_Y, floor_y=floor_y, snap_wheels=True
    )

    configs: List[Tuple[str, Sequence[float]]] = [
        ("ARM_DEFAULT_legacy", ARM_DEFAULT_LEGACY),
        ("LOCOMANIP_ARM_DEFAULT_410", LOCOMANIP_ARM_DEFAULT_410),
        ("ARM_APEXNAV_INIT_search", ARM_APEXNAV_INIT_SEARCH),
        ("ARM_APEXNAV_INIT_current", ARM_APEXNAV_INIT),
    ]

    compare_rows = []
    best = None
    for name, q in configs:
        env.set_arm_joints(q)
        b = capture_bundle(env, name)
        # save panels
        sub = out_dir / name
        sub.mkdir(exist_ok=True)
        Image.fromarray(b["ee_rgb"]).save(sub / "ee_rgb.png")
        Image.fromarray(depth_vis(b["ee_depth"])).save(sub / "ee_depth.png")
        Image.fromarray(b["third_rgb"]).save(sub / "third.png")
        ann = annotate(
            b["ee_rgb"],
            [
                f"{name}",
                f"AGL={b['metrics']['height_agl_m']:.3f}m pitch={b['metrics']['pitch_deg']:.1f} "
                f"yaw_err={b['metrics']['yaw_err_deg']:.1f} roll={b['metrics']['roll_deg']:.1f}",
                f"tol_all={b['tolerances']['all_ok']} near_frac={b['depth']['near_lt_0p35_frac']:.2f} "
                f"contacts={b['contacts']}",
            ],
        )
        Image.fromarray(ann).save(sub / "ee_rgb_annot.png")
        row = {k: b[k] for k in ("label", "arm_q", "metrics", "tolerances", "depth", "contacts", "upright", "arm_clearance")}
        compare_rows.append(row)
        # score: prefer horizontal forward ~0.88, low near-occlusion, arm above deck
        score = 0.0
        if b["tolerances"]["all_ok"]:
            score += 5.0
        else:
            score += max(0.0, 2.0 - abs(b["metrics"]["height_agl_m"] - 0.88) * 10)
            score += max(0.0, 1.0 - abs(b["metrics"]["pitch_deg"]) / 20.0)
            score += max(0.0, 1.0 - abs(b["metrics"]["yaw_err_deg"]) / 30.0)
        score -= 3.0 * b["depth"]["near_lt_0p35_frac"]
        above = all(v.get("above_base_deck", False) for v in b["arm_clearance"].values())
        if above:
            score += 1.5
        else:
            score -= 2.0
        # penalize extreme wrist configs (search artifacts)
        if abs(float(q[4])) > 2.8:
            score -= 1.5
        row["score"] = score
        if best is None or score > best["score"]:
            best = {"name": name, "q": list(q), "score": score, "bundle_label": name}

    # ################################
    # Look comparison on best reasonable config (prefer LocoManip 4.10 if competitive)
    # ################################
    prefer = "LOCOMANIP_ARM_DEFAULT_410"
    prefer_row = next(r for r in compare_rows if r["label"] == prefer)
    search_row = next(r for r in compare_rows if r["label"] == "ARM_APEXNAV_INIT_search")
    use_name = prefer
    use_q = list(LOCOMANIP_ARM_DEFAULT_410)
    reason = "prefer_locomanip_410_default"
    if prefer_row["depth"]["near_lt_0p35_frac"] > 0.45 and search_row["tolerances"]["all_ok"]:
        if search_row["depth"]["near_lt_0p35_frac"] + 0.15 < prefer_row["depth"]["near_lt_0p35_frac"]:
            use_name = "ARM_APEXNAV_INIT_search"
            use_q = list(ARM_APEXNAV_INIT_SEARCH)
            reason = "search_less_occlusion_than_410"
    elif prefer_row["metrics"]["height_agl_m"] < 0.5 and best and best["name"] != prefer:
        use_name = best["name"]
        use_q = best["q"]
        reason = "410_too_low_fallback_best"

    look_dir = out_dir / "look_compare" / use_name
    look_dir.mkdir(parents=True, exist_ok=True)
    env.set_arm_joints(use_q)
    init_b = capture_bundle(env, f"{use_name}_INIT_LEVEL")
    apply_look(env, "DOWN")
    down_b = capture_bundle(env, f"{use_name}_TURN_DOWN")
    env.set_arm_joints(use_q)
    apply_look(env, "UP")
    up_b = capture_bundle(env, f"{use_name}_TURN_UP")

    panels = []
    for b, tag in ((init_b, "INIT"), (down_b, "TURN_DOWN"), (up_b, "TURN_UP")):
        Image.fromarray(b["ee_rgb"]).save(look_dir / f"{tag}_ee_rgb.png")
        Image.fromarray(depth_vis(b["ee_depth"])).save(look_dir / f"{tag}_ee_depth.png")
        Image.fromarray(b["third_rgb"]).save(look_dir / f"{tag}_third.png")
        blank_map = np.full((240, 320, 3), 40, dtype=np.uint8)
        demo = compose_frame(
            b["third_rgb"],
            b["ee_rgb"],
            blank_map,
            goal="camera_diag",
            step={"INIT": 0, "TURN_DOWN": 1, "TURN_UP": 2}[tag],
            action=tag,
            phase="kinematic_view_diag",
            control_mode=MODE_KINEMATIC,
                    status=(
                        f"pitch={b['metrics']['pitch_deg']:.1f} "
                        f"near={b['depth']['near_lt_0p35_frac']:.2f}"
                    ),
                    )
        Image.fromarray(demo).save(look_dir / f"{tag}_demo.png")
        panels.append(
            {
                "tag": tag,
                "metrics": b["metrics"],
                "tolerances": b["tolerances"],
                "depth": b["depth"],
                "contacts": b["contacts"],
                "arm_q": b["arm_q"],
                "arm_clearance": b["arm_clearance"],
            }
        )

    # strip image arrays from compare for JSON
    report = {
        "control_mode": MODE_KINEMATIC,
        "locomanip_weight_pin_commit": LOCOMANIP_COMMIT,
        "locomanip_head_read_for_arm": LOCOMANIP_HEAD_READ,
        "locomanip_head_note": (
            "ARM defaults read from LocoManip HEAD (stage 4.10). "
            "PPO ckpt remains stage45j @ LOCOMANIP_COMMIT; weights NOT swapped."
        ),
        "look_joint": {"index": LOOK_JOINT_INDEX, "name": "cr10_joint3", "delta_rad": LOOK_DELTA_RAD},
        "pinned_teleop_ckpt_unchanged": True,
        "configs": compare_rows,
        "selected_for_look": {"name": use_name, "q": use_q, "reason": reason},
        "look_compare": panels,
        "occlusion_interpretation": {
            "near_lt_0p35_frac": "fraction of depth pixels <0.35m; high ≈ arm/gripper self-occlusion or wall hug",
            "init_vs_turn": (
                "If INIT near_frac low but TURN_DOWN near_frac high → occlusion is LOOK-induced, "
                "not initial orientation error."
            ),
        },
        "apexnav_free_hypothesis": [
            "ApexNav free grids come from depth rays; filter_min/max_height default 0.5–0.88 m AGL.",
            "Heavy near-field self-occlusion → few valid mid-range rays → little FREE / NO_COVERABLE_FRONTIER.",
            "Tight bedroom spawn (adapted) + init lookaround into furniture also shrinks free.",
            "Verify after adopting a less self-occluding init pose and/or more open episode start.",
        ],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    # mosaic: INIT | DOWN | UP EE rgb
    mosa = Image.new("RGB", (640 * 3, 480))
    for i, tag in enumerate(("INIT", "TURN_DOWN", "TURN_UP")):
        im = Image.open(look_dir / f"{tag}_ee_rgb.png").resize((640, 480))
        mosa.paste(im, (i * 640, 0))
    mosa.save(out_dir / "look_ee_mosaic.png")

    try:
        env.close()
    except Exception:
        pass
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out_dir",
        default=str(Path(DEFAULT_OUT_DIR) / f"camera_view_diag_{time.strftime('%Y%m%d_%H%M%S')}"),
    )
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args(argv)
    rep = run(Path(args.out_dir), args.scene, args.gpu)
    print(json.dumps({
        "out_dir": args.out_dir,
        "selected": rep["selected_for_look"],
        "configs": [
            {
                "label": c["label"],
                "agl": c["metrics"]["height_agl_m"],
                "pitch": c["metrics"]["pitch_deg"],
                "yaw_err": c["metrics"]["yaw_err_deg"],
                "roll": c["metrics"]["roll_deg"],
                "tol": c["tolerances"]["all_ok"],
                "near": c["depth"]["near_lt_0p35_frac"],
                "score": c["score"],
            }
            for c in rep["configs"]
        ],
        "look": [
            {
                "tag": x["tag"],
                "agl": x["metrics"]["height_agl_m"],
                "pitch": x["metrics"]["pitch_deg"],
                "near": x["depth"]["near_lt_0p35_frac"],
            }
            for x in rep["look_compare"]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
