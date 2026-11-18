# ################################
# VLN adapt: table-edge spawn for Ranger (offline GT used only for placement)
# ################################
"""Search navigable SE(2) poses facing an object AABB center.

Observation actions must NOT use this GT for aiming — spawn only.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from src.constants import ARM_APEXNAV_INIT
from src.execution_collision import report_initial_penetration
from src.spawn_utils import probe_pose_clearance


def _yaw_face_xz(from_xz: Tuple[float, float], to_xz: Tuple[float, float]) -> float:
    # Habitat forward = (sin yaw, cos yaw) in xz (see kinematic_demo)
    dx = float(to_xz[0] - from_xz[0])
    dz = float(to_xz[1] - from_xz[1])
    return math.atan2(dx, dz)


def _ee_target_pixels(env, semantic_id: Optional[int]) -> int:
    """GT visibility probe for spawn ranking only (not for observation aiming)."""
    if semantic_id is None or not getattr(env, "enable_semantic", False):
        return -1
    try:
        obs = env.observe_ee_only()
        sem = obs.get("ee_semantic")
        if sem is None:
            return -1
        return int((sem.astype(np.int64) == int(semantic_id)).sum())
    except Exception:
        return -1


def find_table_edge_spawn(
    env,
    obj_center: Sequence[float],
    *,
    radii_m: Sequence[float] = (1.4, 1.8, 2.3),
    n_angles: int = 12,
    arm_q: Optional[Sequence[float]] = None,
    semantic_id: Optional[int] = None,
    min_visible_pixels: int = 80,
) -> Dict[str, Any]:
    """Return best clearance pose facing the object, with contact evidence.

    When ``semantic_id`` is set, rank by EE semantic visibility (placement only).
    """
    if arm_q is None:
        arm_q = ARM_APEXNAV_INIT
    cx, cy, cz = float(obj_center[0]), float(obj_center[1]), float(obj_center[2])
    pf = env.sim.pathfinder
    candidates: List[Dict[str, Any]] = []

    for r in radii_m:
        for k in range(n_angles):
            ang = 2.0 * math.pi * k / n_angles
            x = cx + r * math.cos(ang)
            z = cz + r * math.sin(ang)
            if pf is None or not pf.is_loaded:
                continue
            # Snap near object height first (multi-floor), then refine floor.
            snapped = pf.snap_point(np.array([x, cy, z], dtype=np.float32))
            if snapped is None:
                continue
            sx, sz = float(snapped[0]), float(snapped[2])
            # Reject if snap drifted too far in xz
            if math.hypot(sx - x, sz - z) > 0.45:
                continue
            floor_y = float(snapped[1])
            yaw = _yaw_face_xz((sx, sz), (cx, cz))
            dist = math.hypot(cx - sx, cz - sz)
            try:
                probe = probe_pose_clearance(
                    env, sx, sz, yaw, floor_y=floor_y, arm_q=arm_q
                )
            except Exception as e:
                candidates.append(
                    {
                        "x": sx,
                        "z": sz,
                        "yaw": yaw,
                        "floor_y": floor_y,
                        "dist_xz": dist,
                        "ok": False,
                        "error": str(e),
                    }
                )
                continue
            pen = report_initial_penetration(env)
            entry = {
                **probe,
                "dist_xz": dist,
                "radius_requested": float(r),
                "angle_k": k,
                "initial_penetration": pen,
                "spawn_ok": bool(probe.get("ok")) and not bool(pen.get("initial_penetration")),
                "ee_target_pixels": -1,
            }
            candidates.append(entry)

    ok = [c for c in candidates if c.get("spawn_ok")]
    # ################################
    # Visibility ranking (GT for placement only): evaluate a shortlist first.
    # ################################
    shortlist = sorted(ok, key=lambda c: abs(float(c.get("dist_xz") or 99) - 1.6))[:8]
    if not shortlist:
        shortlist = sorted(
            [c for c in candidates if c.get("ok")],
            key=lambda c: abs(float(c.get("dist_xz") or 99) - 1.6),
        )[:8]
    for c in shortlist:
        env.set_base_pose(
            c["x"],
            c["z"],
            c["yaw"],
            y=float(c["floor_y"]) + float(env.default_base_y),
            floor_y=float(c["floor_y"]),
            snap_wheels=True,
            update_wheel_joints=False,
        )
        env.set_arm_joints(arm_q)
        c["ee_target_pixels"] = int(_ee_target_pixels(env, semantic_id))

    visible_ok = [
        c for c in shortlist if int(c.get("ee_target_pixels") or 0) >= min_visible_pixels
    ]
    pool = visible_ok if visible_ok else (shortlist if shortlist else ok)
    if not pool:
        return {
            "found": False,
            "n_candidates": len(candidates),
            "best": None,
            "candidates_preview": candidates[:8],
        }

    def score(c: Dict[str, Any]) -> Tuple:
        vis = int(c.get("ee_target_pixels") or -1)
        pen = 0 if not c.get("initial_penetration", {}).get("initial_penetration") else 1
        contacts = int(c.get("contacts") or 99)
        dist = float(c.get("dist_xz") or 99)
        return (-vis, pen, contacts, abs(dist - 1.6))

    best = sorted(pool, key=score)[0]
    env.set_base_pose(
        best["x"],
        best["z"],
        best["yaw"],
        y=float(best["floor_y"]) + float(env.default_base_y),
        floor_y=float(best["floor_y"]),
        snap_wheels=True,
        update_wheel_joints=False,
    )
    env.set_arm_joints(arm_q)
    pen = report_initial_penetration(env)
    vis = _ee_target_pixels(env, semantic_id)
    return {
        "found": True,
        "n_candidates": len(candidates),
        "n_ok": len(ok),
        "n_visible_ok": len(visible_ok),
        "best": {
            "x": float(env.base_xyz[0]),
            "y": float(env.base_xyz[1]),
            "z": float(env.base_xyz[2]),
            "yaw": float(env.base_yaw),
            "floor_y": float(env.floor_y),
            "dist_xz": float(best.get("dist_xz") or 0.0),
            "contacts": int(env.contact_count()),
            "ee_target_pixels": int(vis),
            "initial_penetration": pen,
        },
        "selection_score_key": "-ee_pixels,pen,contacts,|dist-1.6|",
    }
