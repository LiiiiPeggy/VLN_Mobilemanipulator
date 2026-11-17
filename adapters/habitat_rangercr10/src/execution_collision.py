"""Kinematic motion collision adjudication for Ranger Habitat execution.

################################
Simulation-only gate: rejects/truncates kinematic teleports that put the robot
into the scene. Does NOT feed scene geometry or goal GT to the planner.
Wheel–floor support contacts are allowed; robot–environment contacts are not.
Discrete sampling can miss obstacles thinner than the sample step.

v1.2: save start / first_blocking / committed contact evidence on reject;
      tighten wheel-support (require upright normal; vs_stage alone is not enough).
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
EXECUTOR_VERSION = "kinematic_collision_v1.2"

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
# Cap detailed contact records per query (logs stay bounded).
MAX_CONTACT_DETAILS = 12


@dataclass
class ContactClassCounts:
    wheel_support: int = 0
    robot_env: int = 0
    self_collision: int = 0
    other: int = 0
    total: int = 0
    robot_env_links: List[str] = field(default_factory=list)
    min_robot_env_distance: Optional[float] = None
    # ################################
    # VLN adapt: per-contact evidence for audits (not fed to planner).
    # ################################
    details: List[Dict[str, Any]] = field(default_factory=list)

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
            "details": list(self.details),
        }


def _link_name(env, link_id: int) -> str:
    for name, lid in env.link_ids.items():
        if int(lid) == int(link_id):
            return str(name)
    return f"link_{int(link_id)}"


def _object_label(env, object_id: int) -> str:
    """Best-effort scene object name; never required for adjudication."""
    oid = int(object_id)
    if oid in STAGE_OBJECT_IDS:
        return "stage_static"
    try:
        rom = env.sim.get_rigid_object_manager()
        if rom.get_library_has_id(oid):
            return str(rom.get_object_handle_by_id(oid))
    except Exception:
        pass
    try:
        names = getattr(env.sim, "semantic_scene", None)
        if names is not None:
            return f"object_id_{oid}"
    except Exception:
        pass
    return f"object_id_{oid}"


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
        other_name = _object_label(env, other_id)
        # ################################
        # Wheel–floor support: require upright normal. vs_stage alone must NOT
        # reclassify low side hits (wall foot / furniture side / step riser) as
        # support. Stage + upright + near_floor + shallow = floor support.
        # ################################
        is_support = bool(is_wheel and near_floor and shallow and upright)
        kind = "wheel_support" if is_support else "robot_env"
        if is_support:
            out.wheel_support += 1
        else:
            out.robot_env += 1
            out.robot_env_links.append(name)
            if out.min_robot_env_distance is None or dist < out.min_robot_env_distance:
                out.min_robot_env_distance = dist
        if len(out.details) < MAX_CONTACT_DETAILS:
            out.details.append(
                {
                    "kind": kind,
                    "robot_link": name,
                    "other_object_id": int(other_id),
                    "other_object": other_name,
                    "vs_stage": bool(vs_stage),
                    "position_xyz": [float(pos[0]), float(pos[1]), float(pos[2])],
                    "normal_on_b_xyz": [float(n[i]) if n.shape[0] > i else 0.0 for i in range(3)],
                    "normal_y_abs": float(n_y),
                    "distance": float(dist),
                    "near_floor": bool(near_floor),
                    "upright": bool(upright),
                    "shallow": bool(shallow),
                    "is_wheel": bool(is_wheel),
                }
            )
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


def _pose_dict(x: float, z: float, yaw: float) -> Dict[str, float]:
    return {"x": float(x), "z": float(z), "yaw": float(yaw)}


def _blocking_evidence(
    *,
    start_contacts: Dict[str, Any],
    first_blocking_contacts: Optional[Dict[str, Any]],
    committed_contacts: Dict[str, Any],
    blocked_sample: Optional[int],
    candidate_pose: Dict[str, float],
    action_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Bundle start / first_blocking / committed contacts for failed probes."""
    return {
        "start_contacts": start_contacts,
        "first_blocking_contacts": first_blocking_contacts,
        "committed_contacts": committed_contacts,
        "blocked_sample": blocked_sample,
        "candidate_pose": candidate_pose,
        "action_hint": action_hint,
    }


