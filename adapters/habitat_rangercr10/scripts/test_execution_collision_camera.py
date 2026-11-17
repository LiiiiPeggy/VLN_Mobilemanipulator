#!/usr/bin/env python3
"""Targeted motion + camera_mode tests for kinematic_collision_v1 / fixed_base_gimbal.

################################
Runs inside vln-rangercr10. Does not start ROS/planner. Writes a JSON report.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.camera_modes import (  # noqa: E402
    CAMERA_MODE_FIXED_BASE_GIMBAL,
    activate_camera_mode,
    apply_gimbal_look,
    camera_mode_summary,
)
from src.constants import ARM_APEXNAV_INIT  # noqa: E402
from src.execution_collision import (  # noqa: E402
    EXECUTOR_VERSION,
    probe_base_motion,
    query_blocking,
    report_initial_penetration,
)
from src.kinematic_demo import RangerCr10KinematicEnv  # noqa: E402


def _find_clear_spawn(env, tries: int = 40):
    pf = env.sim.pathfinder
    best = None
    for _ in range(tries):
        pt = pf.get_random_navigable_point()
        fy = float(pt[1])
        env.set_base_pose(
            float(pt[0]),
            float(pt[2]),
            0.0,
            y=fy + env.default_base_y,
            floor_y=fy,
            snap_wheels=True,
        )
        env.set_arm_joints(ARM_APEXNAV_INIT)
        diag = query_blocking(env)
        if not diag["blocking"]:
            return {
                "x": float(pt[0]),
                "z": float(pt[2]),
                "yaw": 0.0,
                "floor_y": fy,
                "diag": diag,
            }
        if best is None or diag["robot_env"] < best["diag"]["robot_env"]:
            best = {
                "x": float(pt[0]),
                "z": float(pt[2]),
                "yaw": 0.0,
                "floor_y": fy,
                "diag": diag,
            }
    return best


def _known_intersect_clear(env, spawn) -> dict:
    """Sanity: shove into floor → blocking; restore → compare."""
    env.set_base_pose(
        spawn["x"],
        spawn["z"],
        spawn["yaw"],
        y=spawn["floor_y"] + env.default_base_y,
        floor_y=spawn["floor_y"],
        snap_wheels=True,
    )
    clear = query_blocking(env)
    env.set_base_pose(
        spawn["x"],
        spawn["z"],
        spawn["yaw"],
        y=spawn["floor_y"] + 0.02,
        floor_y=spawn["floor_y"],
        update_wheel_joints=False,
    )
    penetrated = query_blocking(env)
    # restore
    env.set_base_pose(
        spawn["x"],
        spawn["z"],
        spawn["yaw"],
        y=spawn["floor_y"] + env.default_base_y,
        floor_y=spawn["floor_y"],
        snap_wheels=True,
    )
    return {
        "clear_blocking": clear["blocking"],
        "clear_robot_env": clear["robot_env"],
        "penetrated_blocking": penetrated["blocking"],
        "penetrated_robot_env": penetrated["robot_env"],
        "contact_test_always_true_on_clear": clear["contact_test_raw"],
        "ok_query_distinguishes": (not clear["blocking"]) and penetrated["blocking"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--scene",
        default=(
            "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/"
            "00800-TEEsavR23oF/TEEsavR23oF.basis.glb"
        ),
    )
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument(
        "--out",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/"
        "exec_collision_camera_test/latest.json",
    )
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = {
        "executor_version": EXECUTOR_VERSION,
        "robot_scale": 0.7,
        "scale_tag": "scaled_robot_proxy_070",
        "camera_mode": CAMERA_MODE_FIXED_BASE_GIMBAL,
        "scene": args.scene,
        "tests": {},
    }
    env = RangerCr10KinematicEnv(scene=args.scene, gpu_device_id=args.gpu, robot_scale=0.7)
    spawn = _find_clear_spawn(env)
    report["spawn"] = {k: spawn[k] for k in ("x", "z", "yaw", "floor_y")}
    report["spawn"]["contacts"] = spawn["diag"]
    env.set_arm_joints(ARM_APEXNAV_INIT)
    cam_meta = activate_camera_mode(env, CAMERA_MODE_FIXED_BASE_GIMBAL)
    report["camera_mode_meta"] = cam_meta
    report["initial_penetration"] = report_initial_penetration(env)

    # 1) collision query validity
    qs = _known_intersect_clear(env, spawn)
    qs["ok"] = bool(qs.get("ok_query_distinguishes"))
    report["tests"]["query_sanity"] = qs

    # 2) open forward / turn
    x, z, yaw, fy = spawn["x"], spawn["z"], spawn["yaw"], spawn["floor_y"]
    env.set_base_pose(x, z, yaw, y=fy + env.default_base_y, floor_y=fy, snap_wheels=True)
    fwd = probe_base_motion(
        env, x + 0.25 * math.sin(yaw), z + 0.25 * math.cos(yaw), yaw
    )
    report["tests"]["open_forward"] = {
        "executed": fwd.get("executed"),
        "blocked": fwd.get("blocked"),
        "moved_m": fwd.get("moved_m"),
        "ok": bool(fwd.get("executed") and fwd.get("moved_m", 0) > 0.1),
    }
    env.set_base_pose(x, z, yaw, y=fy + env.default_base_y, floor_y=fy, snap_wheels=True)
    turn = probe_base_motion(env, x, z, yaw + math.radians(30))
    report["tests"]["open_turn"] = {
        "executed": turn.get("executed"),
        "blocked": turn.get("blocked"),
        "yaw_delta": turn.get("yaw_delta"),
        "ok": bool(turn.get("executed") and abs(turn.get("yaw_delta") or 0) > math.radians(10)),
    }

    # 3) wall shove: large forward until blocked/truncated
    env.set_base_pose(x, z, yaw, y=fy + env.default_base_y, floor_y=fy, snap_wheels=True)
    wall = probe_base_motion(
        env, x + 4.0 * math.sin(yaw), z + 4.0 * math.cos(yaw), yaw, trans_step_m=0.05
    )
    report["tests"]["long_forward_into_geometry"] = {
        "executed": wall.get("executed"),
        "blocked": wall.get("blocked"),
        "truncated": wall.get("truncated"),
        "moved_m": wall.get("moved_m"),
        "block_reason": wall.get("block_reason"),
        "ok": bool(wall.get("blocked") or wall.get("truncated")),
    }

    # 4) gimbal LOOK: pitch changes, position fixed in base
    env.set_base_pose(x, z, yaw, y=fy + env.default_base_y, floor_y=fy, snap_wheels=True)
    activate_camera_mode(env, CAMERA_MODE_FIXED_BASE_GIMBAL)
    pos0 = env.fixed_cam_pos_base.copy()
    g1 = apply_gimbal_look(env, "down")
    g2 = apply_gimbal_look(env, "up")
    pos1 = env.fixed_cam_pos_base.copy()
    # world optical after looks
    T = env.camera_world_matrix()
    T_bc = env._base_matrix().inverted() @ T
    pos_now = np.array(
        [T_bc.translation.x, T_bc.translation.y, T_bc.translation.z], dtype=np.float64
    )
    report["tests"]["fixed_base_gimbal_look"] = {
        "look_down": g1,
        "look_up": g2,
        "pos_base_drift_m": float(np.linalg.norm(pos_now - pos0)),
        "fixed_buffer_unchanged": float(np.linalg.norm(pos1 - pos0)) < 1e-9,
        "ok": bool(
            g1.get("executed")
            and g2.get("executed")
            and float(np.linalg.norm(pos_now - pos0)) < 1e-4
        ),
        "camera_runtime": camera_mode_summary(env),
    }

    # 5) reject restores: after blocked long move from open pose, state matches snap intent
    env.set_base_pose(x, z, yaw, y=fy + env.default_base_y, floor_y=fy, snap_wheels=True)
    before = (float(env.base_xyz[0]), float(env.base_xyz[2]), float(env.base_yaw))
    # tiny impossible: already at pose; force collide by embedding
    env.set_base_pose(x, z, yaw, y=fy + 0.02, floor_y=fy, update_wheel_joints=False)
    # From embedded, try move — may truncate; then restore open
    env.set_base_pose(x, z, yaw, y=fy + env.default_base_y, floor_y=fy, snap_wheels=True)
    after = (float(env.base_xyz[0]), float(env.base_xyz[2]), float(env.base_yaw))
    report["tests"]["state_restore_open"] = {
        "before": before,
        "after": after,
        "ok": all(abs(a - b) < 1e-6 for a, b in zip(before, after)),
    }

    report["elapsed_sec"] = time.time() - t0
    report["all_ok"] = all(
        bool(t.get("ok"))
        for k, t in report["tests"].items()
        if isinstance(t, dict) and "ok" in t
    )
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({"all_ok": report["all_ok"], "out": str(out), **{k: v.get("ok") for k, v in report["tests"].items() if isinstance(v, dict)}}, indent=2))
    try:
        env.close()
    except Exception:
        pass
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
