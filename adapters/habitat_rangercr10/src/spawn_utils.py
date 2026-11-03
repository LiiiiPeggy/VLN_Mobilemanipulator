"""Find a collision-aware spawn near an ObjectNav start (adapter Episode, not benchmark)."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from .constants import ARM_APEXNAV_INIT
from .kinematic_demo import DEFAULT_BASE_Y


def probe_pose_clearance(
    env,
    x: float,
    z: float,
    yaw: float,
    floor_y: float,
    arm_q: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Kinematic place + contact count; returns diagnostics (not dynamics)."""
    # ################################
    # Probe with ApexNav arm pose so EE/arm collisions are counted, not just chassis.
    # ################################
    env.set_base_pose(
        x, z, yaw, y=float(floor_y) + DEFAULT_BASE_Y, floor_y=floor_y, snap_wheels=True
    )
    if arm_q is not None:
        env.set_arm_joints(arm_q)
    up = env.upright_diagnostics()
    contacts = int(env.contact_count())
    wheels = env.wheel_link_heights()
    wheel_agl = None
    if wheels:
        wheel_agl = float(np.mean(list(wheels.values())) - float(floor_y))
    return {
        "x": float(env.base_xyz[0]),
        "z": float(env.base_xyz[2]),
        "yaw": yaw,
        "floor_y": floor_y,
        "base_y": float(env.base_xyz[1]),
        "contacts": contacts,
        "upright": up,
        "wheels": wheels,
        "wheel_mean_agl": wheel_agl,
        "ok": bool(
            up.get("up_dot_hab_y", 0) > 0.95
            and (up.get("wheel_y_spread") or 99) < 0.05
            and contacts < 18
            and (wheel_agl is None or abs(wheel_agl - 0.125) < 0.05)
        ),
    }


def find_adapted_start(
    env,
    start_xz: Tuple[float, float],
    yaw: float,
    floor_y: float,
    radius_m: float = 2.5,
    n_ring: int = 10,
    arm_q: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    """Search nearby XY for upright low-contact pose; record offset if moved."""
    if arm_q is None:
        arm_q = ARM_APEXNAV_INIT
    sx, sz = float(start_xz[0]), float(start_xz[1])
    candidates = [(sx, sz)]
    # ################################
    # Coarse rings first (fast); stop on first ok. Full mesh contact is expensive.
    # ################################
    for r in (0.5, 0.8, 1.2, 1.8, 2.5):
        if r > radius_m:
            break
        for k in range(n_ring):
            ang = 2 * math.pi * k / n_ring
            candidates.append((sx + r * math.cos(ang), sz + r * math.sin(ang)))

    best = None
    trials = []
    for x, z in candidates:
        try:
            pf = env.sim.pathfinder
            if pf is not None and pf.is_loaded:
                snapped = pf.snap_point(np.array([x, floor_y + 0.1, z], dtype=np.float32))
                if snapped is not None:
                    # drop if snap moved too far (obstacle / off-mesh)
                    if math.hypot(float(snapped[0] - x), float(snapped[2] - z)) > 0.35:
                        continue
                    x, z = float(snapped[0]), float(snapped[2])
                    # also reject if far from start floor
                    if abs(float(snapped[1]) - floor_y) > 0.35:
                        continue
        except Exception:
            pass
        d = probe_pose_clearance(env, x, z, yaw, floor_y, arm_q=arm_q)
        d["offset_from_episode_m"] = float(math.hypot(d["x"] - sx, d["z"] - sz))
        trials.append(
            {
                "contacts": d["contacts"],
                "ok": d["ok"],
                "offset": d["offset_from_episode_m"],
                "x": d["x"],
                "z": d["z"],
            }
        )
        if d["ok"]:
            best = d
            break
        if best is None or d["contacts"] < best["contacts"]:
            best = d

    assert best is not None
    env.set_base_pose(
        best["x"], best["z"], yaw, y=best["base_y"], floor_y=floor_y, snap_wheels=True
    )
    env.set_arm_joints(arm_q)
    # refresh diagnostics after final place
    best["contacts"] = int(env.contact_count())
    best["upright"] = env.upright_diagnostics()
    best["wheels"] = env.wheel_link_heights()
    best["base_y"] = float(env.base_xyz[1])
    best["adapted_episode"] = best["offset_from_episode_m"] > 0.05
    best["episode_start_xz"] = [sx, sz]
    best["n_trials"] = len(trials)
    best["trial_summary"] = trials[:12]
    best["arm_q_used"] = list(arm_q)
    return best
