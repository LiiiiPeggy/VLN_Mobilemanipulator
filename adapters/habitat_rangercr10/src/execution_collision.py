"""Kinematic motion collision adjudication for Ranger Habitat execution.

################################
Simulation-only gate: rejects/truncates kinematic teleports that put the robot
into the scene. Does NOT feed scene geometry or goal GT to the planner.
Wheel–floor support contacts are allowed; robot–environment contacts are not.
Discrete sampling can miss obstacles thinner than the sample step.
################################
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

# ################################
# Executor protocol version (reported in summary / Cursor B handoff).
# ################################
EXECUTOR_VERSION = "kinematic_collision_v1.1"

WHEEL_LINK_NAMES = frozenset(
    {"fr_wheel_link", "fl_wheel_link", "rl_wheel_link", "rr_wheel_link"}
)

# Discrete sample defaults (meters / radians). Documented limitations apply.
DEFAULT_TRANS_STEP_M = 0.05
DEFAULT_YAW_STEP_RAD = math.radians(5.0)
DEFAULT_ARM_SAMPLES = 8
# Penetration deeper than this on a support contact is still allowed (resting).
SUPPORT_MAX_PENETRATION_M = 0.05
# Contact height band relative to floor for wheel support (× wheel radius).
SUPPORT_HEIGHT_BAND_FACTOR = 1.8
SUPPORT_NORMAL_Y_MIN = 0.45
# Stage / static mesh object_id in Habitat is typically 0.
STAGE_OBJECT_IDS = frozenset({0, -1})


@dataclass
class ContactClassCounts:
    wheel_support: int = 0
    robot_env: int = 0
    self_collision: int = 0
    other: int = 0
    total: int = 0
    robot_env_links: List[str] = field(default_factory=list)
    min_robot_env_distance: Optional[float] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "wheel_support": self.wheel_support,
            "robot_env": self.robot_env,
            "self_collision": self.self_collision,
            "other": self.other,
            "total": self.total,
            "robot_env_links": sorted(set(self.robot_env_links)),
            "min_robot_env_distance": self.min_robot_env_distance,
            "blocking": self.robot_env > 0,
        }


def _link_name(env, link_id: int) -> str:
    for name, lid in env.link_ids.items():
        if int(lid) == int(link_id):
            return str(name)
    return f"link_{int(link_id)}"


def classify_contacts(env) -> ContactClassCounts:
    """Classify Bullet contacts after perform_discrete_collision_detection()."""
    env.sim.perform_discrete_collision_detection()
    cps = env.sim.get_physics_contact_points()
    rid = int(env.ao.object_id)
    floor_y = float(getattr(env, "floor_y", float(env.base_xyz[1]) - env.default_base_y))
    wheel_r = float(getattr(env, "wheel_radius_snap", 0.125))
    # ################################
    # Tire contact points often sit a few cm below navmesh floor_y under kinematic
    # snap; keep a generous lower band so wheels are not labeled robot_env.
    # ################################
    height_lo = floor_y - max(0.06, 0.75 * wheel_r)
    height_hi = floor_y + SUPPORT_HEIGHT_BAND_FACTOR * wheel_r
    out = ContactClassCounts(total=len(cps))
    for c in cps:
        a, b = int(c.object_id_a), int(c.object_id_b)
        if a == rid and b == rid:
            out.self_collision += 1
            continue
        if rid not in (a, b):
            out.other += 1
            continue
        # Robot link id on the robot side
        link_id = int(c.link_id_a) if a == rid else int(c.link_id_b)
        name = _link_name(env, link_id)
        pos = c.position_on_a_in_ws if a == rid else c.position_on_b_in_ws
        py = float(pos[1])
        # Normal on B in world; for support we want mostly vertical.
        n = np.asarray(c.contact_normal_on_b_in_ws, dtype=np.float64)
        n_y = abs(float(n[1])) if n.shape[0] >= 2 else 0.0
        dist = float(c.contact_distance)
        is_wheel = name in WHEEL_LINK_NAMES
        near_floor = height_lo <= py <= height_hi
        upright = n_y >= SUPPORT_NORMAL_Y_MIN
        shallow = dist >= -SUPPORT_MAX_PENETRATION_M
        other_id = b if a == rid else a
        vs_stage = int(other_id) in STAGE_OBJECT_IDS
        # ################################
        # Wheel–floor / wheel–stage near the tire plane counts as support even if
        # the contact normal is slightly tilted (kinematic rest penetration).
        # ################################
        if is_wheel and near_floor and shallow and (upright or vs_stage):
            out.wheel_support += 1
            continue
        out.robot_env += 1
        out.robot_env_links.append(name)
        if out.min_robot_env_distance is None or dist < out.min_robot_env_distance:
            out.min_robot_env_distance = dist
    return out


def query_blocking(env) -> Dict[str, Any]:
    """Return contact classification + contact_test (diagnostic only)."""
    counts = classify_contacts(env)
    d = counts.as_dict()
    d["contact_test_raw"] = bool(env.sim.contact_test(int(env.ao.object_id)))
    d["note"] = (
        "contact_test_raw is True whenever any contact exists (incl. wheel support); "
        "do NOT treat contact_test_raw==False as clear, or True as blocking."
    )
    return d


def snapshot_state(env) -> Dict[str, Any]:
    return {
        "base_xyz": np.array(env.base_xyz, dtype=np.float64).copy(),
        "base_yaw": float(env.base_yaw),
        "arm_q": np.array(env.arm_q, dtype=np.float64).copy(),
        "steer_q": np.array(env.steer_q, dtype=np.float64).copy(),
        "wheel_q": np.array(env.wheel_q, dtype=np.float64).copy(),
        "prev_base_xz_yaw": None
        if env._prev_base_xz_yaw is None
        else tuple(float(x) for x in env._prev_base_xz_yaw),
        "floor_y": float(getattr(env, "floor_y", 0.0)),
        "gimbal_pitch": float(getattr(env, "gimbal_pitch", 0.0)),
    }


def restore_state(env, snap: Dict[str, Any], apply: bool = True) -> None:
    env.base_xyz[:] = snap["base_xyz"]
    env.base_yaw = float(snap["base_yaw"])
    env.arm_q = np.array(snap["arm_q"], dtype=np.float64).copy()
    env.steer_q = np.array(snap["steer_q"], dtype=np.float64).copy()
    env.wheel_q = np.array(snap["wheel_q"], dtype=np.float64).copy()
    env._prev_base_xz_yaw = snap["prev_base_xz_yaw"]
    env.floor_y = float(snap["floor_y"])
    if hasattr(env, "gimbal_pitch"):
        env.gimbal_pitch = float(snap.get("gimbal_pitch", 0.0))
    if apply:
        env._apply_state()


def _place_base(env, x: float, z: float, yaw: float, y: float, floor_y: float) -> None:
    env.set_base_pose(
        float(x),
        float(z),
        float(yaw),
        y=float(y),
        floor_y=float(floor_y),
        snap_wheels=False,
        update_wheel_joints=True,
    )


def probe_base_motion(
    env,
    x1: float,
    z1: float,
    yaw1: float,
    *,
    trans_step_m: float = DEFAULT_TRANS_STEP_M,
    yaw_step_rad: float = DEFAULT_YAW_STEP_RAD,
) -> Dict[str, Any]:
    """Try base SE(2) motion with intermediate samples; commit last clear pose.

    Probe vs commit: on failure restores the pre-call snapshot. Does not publish
    observations.
    """
    snap = snapshot_state(env)
    x0, y0, z0 = float(snap["base_xyz"][0]), float(snap["base_xyz"][1]), float(snap["base_xyz"][2])
    yaw0 = float(snap["base_yaw"])
    floor_y = float(snap["floor_y"])

    dx, dz = float(x1) - x0, float(z1) - z0
    dist = math.hypot(dx, dz)
    dyaw = (float(yaw1) - yaw0 + math.pi) % (2.0 * math.pi) - math.pi
    n_trans = max(1, int(math.ceil(dist / max(trans_step_m, 1e-6)))) if dist > 1e-9 else 0
    n_yaw = max(1, int(math.ceil(abs(dyaw) / max(yaw_step_rad, 1e-6)))) if abs(dyaw) > 1e-9 else 0
    n = max(n_trans, n_yaw, 1)

    last_valid = (x0, z0, yaw0)
    last_diag = query_blocking(env)
    blocked_at = None
    samples: List[Dict[str, Any]] = []
    for i in range(1, n + 1):
        t = i / float(n)
        xi = x0 + t * dx
        zi = z0 + t * dz
        yawi = yaw0 + t * dyaw
        _place_base(env, xi, zi, yawi, y0, floor_y)
        diag = query_blocking(env)
        samples.append(
            {
                "i": i,
                "t": t,
                "x": xi,
                "z": zi,
                "yaw": yawi,
                "blocking": diag["blocking"],
                "robot_env": diag["robot_env"],
            }
        )
        if diag["blocking"]:
            blocked_at = i
            break
        last_valid = (xi, zi, yawi)
        last_diag = diag

    if blocked_at is None:
        # Full motion clear — already at goal
        return {
            "ok": True,
            "truncated": False,
            "executed": True,
            "blocked": False,
            "block_reason": None,
            "n_samples": n,
            "trans_step_m": trans_step_m,
            "yaw_step_rad": yaw_step_rad,
            "moved_m": math.hypot(last_valid[0] - x0, last_valid[1] - z0),
            "yaw_delta": (last_valid[2] - yaw0 + math.pi) % (2.0 * math.pi) - math.pi,
            "contacts": last_diag,
            "samples_preview": samples[:3] + samples[-2:],
            "executor_version": EXECUTOR_VERSION,
        }

    # Restore then commit last valid (may equal start → full reject)
    restore_state(env, snap)
    if last_valid == (x0, z0, yaw0):
        return {
            "ok": False,
            "truncated": False,
            "executed": False,
            "blocked": True,
            "block_reason": "robot_env_collision",
            "n_samples": n,
            "trans_step_m": trans_step_m,
            "yaw_step_rad": yaw_step_rad,
            "moved_m": 0.0,
            "yaw_delta": 0.0,
            "contacts": last_diag if blocked_at == 1 else query_blocking(env),
            "blocked_sample": blocked_at,
            "samples_preview": samples[:5],
            "executor_version": EXECUTOR_VERSION,
        }

    _place_base(env, last_valid[0], last_valid[1], last_valid[2], y0, floor_y)
    commit_diag = query_blocking(env)
    return {
        "ok": True,
        "truncated": True,
        "executed": True,
        "blocked": True,
        "block_reason": "truncated_at_robot_env_collision",
        "n_samples": n,
        "trans_step_m": trans_step_m,
        "yaw_step_rad": yaw_step_rad,
        "moved_m": math.hypot(last_valid[0] - x0, last_valid[1] - z0),
        "yaw_delta": (last_valid[2] - yaw0 + math.pi) % (2.0 * math.pi) - math.pi,
        "contacts": commit_diag,
        "blocked_sample": blocked_at,
        "samples_preview": samples[:5],
        "executor_version": EXECUTOR_VERSION,
    }


def probe_arm_motion(
    env,
    q1: Sequence[float],
    *,
    n_samples: int = DEFAULT_ARM_SAMPLES,
) -> Dict[str, Any]:
    """Interpolate arm joints; reject if any intermediate has robot–env collision."""
    snap = snapshot_state(env)
    q0 = np.array(snap["arm_q"], dtype=np.float64)
    q1 = np.asarray(q1, dtype=np.float64)
    assert q1.shape == (6,)
    n = max(1, int(n_samples))
    last_valid_q = q0.copy()
    last_diag = query_blocking(env)
    blocked_at = None
    for i in range(1, n + 1):
        t = i / float(n)
        qi = (1.0 - t) * q0 + t * q1
        env.set_arm_joints(qi)
        diag = query_blocking(env)
        if diag["blocking"]:
            blocked_at = i
            break
        last_valid_q = qi.copy()
        last_diag = diag

    if blocked_at is None:
        return {
            "ok": True,
            "truncated": False,
            "executed": True,
            "blocked": False,
            "block_reason": None,
            "n_samples": n,
            "contacts": last_diag,
            "executor_version": EXECUTOR_VERSION,
        }

    restore_state(env, snap)
    if np.allclose(last_valid_q, q0):
        return {
            "ok": False,
            "truncated": False,
            "executed": False,
            "blocked": True,
            "block_reason": "arm_robot_env_collision",
            "n_samples": n,
            "contacts": last_diag,
            "blocked_sample": blocked_at,
            "executor_version": EXECUTOR_VERSION,
        }
    env.set_arm_joints(last_valid_q)
    return {
        "ok": True,
        "truncated": True,
        "executed": True,
        "blocked": True,
        "block_reason": "arm_truncated_at_robot_env_collision",
        "n_samples": n,
        "contacts": query_blocking(env),
        "blocked_sample": blocked_at,
        "executor_version": EXECUTOR_VERSION,
    }


def report_initial_penetration(env) -> Dict[str, Any]:
    """Call once after spawn/camera init; not used as a motion baseline."""
    diag = query_blocking(env)
    return {
        "initial_penetration": bool(diag["blocking"]),
        "contacts": diag,
        "executor_version": EXECUTOR_VERSION,
        "note": "Initial penetration is reported separately and is NOT a legal motion baseline.",
    }