def probe_base_motion(
    env,
    x1: float,
    z1: float,
    yaw1: float,
    *,
    trans_step_m: float = DEFAULT_TRANS_STEP_M,
    yaw_step_rad: float = DEFAULT_YAW_STEP_RAD,
    action_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Try base SE(2) motion with intermediate samples; commit last clear pose.

    Probe vs commit: on failure restores the pre-call snapshot. Does not publish
    observations. On reject/truncate, contacts are split into start /
    first_blocking / committed (committed may equal start on full reject).
    """
    snap = snapshot_state(env)
    x0, y0, z0 = float(snap["base_xyz"][0]), float(snap["base_xyz"][1]), float(snap["base_xyz"][2])
    yaw0 = float(snap["base_yaw"])
    floor_y = float(snap["floor_y"])
    start_contacts = query_blocking(env)
    candidate = _pose_dict(x1, z1, yaw1)

    dx, dz = float(x1) - x0, float(z1) - z0
    dist = math.hypot(dx, dz)
    dyaw = (float(yaw1) - yaw0 + math.pi) % (2.0 * math.pi) - math.pi
    n_trans = max(1, int(math.ceil(dist / max(trans_step_m, 1e-6)))) if dist > 1e-9 else 0
    n_yaw = max(1, int(math.ceil(abs(dyaw) / max(yaw_step_rad, 1e-6)))) if abs(dyaw) > 1e-9 else 0
    n = max(n_trans, n_yaw, 1)

    last_valid = (x0, z0, yaw0)
    last_diag = start_contacts
    blocked_at = None
    first_blocking = None
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
            # ################################
            # Capture contacts AT the first blocking sample before restore.
            # ################################
            first_blocking = diag
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
            "start_contacts": start_contacts,
            "first_blocking_contacts": None,
            "committed_contacts": last_diag,
            "blocking_evidence": _blocking_evidence(
                start_contacts=start_contacts,
                first_blocking_contacts=None,
                committed_contacts=last_diag,
                blocked_sample=None,
                candidate_pose=candidate,
                action_hint=action_hint,
            ),
            "samples_preview": samples[:3] + samples[-2:],
            "executor_version": EXECUTOR_VERSION,
        }

    # Restore then commit last valid (may equal start → full reject)
    restore_state(env, snap)
    if last_valid == (x0, z0, yaw0):
        committed = start_contacts
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
            # ################################
            # Legacy key: prefer first_blocking (true reject evidence), not start.
            # ################################
            "contacts": first_blocking if first_blocking is not None else start_contacts,
            "start_contacts": start_contacts,
            "first_blocking_contacts": first_blocking,
            "committed_contacts": committed,
            "blocking_evidence": _blocking_evidence(
                start_contacts=start_contacts,
                first_blocking_contacts=first_blocking,
                committed_contacts=committed,
                blocked_sample=blocked_at,
                candidate_pose=candidate,
                action_hint=action_hint,
            ),
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
        "contacts": first_blocking if first_blocking is not None else commit_diag,
        "start_contacts": start_contacts,
        "first_blocking_contacts": first_blocking,
        "committed_contacts": commit_diag,
        "blocking_evidence": _blocking_evidence(
            start_contacts=start_contacts,
            first_blocking_contacts=first_blocking,
            committed_contacts=commit_diag,
            blocked_sample=blocked_at,
            candidate_pose=candidate,
            action_hint=action_hint,
        ),
        "blocked_sample": blocked_at,
        "samples_preview": samples[:5],
        "executor_version": EXECUTOR_VERSION,
    }


def probe_arm_motion(
    env,
    q1: Sequence[float],
    *,
    n_samples: int = DEFAULT_ARM_SAMPLES,
    action_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Interpolate arm joints; reject if any intermediate has robot–env collision."""
    snap = snapshot_state(env)
    q0 = np.array(snap["arm_q"], dtype=np.float64)
    q1 = np.asarray(q1, dtype=np.float64)
    assert q1.shape == (6,)
    n = max(1, int(n_samples))
    start_contacts = query_blocking(env)
    last_valid_q = q0.copy()
    last_diag = start_contacts
    blocked_at = None
    first_blocking = None
    for i in range(1, n + 1):
        t = i / float(n)
        qi = (1.0 - t) * q0 + t * q1
        env.set_arm_joints(qi)
        diag = query_blocking(env)
        if diag["blocking"]:
            blocked_at = i
            first_blocking = diag
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
            "start_contacts": start_contacts,
            "first_blocking_contacts": None,
            "committed_contacts": last_diag,
            "blocking_evidence": _blocking_evidence(
                start_contacts=start_contacts,
                first_blocking_contacts=None,
                committed_contacts=last_diag,
                blocked_sample=None,
                candidate_pose={"arm_q": q1.tolist()},
                action_hint=action_hint,
            ),
            "executor_version": EXECUTOR_VERSION,
        }

    restore_state(env, snap)
    if np.allclose(last_valid_q, q0):
        committed = start_contacts
        return {
            "ok": False,
            "truncated": False,
            "executed": False,
            "blocked": True,
            "block_reason": "arm_robot_env_collision",
            "n_samples": n,
            "contacts": first_blocking if first_blocking is not None else start_contacts,
            "start_contacts": start_contacts,
            "first_blocking_contacts": first_blocking,
            "committed_contacts": committed,
            "blocking_evidence": _blocking_evidence(
                start_contacts=start_contacts,
                first_blocking_contacts=first_blocking,
                committed_contacts=committed,
                blocked_sample=blocked_at,
                candidate_pose={"arm_q": q1.tolist()},
                action_hint=action_hint,
            ),
            "blocked_sample": blocked_at,
            "executor_version": EXECUTOR_VERSION,
        }
    env.set_arm_joints(last_valid_q)
    commit_diag = query_blocking(env)
    return {
        "ok": True,
        "truncated": True,
        "executed": True,
        "blocked": True,
        "block_reason": "arm_truncated_at_robot_env_collision",
        "n_samples": n,
        "contacts": first_blocking if first_blocking is not None else commit_diag,
        "start_contacts": start_contacts,
        "first_blocking_contacts": first_blocking,
        "committed_contacts": commit_diag,
        "blocking_evidence": _blocking_evidence(
            start_contacts=start_contacts,
            first_blocking_contacts=first_blocking,
            committed_contacts=commit_diag,
            blocked_sample=blocked_at,
            candidate_pose={"arm_q": q1.tolist()},
            action_hint=action_hint,
        ),
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
        "spawn_status": (
            "invalid_initial_penetration" if diag["blocking"] else "ok"
        ),
        "note": (
            "Initial penetration is reported separately and is NOT a legal motion "
            "baseline. Do not enlarge contact tolerance to clear invalid spawns."
        ),
    }
