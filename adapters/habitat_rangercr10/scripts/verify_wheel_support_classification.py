#!/usr/bin/env python3
"""Verify wheel-support vs side-hit classification (no ROS/planner).

################################
Places the scaled Ranger at known poses and checks classify_contacts():
  - open floor: wheels → wheel_support (upright)
  - shove into floor: robot_env (deep) or support if shallow
  - translate into wall / furniture: side contacts must be robot_env even if
    vs_stage and near floor height (regression for upright||vs_stage bug)

Runs inside vln-rangercr10. Does not start ROS.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.constants import ARM_APEXNAV_INIT  # noqa: E402
from src.execution_collision import (  # noqa: E402
    EXECUTOR_VERSION,
    SUPPORT_NORMAL_Y_MIN,
    classify_contacts,
    probe_base_motion,
    query_blocking,
)
from src.kinematic_demo import RangerCr10KinematicEnv  # noqa: E402


def _set_pose(env, x, z, yaw, floor_y):
    env.set_base_pose(
        float(x),
        float(z),
        float(yaw),
        y=float(floor_y) + env.default_base_y,
        floor_y=float(floor_y),
        snap_wheels=True,
    )
    env.set_arm_joints(ARM_APEXNAV_INIT)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument(
        "--scene",
        default="/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/00824-Dd4bFSTQ8gi/Dd4bFSTQ8gi.basis.glb",
    )
    p.add_argument("--robot_scale", type=float, default=0.7)
    p.add_argument("--out", default="")
    args = p.parse_args()

    env = RangerCr10KinematicEnv(
        scene=args.scene, gpu_id=args.gpu, robot_scale=args.robot_scale
    )
    pf = env.sim.pathfinder
    report = {
        "executor_version": EXECUTOR_VERSION,
        "support_normal_y_min": SUPPORT_NORMAL_Y_MIN,
        "cases": [],
    }

    # Case A: open navigable floor
    pt = pf.get_random_navigable_point()
    for _ in range(30):
        pt = pf.get_random_navigable_point()
        _set_pose(env, pt[0], pt[2], 0.0, pt[1])
        d = query_blocking(env)
        if not d["blocking"]:
            break
    _set_pose(env, pt[0], pt[2], 0.0, pt[1])
    d_floor = query_blocking(env)
    report["cases"].append(
        {
            "name": "open_floor",
            "pose": {"x": float(pt[0]), "z": float(pt[2]), "floor_y": float(pt[1])},
            "diag": d_floor,
            "expect_blocking": False,
            "pass": (not d_floor["blocking"]) and d_floor["wheel_support"] > 0,
        }
    )

    # Case B: deep floor shove (should block)
    _set_pose(env, pt[0], pt[2], 0.0, pt[1])
    env.set_base_pose(
        float(pt[0]),
        float(pt[2]),
        0.0,
        y=float(pt[1]) + 0.02,
        floor_y=float(pt[1]),
        update_wheel_joints=False,
    )
    d_deep = query_blocking(env)
    report["cases"].append(
        {
            "name": "deep_floor_shove",
            "diag": d_deep,
            "expect_blocking": True,
            "pass": bool(d_deep["blocking"]),
        }
    )
    _set_pose(env, pt[0], pt[2], 0.0, pt[1])

    # Case C: probe forward until first block — inspect first_blocking details
    # Prefer a heading that hits something within 1.5m
    hit = None
    for yaw in [0.0, math.pi / 2, math.pi, -math.pi / 2]:
        _set_pose(env, pt[0], pt[2], yaw, pt[1])
        x1 = float(pt[0]) + 1.5 * math.sin(yaw)
        z1 = float(pt[2]) + 1.5 * math.cos(yaw)
        res = probe_base_motion(env, x1, z1, yaw, action_hint="probe_forward")
        if res.get("blocked") and res.get("first_blocking_contacts"):
            hit = {"yaw": yaw, "res": res}
            break
    if hit is None:
        report["cases"].append(
            {
                "name": "forward_side_or_obstacle",
                "pass": None,
                "note": "no blocking contact within 1.5m from this spawn",
            }
        )
    else:
        fb = hit["res"]["first_blocking_contacts"]
        details = fb.get("details") or []
        # Any non-upright wheel contact labeled robot_env is the intended fix
        sideish = [
            d
            for d in details
            if d.get("kind") == "robot_env"
            and d.get("is_wheel")
            and not d.get("upright")
        ]
        # Must not classify non-upright as wheel_support
        bad_support = [
            d
            for d in details
            if d.get("kind") == "wheel_support" and not d.get("upright")
        ]
        report["cases"].append(
            {
                "name": "forward_side_or_obstacle",
                "yaw": hit["yaw"],
                "blocked_sample": hit["res"].get("blocked_sample"),
                "has_start_contacts": hit["res"].get("start_contacts") is not None,
                "has_first_blocking": hit["res"].get("first_blocking_contacts") is not None,
                "has_committed": hit["res"].get("committed_contacts") is not None,
                "first_blocking_summary": {
                    "robot_env": fb.get("robot_env"),
                    "wheel_support": fb.get("wheel_support"),
                    "links": fb.get("robot_env_links"),
                    "n_details": len(details),
                    "sideish_wheel_robot_env": len(sideish),
                    "bad_non_upright_support": len(bad_support),
                },
                "sample_details": details[:4],
                "pass": len(bad_support) == 0 and hit["res"].get("first_blocking_contacts") is not None,
            }
        )

    report["all_pass"] = all(
        c.get("pass") in (True, None) for c in report["cases"]
    ) and any(c.get("pass") is True for c in report["cases"])

    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    env.close()
    return 0 if report["all_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
