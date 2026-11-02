"""Bounded ApexNav-style closed loop on kinematic Ranger env (native Habitat).

Does **not** modify baselines/ApexNav configs. This round:
  - uses ApexNav discrete action IDs (params.ACTION)
  - executes them as kinematic base/arm state sets
  - records EE RGB-D each step (dynamic camera)
  - maintains a tiny occupancy stub from depth (not full ApexNav map)

Full ROS planner (`/habitat/plan_action`) is optional follow-up; when unavailable we
run a scripted exploration sequence and mark `apexnav_planner=scripted_actions`.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np
from PIL import Image

from .constants import DEFAULT_OUT_DIR, DEFAULT_SCENE, MODE_KINEMATIC, URDF_HABITAT
from .kinematic_demo import RangerCr10KinematicEnv
from .traj_utils import save_depth_mm

STOP, MOVE_FORWARD, TURN_LEFT, TURN_RIGHT, LOOK_UP, LOOK_DOWN = range(6)
FORWARD_M = 0.25
TURN_RAD = math.radians(30)
ACTION_NAME = {
    STOP: "STOP",
    MOVE_FORWARD: "MOVE_FORWARD",
    TURN_LEFT: "TURN_LEFT",
    TURN_RIGHT: "TURN_RIGHT",
    LOOK_UP: "LOOK_UP",
    LOOK_DOWN: "LOOK_DOWN",
}


def apply_discrete_action(env: RangerCr10KinematicEnv, action: int) -> None:
    x, y, z = env.base_xyz
    yaw = env.base_yaw
    if action == MOVE_FORWARD:
        x += FORWARD_M * math.sin(yaw)
        z += FORWARD_M * math.cos(yaw)
    elif action == TURN_LEFT:
        yaw += TURN_RAD
    elif action == TURN_RIGHT:
        yaw -= TURN_RAD
    elif action == LOOK_UP:
        q = env.arm_q.copy()
        q[4] = float(np.clip(q[4] - 0.15, -2.0, 2.0))
        env.set_arm_joints(q)
        return
    elif action == LOOK_DOWN:
        q = env.arm_q.copy()
        q[4] = float(np.clip(q[4] + 0.15, -2.0, 2.0))
        env.set_arm_joints(q)
        return
    elif action == STOP:
        return
    env.set_base_pose(float(x), float(z), float(yaw), y=float(y))


def depth_obstacle_ratio(depth: np.ndarray, near: float = 0.3, far: float = 2.0) -> float:
    valid = depth[(depth > near) & (depth < far)]
    if valid.size == 0:
        return 0.0
    return float(valid.size) / float(depth.size)


def scripted_policy(step: int, obstacle_ratio: float) -> int:
    """Tiny stand-in for ApexNav planner: turn away from close depth, else explore."""
    if obstacle_ratio > 0.12:
        return TURN_LEFT if (step % 2 == 0) else TURN_RIGHT
    seq = [TURN_LEFT, TURN_LEFT, MOVE_FORWARD, MOVE_FORWARD, TURN_RIGHT, MOVE_FORWARD, LOOK_UP, LOOK_DOWN]
    return seq[step % len(seq)]


def run_bounded(args: argparse.Namespace) -> dict:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rgb_ee").mkdir(exist_ok=True)
    (out / "depth_ee").mkdir(exist_ok=True)
    (out / "third").mkdir(exist_ok=True)

    env = None
    log = []
    status = "ok"
    error = None
    t0 = time.time()
    try:
        env = RangerCr10KinematicEnv(scene=args.scene, urdf=args.urdf, gpu_device_id=args.gpu)
        env.set_base_pose(1.0, 1.0, 0.0)
        stopped = False
        for i in range(args.max_steps):
            obs = env.observe()
            depth = obs["ee_depth"]
            ratio = depth_obstacle_ratio(depth)
            if stopped:
                action = STOP
            else:
                action = scripted_policy(i, ratio)
                if i >= args.max_steps - 1:
                    action = STOP
                    stopped = True
            apply_discrete_action(env, action)
            if action == STOP:
                stopped = True
            # observe after motion
            obs = env.observe()
            Image.fromarray(obs["ee_rgb"][..., :3]).save(out / "rgb_ee" / f"frame_{i:04d}.png")
            save_depth_mm(out / "depth_ee" / f"frame_{i:04d}.png", obs["ee_depth"])
            Image.fromarray(obs["third_rgb"][..., :3]).save(out / "third" / f"frame_{i:04d}.png")
            log.append(
                {
                    "i": i,
                    "action": int(action),
                    "action_name": ACTION_NAME.get(int(action), str(action)),
                    "obstacle_ratio": ratio,
                    "base": {
                        "x": float(env.base_xyz[0]),
                        "y": float(env.base_xyz[1]),
                        "z": float(env.base_xyz[2]),
                        "yaw": float(env.base_yaw),
                    },
                    "arm": env.arm_q.tolist(),
                    "contacts": env.contact_count(),
                    "joint_limits_ok": all(v["within"] for v in env.joint_limits_report().values()),
                    "depth_stats": {
                        "min": float(np.min(obs["ee_depth"])),
                        "max": float(np.max(obs["ee_depth"])),
                        "mean": float(np.mean(obs["ee_depth"])),
                    },
                }
            )
            if stopped and action == STOP and i >= 1:
                # allow one STOP frame then end
                break
    except Exception as e:
        status = "failed"
        error = f"{type(e).__name__}: {e}"
        (out / "error.log").write_text(traceback.format_exc())
        raise
    finally:
        if env is not None:
            env.close()

    elapsed = time.time() - t0
    summary = {
        "status": status,
        "control_mode": MODE_KINEMATIC,
        "apexnav_planner": "scripted_actions",
        "note": (
            "Bounded multi-step loop with ApexNav action IDs + EE RGB-D feedback. "
            "Not full ApexNav ROS planner; not PPO whole-body dynamics."
        ),
        "max_steps": args.max_steps,
        "n_steps": len(log),
        "elapsed_sec": elapsed,
        "out_dir": str(out),
        "error": error,
        "log": log,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--urdf", default=URDF_HABITAT)
    p.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "apexnav_loop"))
    p.add_argument("--max_steps", type=int, default=16)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args()
    try:
        summary = run_bounded(args)
        print(json.dumps({k: v for k, v in summary.items() if k != "log"}, indent=2))
        return 0 if summary.get("status") == "ok" else 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
