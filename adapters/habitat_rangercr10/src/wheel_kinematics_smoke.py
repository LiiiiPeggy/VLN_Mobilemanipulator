"""Kinematic 4WS wheel roll/steer smoke (visualization only)."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from .constants import ARM_APEXNAV_INIT, DEFAULT_SCENE, URDF_HABITAT
from .kinematic_demo import RangerCr10KinematicEnv


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--out_dir",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/wheel_kinematics_smoke",
    )
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args(argv)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    env = RangerCr10KinematicEnv(scene=args.scene, urdf=URDF_HABITAT, gpu_device_id=args.gpu)
    try:
        x0, z0, yaw0, fy = 0.36, -1.23, 1.24, 0.01882
        env.set_base_pose(
            x0, z0, yaw0, floor_y=fy, snap_wheels=True, update_wheel_joints=False
        )
        env.set_arm_joints(ARM_APEXNAV_INIT)
        frames = []
        for i in range(8):
            x = x0 + 0.25 * (i + 1) * math.sin(yaw0)
            z = z0 + 0.25 * (i + 1) * math.cos(yaw0)
            env.set_base_pose(x, z, yaw0, floor_y=fy, snap_wheels=False)
            Image.fromarray(env.observe_third_only()[..., :3]).save(out / f"fwd_{i:02d}.png")
            frames.append(
                {
                    "phase": "forward",
                    "i": i,
                    "steer": env.steer_q.tolist(),
                    "wheel": env.wheel_q.tolist(),
                }
            )
        x = x0 + 2.0 * math.sin(yaw0)
        z = z0 + 2.0 * math.cos(yaw0)
        yaw = yaw0
        env.set_base_pose(x, z, yaw, floor_y=fy, snap_wheels=False, update_wheel_joints=False)
        for i in range(6):
            yaw += math.radians(30.0)
            env.set_base_pose(x, z, yaw, floor_y=fy, snap_wheels=False)
            Image.fromarray(env.observe_third_only()[..., :3]).save(out / f"turn_{i:02d}.png")
            frames.append(
                {
                    "phase": "turn",
                    "i": i,
                    "steer": env.steer_q.tolist(),
                    "wheel": env.wheel_q.tolist(),
                }
            )
        wq_before = env.wheel_q.copy()
        sq_before = env.steer_q.copy()
        env.set_arm_joints([0.2, 0.1, -2.0, -0.8, -1.2, 0.0])
        arm_ok = bool(np.allclose(wq_before, env.wheel_q) and np.allclose(sq_before, env.steer_q))
        fwd = [f for f in frames if f["phase"] == "forward"]
        turn = [f for f in frames if f["phase"] == "turn"]
        roll_changed = abs(fwd[-1]["wheel"][0] - fwd[0]["wheel"][0]) > 0.2
        steer_nonzero = max(abs(v) for v in turn[-1]["steer"]) > 0.1
        summary = {
            "control_mode": "kinematic_state_set_wheel_viz",
            "not_wheel_ground_dynamics": True,
            "forward_roll_changed": roll_changed,
            "turn_steer_nonzero": steer_nonzero,
            "arm_only_wheels_frozen": arm_ok,
            "final_steer": turn[-1]["steer"],
            "final_wheel": turn[-1]["wheel"],
            "pass": bool(roll_changed and steer_nonzero and arm_ok),
            "frames": frames,
        }
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps({k: summary[k] for k in summary if k != "frames"}, indent=2))
        return 0 if summary["pass"] else 1
    finally:
        try:
            env.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
