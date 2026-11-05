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
        # ################################
        # Ranger+CR10 is much larger than the Habitat ObjectNav agent; Bullet
        # mesh contacts of 20–40 at a tight bedroom start are common. Prefer
        # upright + wheel snap; treat contacts as a soft score, not a hard 18.
        # ################################
        "ok": bool(
            up.get("up_dot_hab_y", 0) > 0.95
            and (up.get("wheel_y_spread") or 99) < 0.05
            and contacts < 40
            and (wheel_agl is None or abs(wheel_agl - 0.125) < 0.05)
        ),
    }


def find_adapted_start(
    env,
    start_xz: Tuple[float, float],
    yaw: float,
    floor_y: float,
    radius_m: float = 4.0,
    n_ring: int = 12,
    arm_q: Optional[Sequence[float]] = None,
    prefer_open_clearance: bool = True,
) -> Dict[str, Any]:
    """Search nearby XY for upright low-contact pose; prefer open clearance for Ranger.

    ################################
    Exact ObjectNav starts can be contact-OK yet leave ApexNav with no A* path to
    frontiers (tight alcoves). When prefer_open_clearance, score ok candidates by
    PathFinder.distance_to_closest_obstacle (GT offline spawn only — not planner GT).
    ################################
    """
    if arm_q is None:
        arm_q = ARM_APEXNAV_INIT
    sx, sz = float(start_xz[0]), float(start_xz[1])
    candidates = [(sx, sz)]
    for r in (0.5, 0.8, 1.2, 1.8, 2.5, 3.2, 4.0):
        if r > radius_m:
            break
        for k in range(n_ring):
            ang = 2 * math.pi * k / n_ring
            candidates.append((sx + r * math.cos(ang), sz + r * math.sin(ang)))

    def _nav_clearance(x: float, z: float) -> float:
        try:
            import magnum as mn

            pf = env.sim.pathfinder
            if pf is None or not pf.is_loaded:
                return 0.0
            p = mn.Vector3(float(x), float(floor_y) + 0.1, float(z))
            if not pf.is_navigable(p):
                p = pf.snap_point(p)
            return float(pf.distance_to_closest_obstacle(p))
        except Exception:
            return 0.0

    ok_pool = []
    best_fallback = None
    trials = []
    for x, z in candidates:
        try:
            pf = env.sim.pathfinder
            if pf is not None and pf.is_loaded:
                snapped = pf.snap_point(np.array([x, floor_y + 0.1, z], dtype=np.float32))
                if snapped is not None:
                    if math.hypot(float(snapped[0] - x), float(snapped[2] - z)) > 0.35:
                        continue
                    x, z = float(snapped[0]), float(snapped[2])
                    if abs(float(snapped[1]) - floor_y) > 0.35:
                        continue
        except Exception:
            pass
        d = probe_pose_clearance(env, x, z, yaw, floor_y, arm_q=arm_q)
        d["offset_from_episode_m"] = float(math.hypot(d["x"] - sx, d["z"] - sz))
        d["nav_clearance_m"] = _nav_clearance(d["x"], d["z"])
        trials.append(
            {
                "contacts": d["contacts"],
                "ok": d["ok"],
                "offset": d["offset_from_episode_m"],
                "nav_clearance_m": d["nav_clearance_m"],
                "x": d["x"],
                "z": d["z"],
            }
        )
        if d["ok"]:
            ok_pool.append(d)
            # Legacy fast-path: accept first ok if not optimizing openness
            if not prefer_open_clearance:
                break
        if best_fallback is None or d["contacts"] < best_fallback["contacts"]:
            best_fallback = d

    if ok_pool and prefer_open_clearance:
        # ################################
        # Keep near the ObjectNav start (≤1.5 m): maximizing clearance alone can
        # walk into empty atria where lookaround yields no coverable frontiers.
        # Target clearance band ~[0.35, 0.90] m (above Habitat 0.18, below void).
        # ################################
        near = [d for d in ok_pool if float(d["offset_from_episode_m"]) <= 1.5] or ok_pool

        def _score(d):
            clr = float(d.get("nav_clearance_m") or 0.0)
            # triangular preference peaking at 0.55 m
            band = 1.0 - min(abs(clr - 0.55) / 0.55, 1.0)
            return (
                -band,
                int(d["contacts"]),
                float(d["offset_from_episode_m"]),
            )

        near.sort(key=_score)
        best = near[0]
    else:
        best = ok_pool[0] if ok_pool else best_fallback

    assert best is not None
    env.set_base_pose(
        best["x"], best["z"], yaw, y=best["base_y"], floor_y=floor_y, snap_wheels=True
    )
    env.set_arm_joints(arm_q)
    best["contacts"] = int(env.contact_count())
    best["upright"] = env.upright_diagnostics()
    best["wheels"] = env.wheel_link_heights()
    best["base_y"] = float(env.base_xyz[1])
    best["adapted_episode"] = best["offset_from_episode_m"] > 0.05
    best["episode_start_xz"] = [sx, sz]
    best["n_trials"] = len(trials)
    best["trial_summary"] = trials[:16]
    best["arm_q_used"] = list(arm_q)
    best["spawn_policy"] = "prefer_open_clearance" if prefer_open_clearance else "first_ok"
    return best
