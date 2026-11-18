# ################################
# VLN adapt: shared observation sequences (no GT aiming)
# ################################
"""Both camera modes start from the same arm joints + optical pose.

fixed_base_gimbal: arm frozen; LOOK_DOWN via simulated gimbal pitch.
arm_view (disk: arm_ee): base fixed; arm joints moved via probe_arm_motion.

Sequences are instance-agnostic — do not read target XYZ for aiming.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

import numpy as np

from src.constants import ARM_APEXNAV_INIT
from src.camera_modes import apply_gimbal_look, activate_camera_mode
from src.execution_collision import probe_arm_motion

# Shared init for both modes (gripper / arm home of ApexNav).
ARM_INIT = tuple(float(x) for x in ARM_APEXNAV_INIT)

# Arm-view waypoints relative to ARM_INIT (joint deltas, rad).
# view_00: init
# view_01: raise + look down (shoulder/elbow/wrist)
# view_02: lateral yaw of base joint + slight look
ARM_DELTAS = (
    (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    (0.0, 0.35, -0.45, 0.0, -0.35, 0.0),  # raise + pitch down
    (0.55, 0.25, -0.35, 0.0, -0.25, 0.0),  # side probe (joint1)
)

# Gimbal: init, look up, look down — use pitch both ways (tabletop-friendly).
GIMBAL_LOOKS = ("hold", "up", "down")


def arm_target_from_delta(delta: Sequence[float]) -> List[float]:
    q0 = np.asarray(ARM_INIT, dtype=np.float64)
    d = np.asarray(delta, dtype=np.float64)
    return (q0 + d).tolist()


def reset_arm_init(env) -> None:
    env.set_arm_joints(ARM_INIT)


def activate_fixed_gimbal(env) -> Dict[str, Any]:
    reset_arm_init(env)
    return activate_camera_mode(env, "fixed_base_gimbal", freeze_arm=True)


def activate_arm_view(env) -> Dict[str, Any]:
    """Use raw FK optical frame (legacy_arm_look) so EE moves with the arm."""
    reset_arm_init(env)
    # Clear any frozen mount from a prior mode.
    env.camera_mode = "legacy_arm_look"
    env.simulated_gimbal = False
    env.fixed_cam_pos_base = None
    env.fixed_cam_rot_base = None
    env.gimbal_pitch = 0.0
    return {
        "camera_mode": "arm_view",
        "disk_mode": "arm_ee",
        "simulated_gimbal": False,
        "arm_baseline": list(ARM_INIT),
        "note": "arm_view uses FK optical frame; joints moved by probe_arm_motion",
    }


def run_gimbal_step(env, step_name: str) -> Dict[str, Any]:
    if step_name == "hold":
        return {
            "executed": True,
            "blocked": False,
            "truncated": False,
            "block_reason": None,
            "action": "hold_init",
            "gimbal_pitch_after": float(getattr(env, "gimbal_pitch", 0.0)),
        }
    meta = apply_gimbal_look(env, "up" if step_name == "up" else "down")
    meta["action"] = f"gimbal_look_{step_name}"
    return meta


def run_arm_step(env, delta: Sequence[float], *, action: str) -> Dict[str, Any]:
    q1 = arm_target_from_delta(delta)
    if np.allclose(delta, 0.0):
        reset_arm_init(env)
        return {
            "executed": True,
            "blocked": False,
            "truncated": False,
            "block_reason": None,
            "action": action,
            "arm_q_after": list(env.arm_q),
            "target_arm_q": q1,
        }
    meta = probe_arm_motion(env, q1, action_hint=action)
    meta["action"] = action
    meta["target_arm_q"] = q1
    meta["arm_q_after"] = list(env.arm_q)
    return meta


def optical_pose_dict(env) -> Dict[str, Any]:
    T = env.camera_world_matrix()
    return {
        "translation_world": [
            float(T.translation.x),
            float(T.translation.y),
            float(T.translation.z),
        ],
        "matrix4_column_major": _mat4_list(T),
        "forward_hab": env.camera_forward_hab().tolist(),
        "gimbal_pitch_rad": float(getattr(env, "gimbal_pitch", 0.0)),
        "arm_q": [float(x) for x in env.arm_q],
        "camera_mode_env": str(getattr(env, "camera_mode", "")),
        "simulated_gimbal": bool(getattr(env, "simulated_gimbal", False)),
    }


def _mat4_list(m) -> List[float]:
    out = []
    for c in range(4):
        for r in range(4):
            out.append(float(m[c][r]))
    return out


def base_pose_dict(env) -> Dict[str, float]:
    return {
        "x": float(env.base_xyz[0]),
        "y": float(env.base_xyz[1]),
        "z": float(env.base_xyz[2]),
        "yaw": float(env.base_yaw),
        "floor_y": float(getattr(env, "floor_y", 0.0)),
    }
