"""Initial D455 pose for ApexNav-compatible ObjectNav (adapter layer).

Target (ApexNav fixed-camera convention):
  - optical-center height ≈ 0.88 m above Habitat scene ground (y-up)
  - optical +Z horizontal, aligned with base forward (sin yaw, 0, cos yaw)
  - pitch ≈ 0°, roll ≈ 0°

Pose MUST come from URDF joint state + FK (``camera_world_matrix``), never by
forging Habitat Agent sensor pose independently of the articulated robot.

``ARM_DEFAULT`` / ``ARM_APEXNAV_INIT`` follow LocoManip stage-4.10d home
(D455 top-mounted on AG95; MuJoCo optical/link AGL ≈0.88 m, Habitat FK ≈0.857 m).
Do not height-chase with unnatural joints; ``ARM_APEXNAV_INIT_SEARCH`` is diagnostics only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from .constants import (
    ARM_APEXNAV_INIT,
    ARM_DEFAULT,
    ARM_JOINT_NAMES,
    APEXNAV_CAM_HEIGHT_M,
    APEXNAV_CAM_HEIGHT_TOL_M,
    APEXNAV_CAM_ANGLE_TOL_DEG,
)
from .kinematic_demo import DEFAULT_BASE_Y

WORLD_UP = np.array([0.0, 1.0, 0.0], dtype=np.float64)


def optical_metrics(env, base_yaw: float) -> Dict[str, Any]:
    """FK metrics of ``d455_depth_optical_frame`` in Habitat y-up world.

    ``height_m`` / ``height_agl_m`` are optical-center height **above local floor**,
    where floor_y := base_link_y - DEFAULT_BASE_Y (wheel contact / navmesh floor).
    """
    T = env.camera_world_matrix()
    p = np.array(
        [T.translation.x, T.translation.y, T.translation.z], dtype=np.float64
    )
    R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
    # RealSense optical: +Z forward, +X right, +Y down
    fwd = R[:, 2]
    right = R[:, 0]
    # Prefer env.floor_y (navmesh); fall back to base_y - DEFAULT_BASE_Y only as legacy
    floor_y = float(getattr(env, "floor_y", float(env.base_xyz[1]) - float(DEFAULT_BASE_Y)))
    height_agl = float(p[1]) - floor_y
    pitch = math.asin(float(np.clip(fwd[1], -1.0, 1.0)))
    fxz = np.array([fwd[0], 0.0, fwd[2]], dtype=np.float64)
    n = float(np.linalg.norm(fxz)) + 1e-12
    fxz /= n
    yaw_err = math.atan2(fxz[0], fxz[2]) - float(base_yaw)
    yaw_err = (yaw_err + math.pi) % (2.0 * math.pi) - math.pi
    roll = math.asin(float(np.clip(np.dot(right, WORLD_UP), -1.0, 1.0)))
    return {
        "pos_hab": p.tolist(),
        "floor_y_hab": floor_y,
        "height_abs_m": float(p[1]),
        "height_m": height_agl,  # AGL — compared to ApexNav 0.88 m
        "height_agl_m": height_agl,
        "optical_fwd_hab": fwd.tolist(),
        "pitch_rad": pitch,
        "pitch_deg": math.degrees(pitch),
        "yaw_err_rad": yaw_err,
        "yaw_err_deg": math.degrees(yaw_err),
        "roll_rad": roll,
        "roll_deg": math.degrees(roll),
        "base_yaw_rad": float(base_yaw),
    }


def within_tolerances(m: Dict[str, Any]) -> Dict[str, bool]:
    h_ok = abs(m["height_m"] - APEXNAV_CAM_HEIGHT_M) <= APEXNAV_CAM_HEIGHT_TOL_M
    ang = APEXNAV_CAM_ANGLE_TOL_DEG
    return {
        "height_ok": h_ok,
        "pitch_ok": abs(m["pitch_deg"]) <= ang,
        "yaw_ok": abs(m["yaw_err_deg"]) <= ang,
        "roll_ok": abs(m["roll_deg"]) <= ang,
        "all_ok": bool(
            h_ok
            and abs(m["pitch_deg"]) <= ang
            and abs(m["yaw_err_deg"]) <= ang
            and abs(m["roll_deg"]) <= ang
        ),
    }


def verify_arm_config(
    env,
    arm_q: Sequence[float],
    *,
    label: str = "candidate",
) -> Dict[str, Any]:
    """Set joints via articulated FK path and verify ApexNav-like camera pose."""
    env.set_arm_joints(arm_q)
    m = optical_metrics(env, env.base_yaw)
    tol = within_tolerances(m)
    limits = env.joint_limits_report()
    contacts = int(env.contact_count())
    return {
        "label": label,
        "arm_q": [float(x) for x in np.asarray(arm_q, dtype=np.float64).tolist()],
        "metrics": m,
        "tolerances": {
            "height_target_m": APEXNAV_CAM_HEIGHT_M,
            "height_tol_m": APEXNAV_CAM_HEIGHT_TOL_M,
            "angle_tol_deg": APEXNAV_CAM_ANGLE_TOL_DEG,
            **tol,
        },
        "joint_limits": limits,
        "contacts_diagnostic": contacts,
        "pose_source": "urdf_fk_d455_depth_optical_frame",
        "forged_render_camera": False,
    }


def choose_initial_arm(env) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Prefer pinned ApexNav init; fall back to search only if pin fails."""
    rep_default = verify_arm_config(env, ARM_DEFAULT, label="ARM_DEFAULT")
    rep_pin = verify_arm_config(env, ARM_APEXNAV_INIT, label="ARM_APEXNAV_INIT")
    report: Dict[str, Any] = {
        "ARM_DEFAULT": rep_default,
        "ARM_APEXNAV_INIT": rep_pin,
        "selected": None,
        "search_used": False,
    }
    if rep_pin["tolerances"]["all_ok"]:
        report["selected"] = "ARM_APEXNAV_INIT"
        env.set_arm_joints(ARM_APEXNAV_INIT)
        report["final"] = rep_pin
        return np.array(ARM_APEXNAV_INIT, dtype=np.float64), report

    # ################################
    # Stage 4.10d: if angles are level and height only slightly off MuJoCo 0.88 m,
    # keep co-pinned ARM_DEFAULT — do NOT height-chase into a self-occluding pose.
    # ################################
    ang_ok = (
        rep_pin["tolerances"]["pitch_ok"]
        and rep_pin["tolerances"]["yaw_ok"]
        and rep_pin["tolerances"]["roll_ok"]
    )
    h = float(rep_pin["metrics"]["height_agl_m"])
    if ang_ok and abs(h - APEXNAV_CAM_HEIGHT_M) <= 0.04:
        report["selected"] = "ARM_APEXNAV_INIT_angle_priority"
        report["angle_priority_note"] = (
            f"height_agl={h:.3f}m vs target 0.88; angles OK; keep stage410d default"
        )
        env.set_arm_joints(ARM_APEXNAV_INIT)
        report["final"] = verify_arm_config(env, ARM_APEXNAV_INIT, label=report["selected"])
        return np.array(ARM_APEXNAV_INIT, dtype=np.float64), report

    # Bounded local refine around pin (no new IK module)
    q, search_rep = _local_refine(env, np.array(ARM_APEXNAV_INIT, dtype=np.float64))
    report["search_used"] = True
    report["search"] = search_rep
    report["selected"] = "search_refined" if search_rep.get("pass") else "best_effort"
    env.set_arm_joints(q)
    report["final"] = verify_arm_config(env, q, label=report["selected"])
    return q, report


