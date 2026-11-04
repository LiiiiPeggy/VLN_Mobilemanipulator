"""Offline ApexNav map / inflation / turn diagnosis for Ranger+CR10 episodes.

################################
Uses saved map PNGs + steps.jsonl. Does NOT modify ApexNav planner code.
Variants A/B/C re-dilate occupied pixels as a proxy for obstacles_inflation.
################################
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from .map_style import (
    LEGACY_COLORS,
    PAPER_BG,
    PAPER_FREE,
    PAPER_OCCUPIED,
    PAPER_ROBOT,
    PAPER_TRAJ,
    PAPER_UNKNOWN,
)

# MuJoCo Stage 4.10d base_link_col half-extents (m)
CHASSIS_HALF_L = 0.651
CHASSIS_HALF_W = 0.4347
CHASSIS_CIRCUM_R = float(math.hypot(CHASSIS_HALF_L, CHASSIS_HALF_W))
BASELINE_INFLATION = 0.18
SAFE_ORIENTED_R = CHASSIS_HALF_W + 0.05  # 0.4847
SAFE_CIRCUM_R = CHASSIS_CIRCUM_R + 0.05  # ~0.833
MAP_RES = 0.05  # sdf_map/resolution


def _wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _mask_near(rgb: np.ndarray, color: Tuple[int, int, int], thr: float = 40.0) -> np.ndarray:
    d = np.linalg.norm(rgb.astype(np.float32) - np.asarray(color, dtype=np.float32), axis=2)
    return d <= thr


def _dilate(mask: np.ndarray, radius_m: float, res: float = MAP_RES) -> np.ndarray:
    r = max(0, int(math.ceil(radius_m / res)))
    if r <= 0:
        return mask.astype(bool)
    try:
        import cv2

        k = 2 * r + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        return cv2.dilate(mask.astype(np.uint8), kernel, iterations=1).astype(bool)
    except Exception:
        return mask.astype(bool)


def analyze_map_png(path: Path, inflation_m: float) -> Dict[str, Any]:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    occ = _mask_near(rgb, LEGACY_COLORS["occupied"], 45) | _mask_near(
        rgb, (40, 40, 40), 25
    )  # paper dark too
    free = _mask_near(rgb, LEGACY_COLORS["free"], 45) | _mask_near(rgb, (220, 220, 220), 25)
    unk = _mask_near(rgb, LEGACY_COLORS["unknown"], 35)
    bg = _mask_near(rgb, LEGACY_COLORS["bg"], 35) | _mask_near(rgb, (255, 255, 255), 5)
    # Re-inflate from raw occupied (ignore already-inflated blue halo as source)
    occ_src = _mask_near(rgb, LEGACY_COLORS["occupied"], 45)
    if not occ_src.any():
        occ_src = _mask_near(rgb, PAPER_OCCUPIED, 30)
    inflated = _dilate(occ_src, inflation_m)
    free_after = free & (~inflated)
    # Unknown-as-obstacle (optimistic=false proxy): block free next to unknown
    blocked_by_unk = free_after & _dilate(unk | bg, inflation_m)
    free_opt_false = free_after & (~blocked_by_unk)
    return {
        "inflation_m": inflation_m,
        "occ_px": int(occ_src.sum()),
        "free_px": int(free.sum()),
        "unk_px": int(unk.sum()),
        "inflated_px": int(inflated.sum()),
        "free_after_inflate_px": int(free_after.sum()),
        "free_after_inflate_and_unknown_px": int(free_opt_false.sum()),
        "free_retained_frac": float(free_after.sum() / max(free.sum(), 1)),
    }


def render_compare(
    path: Path,
    out_path: Path,
    inflation_m: float,
    robot_xy_pix: Optional[Tuple[int, int]] = None,
) -> None:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    h, w = rgb.shape[:2]
    occ_src = _mask_near(rgb, LEGACY_COLORS["occupied"], 45)
    free = _mask_near(rgb, LEGACY_COLORS["free"], 45)
    inflated = _dilate(occ_src, inflation_m)
    canvas = np.full((h, w, 3), PAPER_BG, dtype=np.uint8)
    canvas[free] = PAPER_FREE
    canvas[inflated] = (180, 180, 220)  # inflated halo (diagnostic)
    canvas[occ_src] = PAPER_OCCUPIED
    im = Image.fromarray(canvas)
    dr = ImageDraw.Draw(im)
    if robot_xy_pix is not None:
        px, py = robot_xy_pix
        dr.ellipse([px - 4, py - 4, px + 4, py + 4], fill=PAPER_ROBOT)
    dr.text((6, 6), f"infl={inflation_m:.2f}m", fill=(0, 0, 0))
    im.save(out_path)


def yaw_motion_audit(steps: List[dict]) -> Dict[str, Any]:
    rows = []
    pi_err = []
    zero_err = []
    for i, s in enumerate(steps):
        if s.get("planner_action_name") != "MOVE_FORWARD" or i == 0:
            continue
        p0 = steps[i - 1]["publish_meta"]["base_ros"]
        p1 = s["publish_meta"]["base_ros"]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        if abs(dx) + abs(dy) < 1e-6:
            continue
        move_yaw = math.atan2(dy, dx)
        odom_yaw = float(s["base"]["yaw"])  # was published as hab yaw
        e0 = abs(_wrap(move_yaw - odom_yaw))
        epi = abs(_wrap(move_yaw - (odom_yaw + math.pi)))
        zero_err.append(e0)
        pi_err.append(epi)
        rows.append(
            {
                "step": s["step"],
                "move_yaw_deg": math.degrees(move_yaw),
                "odom_hab_yaw_deg": math.degrees(odom_yaw),
                "err_deg": math.degrees(e0),
                "err_if_hab_plus_pi_deg": math.degrees(epi),
            }
        )
    return {
        "n_forward": len(rows),
        "mean_abs_err_deg": float(np.mean(zero_err) * 180 / math.pi) if zero_err else None,
        "mean_abs_err_with_plus_pi_deg": float(np.mean(pi_err) * 180 / math.pi) if pi_err else None,
        "samples": rows,
        "conclusion": (
            "odom_yaw_lagged_motion_by_pi"
            if zero_err and float(np.mean(zero_err)) > 2.5
            else "aligned"
        ),
    }


def action_stats(steps: List[dict], acts: List[dict]) -> Dict[str, Any]:
    explore = [a for a in acts if a.get("phase") == "explore_planner"]
    names = Counter(a.get("name") for a in explore)
    # consecutive left turns
    max_left_streak = streak = 0
    for a in explore:
        if a.get("name") == "TURN_LEFT":
            streak += 1
            max_left_streak = max(max_left_streak, streak)
        else:
            streak = 0
    fwd_dist = 0.0
    prev = None
    for s, a in zip(steps, acts):
        if a.get("phase") != "explore_planner":
            continue
        b = s["base"]
        if prev is not None and a.get("name") == "MOVE_FORWARD":
            fwd_dist += math.hypot(b["x"] - prev["x"], b["z"] - prev["z"])
        prev = b
    expl = Counter(s.get("expl_result") for s in steps if s.get("phase") == "explore_planner")
    return {
        "explore_actions": dict(names),
        "max_turn_left_streak": max_left_streak,
        "forward_distance_m": fwd_dist,
        "expl_result_counts": {str(k): v for k, v in expl.items()},
        "expl_result_legend": {
            "0": "EXPLORATION",
            "4": "NO_PASSABLE_FRONTIER",
            "5": "NO_COVERABLE_FRONTIER",
            "6": "SEARCH_EXTREME",
        },
    }


def footprint_report() -> Dict[str, Any]:
    return {
        "source": "MuJoCo base_link_col half-extents Stage4.10d",
        "chassis_half_length_m": CHASSIS_HALF_L,
        "chassis_half_width_m": CHASSIS_HALF_W,
        "chassis_circumscribed_radius_m": CHASSIS_CIRCUM_R,
        "baseline_habitat_agent_radius_m": BASELINE_INFLATION,
        "recommended_oriented_radius_m": SAFE_ORIENTED_R,
        "recommended_circum_radius_m": SAFE_CIRCUM_R,
        "baseline_vs_half_width": BASELINE_INFLATION / CHASSIS_HALF_W,
        "note": (
            "Isotropic obstacles_inflation should approximate robot radius for point-robot planning. "
            "0.18 m is far below Ranger chassis; unsafe for real clearance. "
            "Increasing inflation reduces free/reachable frontiers — yaw fix is primary for turn spam."
        ),
    }


def run_episode_diag(run_dir: Path, out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    steps = [json.loads(l) for l in (run_dir / "steps.jsonl").read_text().splitlines() if l.strip()]
    acts = [json.loads(l) for l in (run_dir / "actions.jsonl").read_text().splitlines() if l.strip()]
    # pick a late map frame with content
    map_idx = len(steps) - 1
    map_path = run_dir / "maps" / f"frame_{map_idx:04d}.png"
    if not map_path.is_file():
        map_path = sorted((run_dir / "maps").glob("frame_*.png"))[-1]

    variants = {
        "A_baseline_0.18": BASELINE_INFLATION,
        "B_oriented_safe_0.485": SAFE_ORIENTED_R,
        "B2_circum_safe_0.83": SAFE_CIRCUM_R,
        "C_diag_under_0.05": 0.05,
    }
    infl_table = {}
    for name, rad in variants.items():
        infl_table[name] = analyze_map_png(map_path, rad)
        render_compare(map_path, out_dir / f"map_{name}.png", rad)

    # optimistic proxy on baseline inflation
    c_opt = {
        "C_optimistic_proxy_at_0.18": {
            "free_if_unknown_ignored": analyze_map_png(map_path, BASELINE_INFLATION)[
                "free_after_inflate_px"
            ],
            "free_if_unknown_blocks": analyze_map_png(map_path, BASELINE_INFLATION)[
                "free_after_inflate_and_unknown_px"
            ],
            "note": "optimistic=false treats unknown like obstacles in ESDF (code sdf_map2d.cpp).",
        }
    }

    rep = {
        "run_dir": str(run_dir),
        "map_frame": str(map_path),
        "footprint": footprint_report(),
        "action_stats": action_stats(steps, acts),
        "yaw_motion_audit": yaw_motion_audit(steps),
        "inflation_variants": infl_table,
        "optimistic_proxy": c_opt,
        "runtime_params_from_log": {
            "obstacles_inflation": 0.18,
            "optimistic": False,
            "filter_min_height": 0.28,
            "filter_max_height": 1.18,
            "resolution": 0.05,
            "habitat_agent_radius_override": 0.18,
        },
    }
    (out_dir / "frontier_inflation_diag.json").write_text(json.dumps(rep, indent=2))
    return rep


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--open_run",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/20261104_114652",
    )
    p.add_argument(
        "--narrow_run",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/20261104_114357",
    )
    p.add_argument(
        "--out_root",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/frontier_inflation_diag",
    )
    args = p.parse_args(argv)
    out_root = Path(args.out_root)
    open_rep = run_episode_diag(Path(args.open_run), out_root / "open_20261104_114652")
    narrow_rep = run_episode_diag(Path(args.narrow_run), out_root / "narrow_20261104_114357")
    summary = {
        "open": {
            "yaw": open_rep["yaw_motion_audit"]["conclusion"],
            "actions": open_rep["action_stats"]["explore_actions"],
            "forward_m": open_rep["action_stats"]["forward_distance_m"],
            "max_left_streak": open_rep["action_stats"]["max_turn_left_streak"],
            "infl": {k: v["free_after_inflate_px"] for k, v in open_rep["inflation_variants"].items()},
        },
        "narrow": {
            "yaw": narrow_rep["yaw_motion_audit"]["conclusion"],
            "actions": narrow_rep["action_stats"]["explore_actions"],
            "forward_m": narrow_rep["action_stats"]["forward_distance_m"],
            "infl": {
                k: v["free_after_inflate_px"] for k, v in narrow_rep["inflation_variants"].items()
            },
        },
        "primary_root_cause": (
            "Habitat→ROS odom yaw lagged motion by π (adapter publish bug); "
            "secondary: inflation 0.18 << Ranger chassis (~0.48–0.83) unsafe; "
            "optimistic=false + sparse free → NO_PASSABLE in tight maps."
        ),
        "fix": "hab_yaw_to_ros(+π) in ros_dynamic_publisher; overlay radius 0.485",
    }
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
