#!/usr/bin/env python3
"""Offline: overlay executed traj + native A* path on demo map inset.

################################
Rewrites maps/frame_*.png and demo/frame_*.png for a finished run, then
re-encodes apexnav_ranger_paper_demo.mp4 (keeps *.mp4.bak). Demo-only; no
planner / Habitat re-sim. Requires native_diag/native_plan_diag.jsonl.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

# Allow `python scripts/overlay_...py` from adapters/habitat_rangercr10
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.demo_compose import compose_frame  # noqa: E402
from src.map_style import (  # noqa: E402
    PAPER_PATH,
    PAPER_ROBOT,
    PAPER_TRAJ,
    PAPER_WAYPOINT,
)


def _load_jsonl(path: Path) -> List[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _hab_to_ros_xy(base: dict) -> Tuple[float, float]:
    return (-float(base["z"]), -float(base["x"]))


def _plan_for_step(
    plans: List[dict],
    step: dict,
    acts_by_step: Dict[int, dict],
) -> List[Tuple[float, float]]:
    rec = step.get("astar_plan_ros")
    if isinstance(rec, list) and len(rec) >= 2:
        out = []
        for p in rec:
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                out.append((float(p[0]), float(p[1])))
        if len(out) >= 2:
            return out
    if not plans:
        return []
    si = int(step.get("step", 0))
    t = float((acts_by_step.get(si) or {}).get("t", 0.0) or 0.0)
    latest = None
    for p in plans:
        if t <= 0.0 or float(p.get("stamp", 0.0)) <= t + 0.5:
            latest = p
    if not latest:
        return []
    out = []
    for p in latest.get("selected_path") or []:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            out.append((float(p[0]), float(p[1])))
    return out


def _center_yaw(step: dict) -> Tuple[float, float, float]:
    pub = step.get("publish_meta") or {}
    if pub.get("odom_ros_plan_proxy"):
        cx, cy = float(pub["odom_ros_plan_proxy"][0]), float(pub["odom_ros_plan_proxy"][1])
    elif pub.get("base_ros"):
        cx, cy = float(pub["base_ros"][0]), float(pub["base_ros"][1])
    else:
        cx, cy = _hab_to_ros_xy(step["base"])
    yaw = float(pub.get("base_yaw_ros", 0.0))
    return cx, cy, yaw


def _traj_upto(steps: List[dict], hold_i: int) -> List[Tuple[float, float]]:
    traj = []
    for i in range(hold_i + 1):
        pub = steps[i].get("publish_meta") or {}
        if pub.get("odom_ros_plan_proxy"):
            traj.append(
                (
                    float(pub["odom_ros_plan_proxy"][0]),
                    float(pub["odom_ros_plan_proxy"][1]),
                )
            )
        elif pub.get("base_ros"):
            traj.append((float(pub["base_ros"][0]), float(pub["base_ros"][1])))
        else:
            traj.append(_hab_to_ros_xy(steps[i]["base"]))
    return traj


def overlay_paths_on_map(
    map_rgb: np.ndarray,
    *,
    cx: float,
    cy: float,
    yaw: float,
    traj: List[Tuple[float, float]],
    plan: List[Tuple[float, float]],
    meters_span: float = 12.0,
) -> np.ndarray:
    """Draw purple A*, orange traj, blue robot on an existing map PNG."""
    # ################################
    # Existing maps already contain traj/robot; redraw plan under traj/robot
    # so both layers are visible and ordered correctly.
    # ################################
    h, w = map_rgb.shape[:2]
    scale = w / meters_span

    def to_pix(xy):
        px = int((xy[0] - cx) * scale + w / 2)
        py = int(-(xy[1] - cy) * scale + h / 2)
        return px, py

    im = Image.fromarray(map_rgb.copy())
    dr = ImageDraw.Draw(im)
    if len(plan) >= 2:
        dr.line([to_pix(p) for p in plan], fill=PAPER_PATH, width=2)
        gx, gy = to_pix(plan[-1])
        dr.ellipse([gx - 4, gy - 4, gx + 4, gy + 4], fill=PAPER_WAYPOINT)
        dr.ellipse([gx - 6, gy - 6, gx + 6, gy + 6], outline=PAPER_WAYPOINT)
    if len(traj) >= 2:
        dr.line([to_pix(p) for p in traj], fill=PAPER_TRAJ, width=2)
    px, py = to_pix((cx, cy))
    tip = (int(px + 12 * math.cos(yaw)), int(py - 12 * math.sin(yaw)))
    dr.ellipse([px - 5, py - 5, px + 5, py + 5], fill=PAPER_ROBOT)
    dr.line([(px, py), tip], fill=PAPER_ROBOT, width=2)
    return np.asarray(im)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", type=Path, required=True)
    ap.add_argument("--fps", type=float, default=2.0)
    args = ap.parse_args()
    run_dir = args.run_dir.resolve()
    steps = _load_jsonl(run_dir / "steps.jsonl")
    acts = _load_jsonl(run_dir / "actions.jsonl")
    acts_by_step = {int(a["step"]): a for a in acts}
    plan_file = run_dir / "native_diag" / "native_plan_diag.jsonl"
    plans = _load_jsonl(plan_file) if plan_file.is_file() else []
    if not plans:
        raise SystemExit(f"missing native A* diag: {plan_file}")

    ep = {}
    if (run_dir / "episode.json").is_file():
        ep = json.loads((run_dir / "episode.json").read_text())
    goal = str(ep.get("object_category", "object"))

    maps_dir = run_dir / "maps"
    demo_dir = run_dir / "demo"
    third_dir = run_dir / "third"
    det_dir = run_dir / "detections"
    n_with_plan = 0
    for step in steps:
        si = int(step["step"])
        map_path = maps_dir / f"frame_{si:04d}.png"
        if not map_path.is_file():
            continue
        cx, cy, yaw = _center_yaw(step)
        plan = _plan_for_step(plans, step, acts_by_step)
        if len(plan) >= 2:
            n_with_plan += 1
        traj = _traj_upto(steps, si)
        map_rgb = np.asarray(Image.open(map_path).convert("RGB"))
        map_rgb = overlay_paths_on_map(
            map_rgb, cx=cx, cy=cy, yaw=yaw, traj=traj, plan=plan
        )
        Image.fromarray(map_rgb).save(map_path)

        third_p = third_dir / f"frame_{si:04d}.png"
        det_p = det_dir / f"frame_{si:04d}.png"
        if third_p.is_file() and det_p.is_file():
            third = np.asarray(Image.open(third_p).convert("RGB"))
            sem = np.asarray(Image.open(det_p).convert("RGB"))
            demo = compose_frame(
                third,
                sem,
                map_rgb,
                goal=goal,
                step=si,
                action=str(step.get("planner_action_name") or ""),
                phase=str(step.get("phase") or ""),
                control_mode=str(step.get("control_mode") or "kinematic_state_set"),
                status="running",
            )
            Image.fromarray(demo).save(demo_dir / f"frame_{si:04d}.png")

    mp4 = demo_dir / "apexnav_ranger_paper_demo.mp4"
    if mp4.is_file():
        bak = demo_dir / "apexnav_ranger_paper_demo.mp4.bak"
        if not bak.is_file():
            shutil.copy2(mp4, bak)
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(args.fps),
        "-i",
        str(demo_dir / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "23",
        str(mp4),
    ]
    subprocess.check_call(cmd)
    meta = {
        "run_dir": str(run_dir),
        "n_steps": len(steps),
        "n_frames_with_astar_path": n_with_plan,
        "n_plans": len(plans),
        "mp4": str(mp4),
        "overlay": "executed_traj_orange + astar_selected_path_purple",
    }
    (demo_dir / "astar_path_overlay_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