def _local_refine(env, q0: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Small random-walk + optional least_squares; adapter-only, not a full IK."""
    lows, highs = env.ao.joint_position_limits
    lims = []
    for jn in ARM_JOINT_NAMES:
        i = env.joint_pos_index[jn]
        lo, hi = float(lows[i]), float(highs[i])
        lims.append(
            (lo if np.isfinite(lo) else -3.0, hi if np.isfinite(hi) else 3.0)
        )
    lo_a = np.array([a[0] for a in lims])
    hi_a = np.array([a[1] for a in lims])
    rng = np.random.default_rng(0)

    def cost(q: np.ndarray) -> Tuple[float, Dict[str, Any]]:
        env.set_arm_joints(q)
        m = optical_metrics(env, env.base_yaw)
        c = (
            5.0 * abs(m["height_m"] - APEXNAV_CAM_HEIGHT_M)
            + 2.0 * abs(m["pitch_rad"])
            + 2.0 * abs(m["yaw_err_rad"])
            + 1.5 * abs(m["roll_rad"])
        )
        return c, m

    best_c, best_m = cost(q0)
    best_q = q0.copy()
    for scale in (0.2, 0.1, 0.05):
        for _ in range(400):
            q = np.clip(best_q + rng.normal(0.0, scale, size=6), lo_a, hi_a)
            c, m = cost(q)
            if c < best_c:
                best_c, best_m, best_q = c, m, q.copy()
                if within_tolerances(best_m)["all_ok"]:
                    break
        if within_tolerances(best_m)["all_ok"]:
            break

    try:
        from scipy.optimize import least_squares

        def resid(q):
            env.set_arm_joints(q)
            m = optical_metrics(env, env.base_yaw)
            return [
                10.0 * (m["height_m"] - APEXNAV_CAM_HEIGHT_M),
                5.0 * m["pitch_rad"],
                5.0 * m["yaw_err_rad"],
                5.0 * m["roll_rad"],
            ]

        sol = least_squares(resid, best_q, bounds=(lo_a, hi_a), max_nfev=200)
        c, m = cost(sol.x)
        if c < best_c:
            best_c, best_m, best_q = c, m, sol.x.copy()
    except Exception as e:
        best_m = {**best_m, "scipy_error": str(e)}

    tol = within_tolerances(best_m)
    return best_q, {
        "pass": tol["all_ok"],
        "q": best_q.tolist(),
        "metrics": best_m,
        "tolerances": tol,
        "cost": best_c,
    }


def apply_and_record_initial_camera(
    env,
    out_dir: Path,
    *,
    save_rgb: bool = True,
) -> Dict[str, Any]:
    """Select init arm, verify FK pose, optionally dump first RGB-D."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    q, report = choose_initial_arm(env)
    final = verify_arm_config(env, q, label=report["selected"])
    report["final"] = final
    if save_rgb:
        obs = env.observe_ee_only()
        Image.fromarray(obs["ee_rgb"][..., :3]).save(out_dir / "init_rgb_ee.png")
        depth = obs["ee_depth"]
        d = np.asarray(depth)
        if d.ndim == 3:
            d = d[..., 0]
        # uint16 mm for quick inspection
        mm = np.clip(d * 1000.0, 0, 65535).astype(np.uint16)
        Image.fromarray(mm).save(out_dir / "init_depth_ee_mm.png")
        report["init_rgb"] = str(out_dir / "init_rgb_ee.png")
        report["init_depth"] = str(out_dir / "init_depth_ee_mm.png")
        report["init_ee_T_note"] = "FK optical frame; Habitat sensor uses +180deg X for -Z look"
    (out_dir / "initial_camera_pose.json").write_text(json.dumps(report, indent=2))
    if not final["tolerances"]["all_ok"]:
        # Do not forge; record deviation and continue with best FK pose.
        report["warning"] = (
            "Initial camera FK outside ApexNav 0.88m/0deg tolerances; "
            "using best URDF FK pose without forging render camera."
        )
        (out_dir / "initial_camera_pose.json").write_text(json.dumps(report, indent=2))
    return report
