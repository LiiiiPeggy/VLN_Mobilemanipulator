"""Lookaround FOV / coverage / passability diagnostics (adapter-only).

################################
Offline + mapping-only diagnostics. Does NOT change ApexNav planner, scale,
PPO, depth-validity policy, or inflation. GT navmesh is diagnosis-only.
################################
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw

# ################################
# Canonical square-pixel K from Habitat HFOV=79° @640×480 (fx=fy).
# Legacy launch fy=422.05 (HFOV×H/W) is NOT independent "measured" FOV.
# ################################
from .camera_model import REF_K_640x480_HFOV79, legacy_broken_fy_from_hfov_aspect, pinhole_from_hfov

APEXNAV_FX = float(REF_K_640x480_HFOV79["fx"])
APEXNAV_FY = float(REF_K_640x480_HFOV79["fy"])
APEXNAV_CX = float(REF_K_640x480_HFOV79["cx"])
APEXNAV_CY = float(REF_K_640x480_HFOV79["cy"])
APEXNAV_W = 640
APEXNAV_H = 480


def fov_from_intrinsics(
    fx: float = APEXNAV_FX,
    fy: float = APEXNAV_FY,
    width: int = APEXNAV_W,
    height: int = APEXNAV_H,
) -> Dict[str, float]:
    if abs(fx - fy) < 1e-6 and abs(fx - APEXNAV_FX) < 1e-3:
        k = pinhole_from_hfov(width, height, 79.0)
        k["source"] = "camera_model.pinhole_from_hfov (Habitat HFOV, square pixels)"
        k["legacy_wrong_fy"] = legacy_broken_fy_from_hfov_aspect(width, height, 79.0)
        return k
    hfov = 2.0 * math.atan(width / (2.0 * fx))
    vfov = 2.0 * math.atan(height / (2.0 * fy))
    return {
        "fx": float(fx),
        "fy": float(fy),
        "cx": float(APEXNAV_CX),
        "cy": float(APEXNAV_CY),
        "width": int(width),
        "height": int(height),
        "hfov_rad": float(hfov),
        "vfov_rad": float(vfov),
        "hfov_deg": float(math.degrees(hfov)),
        "vfov_deg": float(math.degrees(vfov)),
        "source": "explicit fx/fy (not assumed Habitat HFOV)",
    }


def quat_xyzw_to_rpy(q: Sequence[float]) -> Tuple[float, float, float]:
    """ROS camera_q xyzw → roll, pitch, yaw (radians), ZYX."""
    x, y, z, w = [float(v) for v in q]
    # roll (x)
    sinr = 2.0 * (w * x + y * z)
    cosr = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr, cosr)
    # pitch (y)
    sinp = 2.0 * (w * y - z * x)
    sinp = max(-1.0, min(1.0, sinp))
    pitch = math.asin(sinp)
    # yaw (z)
    siny = 2.0 * (w * z + x * y)
    cosy = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny, cosy)
    return roll, pitch, yaw


def wrap_pi(a: float) -> float:
    while a > math.pi:
        a -= 2.0 * math.pi
    while a < -math.pi:
        a += 2.0 * math.pi
    return a


def horizontal_overlap_deg(hfov_deg: float, yaw_step_deg: float) -> Dict[str, float]:
    ov = float(hfov_deg) - float(yaw_step_deg)
    return {
        "hfov_deg": float(hfov_deg),
        "yaw_step_deg": float(yaw_step_deg),
        "overlap_deg": float(ov),
        "overlap_frac_of_hfov": float(ov / max(hfov_deg, 1e-6)),
        "gap_if_negative_deg": float(max(0.0, -ov)),
    }


def analyze_episode_lookaround(run_dir: Path) -> Dict[str, Any]:
    """Extract per-frame camera / yaw / map stats from a finished apexnav_real run."""
    run_dir = Path(run_dir)
    steps = [
        json.loads(l)
        for l in (run_dir / "steps.jsonl").read_text().splitlines()
        if l.strip()
    ]
    acts = [
        json.loads(l)
        for l in (run_dir / "actions.jsonl").read_text().splitlines()
        if l.strip()
    ]
    fov = fov_from_intrinsics()
    rows: List[Dict[str, Any]] = []
    for i, s in enumerate(steps):
        meta = s.get("publish_meta") or {}
        act = acts[i] if i < len(acts) else {}
        cam_q = meta.get("camera_q_xyzw")
        rpy = quat_xyzw_to_rpy(cam_q) if cam_q and len(cam_q) == 4 else (None, None, None)
        dv = meta.get("depth_validity") or {}
        row = {
            "step": int(s.get("step", i)),
            "phase": s.get("phase") or act.get("phase"),
            "action": s.get("planner_action_name") or act.get("name"),
            "t_action": act.get("t"),
            "stamp_ros": meta.get("stamp"),
            "base_yaw_hab": float((s.get("base") or {}).get("yaw", meta.get("base_yaw_hab") or 0.0)),
            "base_yaw_ros": meta.get("base_yaw_ros"),
            "camera_ros": meta.get("camera_ros"),
            "camera_roll_rad": rpy[0],
            "camera_pitch_rad": rpy[1],
            "camera_yaw_rad": rpy[2],
            "camera_roll_deg": None if rpy[0] is None else math.degrees(rpy[0]),
            "camera_pitch_deg": None if rpy[1] is None else math.degrees(rpy[1]),
            "camera_yaw_deg": None if rpy[2] is None else math.degrees(rpy[2]),
            "depth_validity": dv,
            "frac_nan_published": dv.get("frac_nan_published"),
            "frac_self_hit": dv.get("frac_self_hit"),
            "map_stats": s.get("map_stats"),
            "itm_cosine": s.get("itm_cosine"),
        }
        rows.append(row)

    # Adjacent yaw deltas (prefer camera optical yaw; fallback base)
    deltas = []
    for i in range(1, len(rows)):
        y0 = rows[i - 1]["camera_yaw_rad"]
        y1 = rows[i]["camera_yaw_rad"]
        if y0 is None or y1 is None:
            y0 = rows[i - 1]["base_yaw_hab"]
            y1 = rows[i]["base_yaw_hab"]
        dy = wrap_pi(float(y1) - float(y0))
        pitch0 = rows[i - 1]["camera_pitch_rad"]
        pitch1 = rows[i]["camera_pitch_rad"]
        dp = None if pitch0 is None or pitch1 is None else float(pitch1) - float(pitch0)
        step_deg = abs(math.degrees(dy))
        ov = horizontal_overlap_deg(fov["hfov_deg"], step_deg)
        deltas.append(
            {
                "from_step": rows[i - 1]["step"],
                "to_step": rows[i]["step"],
                "action": rows[i]["action"],
                "phase": rows[i]["phase"],
                "dyaw_rad": dy,
                "dyaw_deg": math.degrees(dy),
                "dpitch_deg": None if dp is None else math.degrees(dp),
                **ov,
            }
        )

    look = [r for r in rows if r.get("phase") == "init_lookaround"]
    turn_deltas = [
        d
        for d in deltas
        if d.get("action") in ("TURN_LEFT", "TURN_RIGHT") and abs(d["dyaw_deg"]) > 1.0
    ]
    mean_step = (
        float(np.mean([abs(d["dyaw_deg"]) for d in turn_deltas])) if turn_deltas else None
    )

    # Map growth during lookaround
    map_series = []
    for r in look:
        ms = r.get("map_stats") or {}
        map_series.append(
            {
                "step": r["step"],
                "occupied": ms.get("occupied"),
                "free": ms.get("free"),
                "unknown": ms.get("unknown"),
                "value_map": ms.get("value_map"),
                "frac_nan": r.get("frac_nan_published"),
            }
        )

    return {
        "run_dir": str(run_dir),
        "fov": fov,
        "habitat_ee_hfov_deg_constant": 79.0,
        "apexnav_action_angle_deg": 30.0,
        "n_steps": len(rows),
        "n_lookaround": len(look),
        "mean_turn_yaw_step_deg": mean_step,
        "overlap_at_mean_step": None
        if mean_step is None
        else horizontal_overlap_deg(fov["hfov_deg"], mean_step),
        "overlap_table": {
            str(s): horizontal_overlap_deg(fov["hfov_deg"], s) for s in (15, 20, 30, 45)
        },
        "frames": rows,
        "deltas": deltas,
        "map_series_lookaround": map_series,
        "findings": _findings(fov, mean_step, turn_deltas, look),
    }


def _findings(fov, mean_step, turn_deltas, look) -> List[str]:
    out = []
    out.append(
        f"D455/Habitat FOV from ApexNav fx/fy: H={fov['hfov_deg']:.2f}° V={fov['vfov_deg']:.2f}° "
        f"(matches EE_RGB_HFOV_DEG=79)."
    )
    if mean_step is not None:
        ov = horizontal_overlap_deg(fov["hfov_deg"], mean_step)
        out.append(
            f"Measured lookaround turn step ≈{mean_step:.1f}° → horizontal overlap "
            f"{ov['overlap_deg']:.1f}° ({100*ov['overlap_frac_of_hfov']:.0f}% of HFOV)."
        )
        if ov["overlap_deg"] > 0:
            out.append(
                "Yaw step alone does NOT create horizontal FOV blind wedges; "
                "white radial gaps are mostly unknown between sparse free-ray sectors "
                "and height-filtered occupied endpoints — not missing FOV coverage."
            )
        else:
            out.append("Yaw step exceeds HFOV → true angular blind zones exist.")
    pitches = [
        r["camera_pitch_deg"]
        for r in look
        if r.get("camera_pitch_deg") is not None
    ]
    if pitches:
        out.append(
            f"Camera pitch during lookaround: min={min(pitches):.1f}° max={max(pitches):.1f}° "
            f"(TURN_DOWN/UP change optical pitch via arm FK)."
        )
    return out


def render_coverage_rose(
    diag: Dict[str, Any],
    out_png: Path,
    size: int = 480,
) -> None:
    """Polar sketch: each lookaround camera yaw as a FOV wedge."""
    fov = diag["fov"]
    hfov = math.radians(fov["hfov_deg"])
    frames = [f for f in diag["frames"] if f.get("phase") == "init_lookaround"]
    img = Image.new("RGB", (size, size), (255, 255, 255))
    dr = ImageDraw.Draw(img, "RGBA")
    cx = cy = size // 2
    R = size // 2 - 20
    # wedges
    for f in frames:
        yaw = f.get("camera_yaw_rad")
        if yaw is None:
            continue
        # Image angle: 0 = +x right, CCW; ROS yaw 0 = +x
        a0 = -yaw - hfov / 2
        a1 = -yaw + hfov / 2
        # approximate wedge as polygon
        pts = [(cx, cy)]
        for k in range(17):
            a = a0 + (a1 - a0) * k / 16.0
            pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
        dr.polygon(pts, fill=(255, 180, 120, 35), outline=(220, 100, 40, 90))
    dr.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(30, 100, 220))
    dr.text((8, 8), f"HFOV={fov['hfov_deg']:.1f}° lookaround wedges", fill=(0, 0, 0))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)


def angular_occupancy_hist(
    occ_xy: np.ndarray, center_xy: Sequence[float], n_bins: int = 36
) -> Dict[str, Any]:
    if occ_xy is None or len(occ_xy) == 0:
        return {"n": 0, "hist": [0] * n_bins}
    c = np.asarray(center_xy, dtype=np.float64)
    ang = np.arctan2(occ_xy[:, 1] - c[1], occ_xy[:, 0] - c[0])
    hist, edges = np.histogram(ang, bins=n_bins, range=(-math.pi, math.pi))
    return {
        "n": int(len(occ_xy)),
        "hist": hist.tolist(),
        "edges": edges.tolist(),
        "peakiness": float(hist.max() / (hist.mean() + 1e-9)),
        "zero_bins": int((hist == 0).sum()),
    }


def gt_false_occupied_probe(
    env,
    occ_xy_ros: np.ndarray,
    floor_y: float,
    robot_xy_ros: Sequence[float],
    max_pts: int = 400,
) -> Dict[str, Any]:
    """Diagnosis-only navmesh proximity audit for occupied cells.

    ################################
    GT pathfinder must NEVER feed the planner.
    NOT a precise false-occupied rate: reports raw query navigability,
    horizontal snap distance, and fraction of cells with snap_xy < 0.35 m
    that land on navigable space (neighborhood evidence only).
    ################################
    """
    if occ_xy_ros is None or len(occ_xy_ros) == 0:
        return {
            "n_tested": 0,
            "metric_name": "occ_navmesh_neighborhood_audit",
            "precise_false_occupied_rate": None,
        }
    pf = env.sim.pathfinder
    pts = np.asarray(occ_xy_ros, dtype=np.float64)
    if len(pts) > max_pts:
        idx = np.linspace(0, len(pts) - 1, max_pts).astype(int)
        pts = pts[idx]
    snap_dists: List[float] = []
    n_query_nav = 0
    n_snap_ok = 0
    n_near_nav = 0
    n_fail = 0
    for x_ros, y_ros in pts:
        hab_x = -float(y_ros)
        hab_z = -float(x_ros)
        p = np.array([hab_x, float(floor_y) + 0.15, hab_z], dtype=np.float32)
        try:
            raw_nav = bool(pf.is_navigable(p))
            if raw_nav:
                n_query_nav += 1
            snapped = pf.snap_point(p)
            if snapped is None or np.any(np.isnan(snapped)):
                n_fail += 1
                continue
            n_snap_ok += 1
            dxy = math.hypot(float(snapped[0]) - hab_x, float(snapped[2]) - hab_z)
            dz = abs(float(snapped[1]) - float(p[1]))
            snap_dists.append(dxy)
            if dxy < 0.35 and pf.is_navigable(snapped):
                n_near_nav += 1
        except Exception:
            n_fail += 1
            continue
    near_rate = None if n_snap_ok == 0 else float(n_near_nav) / float(n_snap_ok)
    return {
        "metric_name": "occ_navmesh_neighborhood_audit",
        "n_tested": int(len(pts)),
        "n_query_navigable_raw": int(n_query_nav),
        "n_snap_ok": int(n_snap_ok),
        "n_query_fail": int(n_fail),
        "n_snap_xy_lt_0p35_and_nav": int(n_near_nav),
        "frac_near_navmesh_lt_0p35": near_rate,
        "snap_xy_m_mean": float(np.mean(snap_dists)) if snap_dists else None,
        "snap_xy_m_median": float(np.median(snap_dists)) if snap_dists else None,
        "precise_false_occupied_rate": None,
        "false_occupied_rate_est": near_rate,  # legacy key; NOT precise FO rate
        "note": (
            "GT diagnosis only. frac_near_navmesh_lt_0p35 means occupied cells "
            "have a navigable snap within 0.35 m — neighborhood evidence, NOT "
            "precise false-occupied rate. Never injected into planner."
        ),
    }


def summarize_passability(first_plan_diag: Dict[str, Any]) -> Dict[str, Any]:
    counts = first_plan_diag.get("counts") or {}
    return {
        "base_cell_state": first_plan_diag.get("base_cell_state"),
        "free_component_from_start": first_plan_diag.get("free_component_from_start"),
        "frontier_seed_cells": first_plan_diag.get("frontier_seed_cells"),
        "frontier_clusters": first_plan_diag.get("frontier_clusters"),
        "astar_trials_n": first_plan_diag.get("astar_trials_n"),
        "astar_ok_n": first_plan_diag.get("astar_ok_n"),
        "occupied_pts": counts.get("occupied_pts") or counts.get("occ_voxels"),
        "free_pts": counts.get("free_pts") or counts.get("free_voxels"),
        "unknown_pts": counts.get("unknown_pts") or counts.get("unk_voxels"),
        "inflate_pts": counts.get("inflate_pts") or counts.get("inflate_voxels"),
        "hypothesis": first_plan_diag.get("hypothesis"),
    }
