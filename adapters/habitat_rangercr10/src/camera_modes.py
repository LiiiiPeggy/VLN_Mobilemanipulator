"""Camera deployment modes for Ranger↔ApexNav / VLFM adapter.

################################
Modes:
  - fixed_base: optical pose fixed in base frame (pos+orientation). For VLFM-like.
  - fixed_base_gimbal: optical *position* fixed in base; pitch via simulated gimbal.
    ApexNav primary baseline this round. Tag simulated_gimbal=True — not a real pan-tilt.
  - legacy_arm_look: historical joint3 LOOK (moves optical center). Old-result only.
################################
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

import magnum as mn
import numpy as np

from .constants import ARM_APEXNAV_INIT, EE_RGB_HFOV_DEG, EE_RGB_RES

CAMERA_MODE_FIXED_BASE = "fixed_base"
CAMERA_MODE_FIXED_BASE_GIMBAL = "fixed_base_gimbal"
CAMERA_MODE_LEGACY_ARM_LOOK = "legacy_arm_look"
CAMERA_MODES = (
    CAMERA_MODE_FIXED_BASE,
    CAMERA_MODE_FIXED_BASE_GIMBAL,
    CAMERA_MODE_LEGACY_ARM_LOOK,
)

# ApexNav LOOK step (±30°) and soft optical pitch clamp for simulated gimbal.
GIMBAL_PITCH_STEP_RAD = math.pi / 6.0
GIMBAL_PITCH_LIMIT_RAD = math.pi / 2.0 - 0.05


def _mat4_to_list(m: mn.Matrix4):
    out = []
    for c in range(4):
        for r in range(4):
            out.append(float(m[c][r]))
    return out


def _np_to_mat4(T: np.ndarray) -> mn.Matrix4:
    T = np.asarray(T, dtype=np.float64).reshape(4, 4)
    cols = [mn.Vector4(float(T[0, c]), float(T[1, c]), float(T[2, c]), float(T[3, c])) for c in range(4)]
    return mn.Matrix4((*cols,))


def optical_in_base(env) -> Dict[str, Any]:
    """FK optical pose expressed in current base frame."""
    T_wb = env._base_matrix()
    T_wc = env.camera_world_matrix_fk()
    T_bw = T_wb.inverted()
    T_bc = T_bw @ T_wc
    p = T_bc.translation
    R = np.array(T_bc.rotation(), dtype=np.float64).reshape(3, 3)
    # Optical +Z forward in optical frame
    fwd = R[:, 2]
    pitch = math.asin(float(np.clip(fwd[1], -1.0, 1.0)))
    return {
        "pos_base": [float(p.x), float(p.y), float(p.z)],
        "pitch_rad": float(pitch),
        "T_base_cam": _mat4_to_list(T_bc),
    }


def activate_camera_mode(env, mode: str, *, freeze_arm: bool = True) -> Dict[str, Any]:
    """Configure env camera_mode after arm baseline is set.

    For fixed_* modes, freezes optical center in base frame from current FK and
    holds arm at current joints (expected ARM_APEXNAV_INIT). Gimbal pitch starts
    at current optical pitch so LOOK deltas remain ApexNav-sized.
    """
    mode = str(mode)
    if mode not in CAMERA_MODES:
        raise ValueError(f"unknown camera_mode={mode}; expected {CAMERA_MODES}")
    env.camera_mode = mode
    env.simulated_gimbal = mode == CAMERA_MODE_FIXED_BASE_GIMBAL
    meta: Dict[str, Any] = {
        "camera_mode": mode,
        "simulated_gimbal": bool(env.simulated_gimbal),
        "arm_baseline": [float(x) for x in env.arm_q],
        "hfov_deg": EE_RGB_HFOV_DEG,
        "resolution_hw": list(EE_RGB_RES),
    }
    if mode == CAMERA_MODE_LEGACY_ARM_LOOK:
        env.fixed_cam_pos_base = None
        env.fixed_cam_rot_base = None
        env.gimbal_pitch = 0.0
        meta["note"] = "legacy joint3 LOOK; optical center moves with arm"
        return meta

    info = optical_in_base(env)
    env.fixed_cam_pos_base = np.array(info["pos_base"], dtype=np.float64)
    # Store full base←cam rotation at activation (includes current pitch).
    T_bc = env._base_matrix().inverted() @ env.camera_world_matrix_fk()
    env.fixed_cam_rot_base = np.array(T_bc.rotation(), dtype=np.float64).reshape(3, 3)
    # Gimbal pitch is an *additional* pitch about optical +X (right), starting at 0
    # relative to the frozen orientation (which already has init pitch≈0).
    env.gimbal_pitch = 0.0
    env.gimbal_pitch_limit = GIMBAL_PITCH_LIMIT_RAD
    env.gimbal_pitch_step = GIMBAL_PITCH_STEP_RAD
    if freeze_arm:
        env.arm_q = np.array(env.arm_q, dtype=np.float64).copy()
        env._apply_state()
    # Sanity: optical not inside chassis roughly (z_base / height)
    pb = env.fixed_cam_pos_base
    meta.update(
        {
            "fixed_cam_pos_base_m": pb.tolist(),
            "init_optical_pitch_rad": info["pitch_rad"],
            "gimbal_pitch_step_rad": GIMBAL_PITCH_STEP_RAD,
            "gimbal_pitch_limit_rad": GIMBAL_PITCH_LIMIT_RAD,
            "warning_cam_inside_body": bool(pb[0] < 0.05 and abs(pb[1]) < 0.15),
            "note": (
                "LOOK changes orientation only; arm joints frozen. "
                "simulated_gimbal — not a physical pan-tilt unit."
                if env.simulated_gimbal
                else "fully fixed relative to base"
            ),
        }
    )
    return meta


def apply_gimbal_look(env, direction: str) -> Dict[str, Any]:
    """LOOK_UP / LOOK_DOWN for fixed_base_gimbal. No arm motion."""
    if getattr(env, "camera_mode", CAMERA_MODE_LEGACY_ARM_LOOK) != CAMERA_MODE_FIXED_BASE_GIMBAL:
        raise RuntimeError("apply_gimbal_look requires fixed_base_gimbal")
    step = float(getattr(env, "gimbal_pitch_step", GIMBAL_PITCH_STEP_RAD))
    lim = float(getattr(env, "gimbal_pitch_limit", GIMBAL_PITCH_LIMIT_RAD))
    before = float(env.gimbal_pitch)
    delta = step if direction == "up" else -step
    after = float(np.clip(before + delta, -lim, lim))
    env.gimbal_pitch = after
    # Position must stay fixed in base
    pos_before = env.fixed_cam_pos_base.copy()
    T = env.camera_world_matrix()
    # Re-extract pos in base
    T_bc = env._base_matrix().inverted() @ T
    pos_after = np.array(
        [T_bc.translation.x, T_bc.translation.y, T_bc.translation.z], dtype=np.float64
    )
    drift = float(np.linalg.norm(pos_after - pos_before))
    return {
        "executed": abs(after - before) > 1e-9,
        "blocked": abs(after - before) <= 1e-9 and abs(delta) > 1e-9,
        "block_reason": "gimbal_pitch_limit" if abs(after - before) <= 1e-9 else None,
        "gimbal_pitch_before": before,
        "gimbal_pitch_after": after,
        "pitch_delta_rad": after - before,
        "optical_pos_base_drift_m": drift,
        "look_equivalence": "simulated_gimbal_pitch",
        "simulated_gimbal": True,
    }


def compose_fixed_camera_world(env) -> mn.Matrix4:
    """World optical matrix from frozen base-frame mount + optional gimbal pitch."""
    T_wb = env._base_matrix()
    pos = env.fixed_cam_pos_base
    R0 = env.fixed_cam_rot_base
    # Build Matrix4 for base←cam at freeze
    T_bc = mn.Matrix4.from_(
        mn.Matrix3x3(
            mn.Vector3(float(R0[0, 0]), float(R0[1, 0]), float(R0[2, 0])),
            mn.Vector3(float(R0[0, 1]), float(R0[1, 1]), float(R0[2, 1])),
            mn.Vector3(float(R0[0, 2]), float(R0[1, 2]), float(R0[2, 2])),
        ),
        mn.Vector3(float(pos[0]), float(pos[1]), float(pos[2])),
    )
    mode = getattr(env, "camera_mode", CAMERA_MODE_LEGACY_ARM_LOOK)
    if mode == CAMERA_MODE_FIXED_BASE_GIMBAL:
        pitch = float(getattr(env, "gimbal_pitch", 0.0))
        # Pitch about optical +X (right): Rx(pitch) in camera frame
        T_bc = T_bc @ mn.Matrix4.rotation_x(mn.Rad(pitch))
    return T_wb @ T_bc


def camera_mode_summary(env) -> Dict[str, Any]:
    mode = getattr(env, "camera_mode", CAMERA_MODE_LEGACY_ARM_LOOK)
    out: Dict[str, Any] = {
        "camera_mode": mode,
        "simulated_gimbal": bool(getattr(env, "simulated_gimbal", False)),
        "gimbal_pitch_rad": float(getattr(env, "gimbal_pitch", 0.0)),
        "arm_q": [float(x) for x in env.arm_q],
        "arm_is_apexnav_init": bool(
            np.allclose(env.arm_q, np.asarray(ARM_APEXNAV_INIT, dtype=np.float64), atol=1e-3)
        ),
    }
    if getattr(env, "fixed_cam_pos_base", None) is not None:
        out["fixed_cam_pos_base_m"] = np.asarray(env.fixed_cam_pos_base).tolist()
        T = env.camera_world_matrix()
        out["optical_pos_world"] = [
            float(T.translation.x),
            float(T.translation.y),
            float(T.translation.z),
        ]
    return out
