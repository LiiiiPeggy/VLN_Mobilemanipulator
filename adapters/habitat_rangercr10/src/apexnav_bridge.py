"""Bounded ApexNav closed-loop sketch on top of kinematic Ranger env.

Does **not** modify baselines/ApexNav configs. High-level search stays in ApexNav;
this bridge only:
  - maps discrete Habitat actions → kinematic base SE(2) steps
  - feeds EE RGB-D + pose back as observations (when wired)

Default mode is a **dry-run / stub** that exercises the motion+camera loop with a
fixed action sequence, documenting where ApexNav planner wiring would plug in.
Full planner ROS loop requires the existing ApexNav container (kept untouched).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .constants import DEFAULT_OUT_DIR, DEFAULT_SCENE, MODE_KINEMATIC, URDF_HABITAT
from .kinematic_demo import RangerCr10KinematicEnv
from .traj_utils import save_depth_mm

# ApexNav params.ACTION mapping (baselines/ApexNav/params.py)
STOP, MOVE_FORWARD, TURN_LEFT, TURN_RIGHT, LOOK_UP, LOOK_DOWN = range(6)
FORWARD_M = 0.25
TURN_RAD = math.radians(30)


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
        # approximate: lift wrist pitch via joint5
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


def run_bounded(args: argparse.Namespace) -> dict:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rgb_ee").mkdir(exist_ok=True)
    (out / "depth_ee").mkdir(exist_ok=True)

    env = RangerCr10KinematicEnv(scene=args.scene, urdf=args.urdf, gpu_device_id=args.gpu)
    env.set_base_pose(1.0, 1.0, 0.0)
    # scripted "search" sequence: turn scan + forward (placeholder for ApexNav actions)
    actions = (
        [TURN_LEFT] * 4
        + [MOVE_FORWARD] * 3
        + [TURN_RIGHT] * 2
        + [LOOK_UP, LOOK_DOWN]
        + [MOVE_FORWARD] * 2
        + [STOP]
    )
    t0 = time.time()
    log = []
    for i, a in enumerate(actions[: args.max_steps]):
        apply_discrete_action(env, a)
        obs = env.observe()
        Image.fromarray(obs["ee_rgb"][..., :3]).save(out / "rgb_ee" / f"frame_{i:04d}.png")
        save_depth_mm(out / "depth_ee" / f"frame_{i:04d}.png", obs["ee_depth"])
        log.append(
            {
                "i": i,
                "action": int(a),
                "base": {
                    "x": float(env.base_xyz[0]),
                    "z": float(env.base_xyz[2]),
                    "yaw": float(env.base_yaw),
                },
                "arm": env.arm_q.tolist(),
                "contacts": env.contact_count(),
            }
        )
    elapsed = time.time() - t0
    summary = {
        "status": "stub_ok",
        "control_mode": MODE_KINEMATIC,
        "apexnav_planner": "not_connected",
        "note": (
            "Bounded multi-step EE RGB-D loop with ApexNav action IDs. "
            "High-level ObjectNav planner not invoked this round; "
            "wire /habitat/plan_action in a follow-up without editing baseline defaults."
        ),
        "max_steps": args.max_steps,
        "n_steps": len(log),
        "elapsed_sec": elapsed,
        "out_dir": str(out),
        "log": log,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    env.close()
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--urdf", default=URDF_HABITAT)
    p.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "apexnav_stub"))
    p.add_argument("--max_steps", type=int, default=16)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args()
    print(json.dumps(run_bounded(args), indent=2))


if __name__ == "__main__":
    main()
