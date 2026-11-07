#!/usr/bin/env python3
"""HY1 startup observation pose — geometric feasibility search (offline).

Does NOT change default deploy, ground gates, inflation, unknown, A*.
Does NOT force FREE or inject GT into the online map.
Scene GT used only for Habitat visibility / contact queries.

Run in vln-rangercr10:
  export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:$PYTHONPATH
  python .../hy1_startup_pose_geometry_search.py
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from src.camera_model import pinhole_from_hfov, project_optical, unproject_optical
from src.coord_habitat_ros import (
    hab_optical_rot_to_ros,
    hab_pos_to_ros,
    hab_yaw_to_ros,
    mat4_hab_optical_to_ros_pose,
)
from src.depth_validity import prepare_depth_for_apexnav
from src.kinematic_demo import RangerCr10KinematicEnv
from src.ppo_mujoco_raise import apply_raise_to_habitat
from src.robot_scale import footprint_at_scale

# Production gates (observe / mirror only)
FILTER_MIN = 0.28
FILTER_MAX = 1.18
VIRTUAL_GROUND = -0.34
GROUND_FREE_MAX_AGL = 0.03
PLANAR_R = 0.12
PLANAR_Z_TOL = 0.02
PLANAR_MIN_N = 5
VOXEL_XY = 0.04
VOXEL_Z = 0.1
OUTLIER_GROUND_R = 0.25
OUTLIER_GROUND_MIN = 8

SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d_v0.2/val/"
    "00894-HY1NcmCgn3n/HY1NcmCgn3n.basis.glb"
)
JOINT_LIMITS = [
    (-3.92, 0.94),
    (-1.57, 1.57),
    (-2.86, 2.86),
    (-3.14, 3.14),
    (-3.14, 3.14),
    (-3.14, 3.14),
]


def _mat4_np(T) -> np.ndarray:
    if hasattr(T, "rotation"):
        R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
        p = np.array(
            [T.translation.x, T.translation.y, T.translation.z], dtype=np.float64
        )
        M = np.eye(4)
        M[:3, :3] = R
        M[:3, 3] = p
        return M
    return np.asarray(T, dtype=np.float64).reshape(4, 4)


def clip_q(q: np.ndarray) -> np.ndarray:
    out = q.astype(np.float64).copy()
    for i, (lo, hi) in enumerate(JOINT_LIMITS):
        out[i] = float(np.clip(out[i], lo, hi))
    return out


def voxel_downsample(pts: np.ndarray, leaf_xy: float, leaf_z: float) -> np.ndarray:
    if len(pts) == 0:
        return pts
    keys = np.stack(
        [
            np.floor(pts[:, 0] / leaf_xy).astype(np.int64),
            np.floor(pts[:, 1] / leaf_xy).astype(np.int64),
            np.floor(pts[:, 2] / leaf_z).astype(np.int64),
        ],
        axis=1,
    )
    _, idx = np.unique(keys, axis=0, return_index=True)
    return pts[np.sort(idx)]


def is_planar(cloud: np.ndarray, idx: int) -> bool:
    p = cloud[idx]
    r2 = PLANAR_R * PLANAR_R
    n_ok = 0
    for j in range(len(cloud)):
        if j == idx:
            continue
        q = cloud[j]
        if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > r2:
            continue
        if abs(p[2] - q[2]) <= PLANAR_Z_TOL:
            n_ok += 1
            if n_ok >= PLANAR_MIN_N:
                return True
    return False


def radius_outlier(cloud: np.ndarray, radius: float, min_n: int) -> np.ndarray:
    if len(cloud) == 0:
        return cloud
    keep = []
    r2 = radius * radius
    for i, p in enumerate(cloud):
        n = 0
        for j, q in enumerate(cloud):
            if i == j:
                continue
            if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 <= r2:
                n += 1
                if n >= min_n:
                    keep.append(i)
                    break
    return cloud[keep] if keep else cloud[:0]


@dataclass
class ZoneDef:
    """Geometric zones — exterior observation ≠ diagnostic rings."""

    robot_scale: float
    half_l: float
    half_w: float
    safety_gap_m: float = 0.05
    exterior_band_m: float = 0.35
    corridor_length_m: float = 0.80
    corridor_side_clear_m: float = 0.05
    note: str = (
        "0–0.3 / 0.3–0.6 m rings remain diagnostic only; "
        "acceptance uses exterior band + startup corridor."
    )


def body_frame_rect_mask(
    pts_xy: np.ndarray, chassis_xy: np.ndarray, yaw_ros: float, half_l: float, half_w: float
) -> np.ndarray:
    """True if point is inside oriented chassis rectangle (ROS XY)."""
    # ROS forward = +X of body after yaw: R = [[c,-s],[s,c]] maps body→world
    c, s = math.cos(yaw_ros), math.sin(yaw_ros)
    d = pts_xy - chassis_xy.reshape(1, 2)
    # world → body: R^T
    bx = c * d[:, 0] + s * d[:, 1]
    by = -s * d[:, 0] + c * d[:, 1]
    return (np.abs(bx) <= half_l) & (np.abs(by) <= half_w)


def sample_zone_points(
    chassis_xy: np.ndarray,
    yaw_ros: float,
    zd: ZoneDef,
) -> Dict[str, np.ndarray]:
    """Return ground samples (ROS XY,z=0) for exterior / corridor / occluded / rings."""
    c, s = math.cos(yaw_ros), math.sin(yaw_ros)
    # body→world
    def bw(bx, by):
        return np.array(
            [chassis_xy[0] + c * bx - s * by, chassis_xy[1] + s * bx + c * by, 0.0]
        )

    exterior = []
    # Forward exterior strip (beyond front bumper)
    x0 = zd.half_l + zd.safety_gap_m
    x1 = x0 + zd.exterior_band_m
    for bx in np.linspace(x0, x1, 8):
        for by in np.linspace(-(zd.half_w + zd.exterior_band_m), zd.half_w + zd.exterior_band_m, 14):
            # exclude deep under-body
            if abs(by) < zd.half_w + zd.safety_gap_m and bx < zd.half_l + zd.safety_gap_m:
                continue
            exterior.append(bw(bx, by))
    # Side strips along length
    for bx in np.linspace(-zd.half_l, zd.half_l + zd.exterior_band_m, 12):
        for side in (-1.0, 1.0):
            for extra in np.linspace(zd.safety_gap_m, zd.exterior_band_m, 5):
                by = side * (zd.half_w + extra)
                exterior.append(bw(bx, by))

    corridor = []
    half_corr_w = zd.half_w + zd.corridor_side_clear_m
    for bx in np.linspace(x0, x0 + zd.corridor_length_m, 12):
        for by in np.linspace(-half_corr_w, half_corr_w, 9):
            corridor.append(bw(bx, by))

    occluded = []
    for bx in np.linspace(-zd.half_l, zd.half_l, 10):
        for by in np.linspace(-zd.half_w, zd.half_w, 8):
            occluded.append(bw(bx, by))

    rings = {"r0_0p3": [], "r0p3_0p6": []}
    for name, (r0, r1) in (("r0_0p3", (0.0, 0.3)), ("r0p3_0p6", (0.3, 0.6))):
        for r in np.linspace(r0 + 0.03, r1 - 0.03, 5):
            for th in np.linspace(0, 2 * math.pi, 24, endpoint=False):
                rings[name].append(
                    [
                        chassis_xy[0] + r * math.cos(th),
                        chassis_xy[1] + r * math.sin(th),
                        0.0,
                    ]
                )

    return {
        "exterior": np.asarray(exterior, dtype=np.float64),
        "corridor": np.asarray(corridor, dtype=np.float64),
        "occluded_body": np.asarray(occluded, dtype=np.float64),
        "r0_0p3": np.asarray(rings["r0_0p3"], dtype=np.float64),
        "r0p3_0p6": np.asarray(rings["r0p3_0p6"], dtype=np.float64),
    }


def project_coverage(
    pts: np.ndarray,
    cam_p: np.ndarray,
    R_ros: np.ndarray,
    K: Dict[str, float],
    w: int,
    h: int,
) -> Dict[str, Any]:
    if len(pts) == 0:
        return {"n": 0, "n_in_front": 0, "n_in_fov": 0, "frac_in_fov": 0.0}
    d = pts - cam_p.reshape(1, 3)
    p_cam = (R_ros.T @ d.T).T
    in_front = p_cam[:, 2] > 0.15  # usable depth along optical
    n_fov = 0
    for i in np.where(in_front)[0]:
        u, v = project_optical(p_cam[i], K)
        if 0 <= u < w and 0 <= v < h:
            n_fov += 1
    return {
        "n": int(len(pts)),
        "n_in_front": int(in_front.sum()),
        "n_in_fov": int(n_fov),
        "frac_in_fov": float(n_fov / max(len(pts), 1)),
    }


def fk_score(
    env,
    q: np.ndarray,
    zones: Dict[str, np.ndarray],
    K: Dict[str, float],
    w: int,
    h: int,
    baseline_contacts: int,
    contact_slack: int = 8,
) -> Dict[str, Any]:
    q = clip_q(q)
    env.set_arm_joints(q)
    contacts = int(env.contact_count())
    cam_T = env.camera_world_matrix()
    cam_M = _mat4_np(cam_T)
    floor_y = float(env.floor_y)
    cam_p, cam_quat = mat4_hab_optical_to_ros_pose(cam_T, floor_y=floor_y)
    R_ros = hab_optical_rot_to_ros(cam_M[:3, :3])
    fwd = R_ros[:, 2]
    reject = None
    if cam_p[2] < 0.22:
        reject = "camera_too_low_agl"
    elif contacts > baseline_contacts + contact_slack:
        reject = "contact_increase"
    elif float(fwd[2]) > -0.15:
        # must look down enough to see near ground (heuristic gate for phase1)
        # still record coverage; may reject later if exterior FOV=0
        pass

    cov = {
        k: project_coverage(zones[k], cam_p, R_ros, K, w, h)
        for k in ("exterior", "corridor", "occluded_body", "r0_0p3", "r0p3_0p6")
    }
    # Prefer exterior/corridor FOV; occluded_body FOV is NOT a goal (through-body)
    score = (
        3.0 * cov["corridor"]["frac_in_fov"]
        + 2.0 * cov["exterior"]["frac_in_fov"]
        + 0.3 * cov["r0p3_0p6"]["frac_in_fov"]
        + 0.15 * cov["r0_0p3"]["frac_in_fov"]
        - 0.5 * max(0.0, float(fwd[2]))  # reward looking down
        - 0.02 * abs(contacts - baseline_contacts)
    )
    if reject:
        score -= 10.0
    return {
        "arm_q": q.astype(float).tolist(),
        "camera_ros_pos_agl": cam_p.astype(float).tolist(),
        "camera_ros_quat_xyzw": cam_quat.astype(float).tolist(),
        "optical_fwd_ros": fwd.astype(float).tolist(),
        "contacts": contacts,
        "contact_delta": contacts - baseline_contacts,
        "reject": reject,
        "coverage": cov,
        "score": float(score),
    }


def depth_eval(
    env,
    q: np.ndarray,
    zones: Dict[str, np.ndarray],
    chassis_xy: np.ndarray,
    yaw_ros: float,
    zd: ZoneDef,
    out_dir: Path,
    tag: str,
) -> Dict[str, Any]:
    q = clip_q(q)
    env.set_arm_joints(q)
    ee = env.observe_ee_only()
    rgb = ee["ee_rgb"][..., :3].copy()
    depth_raw = np.asarray(ee["ee_depth"], dtype=np.float32)
    if depth_raw.ndim == 3:
        depth_raw = depth_raw[..., 0]
    cam_T = env.camera_world_matrix()
    cam_M = _mat4_np(cam_T)
    depth_prep, dstats = prepare_depth_for_apexnav(
        depth_raw,
        env=env,
        camera_T_hab=cam_T,
        depth_min=0.0,
        depth_max=5.0,
        hfov_deg=79.0,
        robot_scale=float(env.robot_scale),
        use_geometric_self_hit=True,
        camera_frame="optical",
    )
    floor_y = float(env.floor_y)
    cam_p, _ = mat4_hab_optical_to_ros_pose(cam_T, floor_y=floor_y)
    R_ros = hab_optical_rot_to_ros(cam_M[:3, :3])
    h, w = depth_raw.shape[:2]
    K = pinhole_from_hfov(w, h, 79.0)
    valid_prep = np.isfinite(depth_prep)
    self_hit = np.isfinite(depth_raw) & np.isnan(depth_prep)

    # Overlay exterior/corridor projections
    canvas = Image.fromarray(rgb.astype(np.uint8).copy())
    draw = ImageDraw.Draw(canvas)
    for name, col in (("exterior", (0, 255, 0)), ("corridor", (255, 200, 0))):
        pts = zones[name]
        d = pts - cam_p.reshape(1, 3)
        p_cam = (R_ros.T @ d.T).T
        for i in range(len(pts)):
            if p_cam[i, 2] <= 0.15:
                continue
            u, v = project_optical(p_cam[i], K)
            if 0 <= u < w and 0 <= v < h:
                ui, vi = int(u), int(v)
                ok = bool(valid_prep[vi, ui]) and (not self_hit[vi, ui])
                r = 3 if ok else 2
                draw.ellipse(
                    [ui - r, vi - r, ui + r, vi + r],
                    outline=col,
                    fill=col if ok else None,
                )
    canvas.save(out_dir / f"{tag}_coverage_overlay.png")
    Image.fromarray(rgb.astype(np.uint8)).save(out_dir / f"{tag}_rgb.png")
    ov = rgb.astype(np.uint8).copy()
    ov[self_hit] = (255, 40, 40)
    Image.fromarray(ov).save(out_dir / f"{tag}_selfhit.png")

    # Unproject → classify → free endpoints
    us, vs = np.meshgrid(np.arange(w), np.arange(h))
    step = 2
    m = valid_prep[::step, ::step]
    uu = us[::step, ::step][m].astype(np.float64)
    vv = vs[::step, ::step][m].astype(np.float64)
    dd = depth_prep[::step, ::step][m].astype(np.float64)
    if len(dd) == 0:
        pts_ros = np.zeros((0, 3))
    else:
        pts_opt = np.stack(
            [unproject_optical(float(uu[i]), float(vv[i]), float(dd[i]), K) for i in range(len(dd))],
            0,
        )
        pts_ros = (R_ros @ pts_opt.T).T + cam_p.reshape(1, 3)

    down = voxel_downsample(pts_ros, VOXEL_XY, VOXEL_Z)
    ground_ok = []
    for i in range(len(down)):
        z = float(down[i, 2])
        if 0.0 <= z <= GROUND_FREE_MAX_AGL and is_planar(down, i):
            ground_ok.append(i)
    ground_pts = down[ground_ok] if ground_ok else down[:0]
    ground_f = radius_outlier(ground_pts, OUTLIER_GROUND_R, OUTLIER_GROUND_MIN)

    # Simulated free cells from free-rays (offline; NOT written to online map)
    res = 0.05
    free_cells = set()
    for p in ground_f:
        a = cam_p[:2]
        b = p[:2]
        for t in np.linspace(0.0, 1.0, 40):
            xy = a + t * (b - a)
            # skip last 1 cell (endpoint neighborhood still free for ground)
            gx = int(round(xy[0] / res))
            gy = int(round(xy[1] / res))
            free_cells.add((gx, gy))

    def zone_free_count(pts: np.ndarray) -> Dict[str, int]:
        n_seen = 0
        n_free = 0
        for p in pts:
            d = p - cam_p
            p_cam = R_ros.T @ d
            if p_cam[2] <= 0.15:
                continue
            u, v = project_optical(p_cam, K)
            if not (0 <= u < w and 0 <= v < h):
                continue
            ui, vi = int(u), int(v)
            if not valid_prep[vi, ui] or self_hit[vi, ui]:
                continue
            n_seen += 1
            gx, gy = int(round(p[0] / res)), int(round(p[1] / res))
            if (gx, gy) in free_cells:
                n_free += 1
        return {"n_with_valid_depth_in_fov": n_seen, "n_in_sim_free": n_free}

    # Corridor connectivity: BFS on free cells along forward corridor bbox
    corr = zones["corridor"]
    if len(corr):
        xs, ys = corr[:, 0], corr[:, 1]
        xmin, xmax, ymin, ymax = xs.min(), xs.max(), ys.min(), ys.max()
    else:
        xmin = xmax = ymin = ymax = 0.0
    start_cell = (
        int(round(chassis_xy[0] / res)),
        int(round(chassis_xy[1] / res)),
    )
    # Start may be under body — seed from free cells nearest front bumper exterior
    front = zones["corridor"][0] if len(zones["corridor"]) else chassis_xy
    seeds = []
    for p in ground_f:
        if body_frame_rect_mask(
            p[:2].reshape(1, 2), chassis_xy, yaw_ros, zd.half_l, zd.half_w
        )[0]:
            continue  # ignore under-body endpoints for corridor seed preference
        seeds.append((int(round(p[0] / res)), int(round(p[1] / res))))
    # Goal: far end of corridor (max body +X)
    if len(zones["corridor"]):
        c0, s0 = math.cos(yaw_ros), math.sin(yaw_ros)
        d0 = zones["corridor"][:, :2] - chassis_xy.reshape(1, 2)
        bx0 = c0 * d0[:, 0] + s0 * d0[:, 1]
        goal_pt = zones["corridor"][int(np.argmax(bx0))]
        goal = (int(round(goal_pt[0] / res)), int(round(goal_pt[1] / res)))
    else:
        goal = start_cell

    def in_corr_bbox(cell):
        x, y = cell[0] * res, cell[1] * res
        return (xmin - res) <= x <= (xmax + res) and (ymin - res) <= y <= (ymax + res)

    reachable = False
    visited = set()
    from collections import deque

    qcells = deque()
    for s0 in seeds:
        if s0 in free_cells and in_corr_bbox(s0):
            qcells.append(s0)
            visited.add(s0)
    # Seed any free cell near corridor near-end (small body-x)
    if len(zones["corridor"]):
        c0, s0 = math.cos(yaw_ros), math.sin(yaw_ros)
        for cell in free_cells:
            if cell in visited or not in_corr_bbox(cell):
                continue
            xy = np.array([cell[0] * res, cell[1] * res])
            dxy = xy - chassis_xy
            bx = c0 * dxy[0] + s0 * dxy[1]
            if zd.half_l + zd.safety_gap_m - 0.05 <= bx <= zd.half_l + zd.safety_gap_m + 0.25:
                qcells.append(cell)
                visited.add(cell)
    while qcells:
        cx, cy = qcells.popleft()
        if (cx, cy) == goal or (
            abs(cx - goal[0]) + abs(cy - goal[1]) <= 1
        ):
            reachable = True
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ncell = (cx + dx, cy + dy)
            if ncell in visited or ncell not in free_cells:
                continue
            if not in_corr_bbox(ncell):
                continue
            visited.add(ncell)
            qcells.append(ncell)

    # Diagnostic ring cloud membership
    def ring_cloud_n(r0, r1):
        if len(pts_ros) == 0:
            return 0
        dxy = np.linalg.norm(pts_ros[:, :2] - chassis_xy.reshape(1, 2), axis=1)
        return int(((dxy >= r0) & (dxy < r1)).sum())

    # Exterior valid depth frac
    ext_cov = zone_free_count(zones["exterior"])
    cor_cov = zone_free_count(zones["corridor"])

    return {
        "tag": tag,
        "arm_q": q.astype(float).tolist(),
        "camera_ros_pos_agl": cam_p.astype(float).tolist(),
        "optical_fwd_ros": R_ros[:, 2].astype(float).tolist(),
        "depth_validity": dstats,
        "n_world": int(len(pts_ros)),
        "n_voxel": int(len(down)),
        "n_ground_planar": int(len(ground_ok)),
        "n_ground_after_outlier": int(len(ground_f)),
        "n_sim_free_cells": int(len(free_cells)),
        "exterior_depth_free": ext_cov,
        "corridor_depth_free": cor_cov,
        "corridor_free_connected_to_goal": bool(reachable),
        "ring_cloud_n": {"r0_0p3": ring_cloud_n(0.0, 0.3), "r0p3_0p6": ring_cloud_n(0.3, 0.6)},
        "contacts": int(env.contact_count()),
        "target_ground_seen": bool(ext_cov["n_with_valid_depth_in_fov"] > 0),
        "production_free_formed": bool(len(ground_f) > 0 and ext_cov["n_in_sim_free"] > 0),
    }


def motion_ok(env, q0: np.ndarray, q1: np.ndarray, baseline: int, steps: int = 12) -> Dict[str, Any]:
    """Interpolate joint space; reject if contact spikes or limits hit."""
    max_delta = 0
    max_contacts = baseline
    for i in range(steps + 1):
        t = i / steps
        q = clip_q((1 - t) * q0 + t * q1)
        env.set_arm_joints(q)
        c = int(env.contact_count())
        max_contacts = max(max_contacts, c)
        max_delta = max(max_delta, c - baseline)
    return {
        "steps": steps,
        "max_contact_delta": int(max_delta),
        "ok": bool(max_delta <= 10),
        "joint_l2": float(np.linalg.norm(q1 - q0)),
    }


def build_candidates(q_raised: np.ndarray, rng: np.random.Generator, n_random: int) -> List[np.ndarray]:
    qs = [q_raised.copy()]
    # Heuristic look-down family (vary j3,j5,j4; keep others near raised)
    for dj3 in np.linspace(-1.2, 0.4, 9):
        for dj5 in np.linspace(-1.6, 1.6, 11):
            for dj4 in (-1.0, 0.0, 1.0):
                q = q_raised.copy()
                q[2] = q[2] + dj3
                q[4] = q[4] + dj5
                q[3] = q[3] + dj4
                qs.append(clip_q(q))
    # Base yaw sweep (j1) + look down
    for dj1 in np.linspace(-1.2, 1.2, 9):
        for dj5 in np.linspace(-1.4, 1.4, 7):
            for dj2 in (-0.4, 0.0, 0.5):
                q = q_raised.copy()
                q[0] = q[0] + dj1
                q[1] = q[1] + dj2
                q[4] = q[4] + dj5
                q[2] = q[2] - 0.5
                qs.append(clip_q(q))
    # Fold-back candidates: large j2/j3 change to bring camera over chassis
    for j2 in np.linspace(-1.2, 1.4, 8):
        for j3 in np.linspace(-2.6, 0.5, 8):
            for j5 in np.linspace(-2.0, 2.0, 6):
                q = q_raised.copy()
                q[1], q[2], q[4] = j2, j3, j5
                qs.append(clip_q(q))
    # Random local + global
    for _ in range(n_random):
        if rng.random() < 0.5:
            noise = rng.normal(0.0, 0.45, size=6)
            qs.append(clip_q(q_raised + noise))
        else:
            q = np.array([rng.uniform(lo, hi) for lo, hi in JOINT_LIMITS])
            qs.append(clip_q(q))
    # Dedup roughly
    uniq = []
    seen = set()
    for q in qs:
        key = tuple(np.round(q, 3).tolist())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(q)
    return uniq


def virtual_mount_geometry(
    chassis_xy: np.ndarray,
    yaw_ros: float,
    zd: ZoneDef,
    K: Dict[str, float],
    w: int,
    h: int,
) -> Dict[str, Any]:
    """Offline: hypothetical chassis-fixed downward camera (not installed)."""
    c, s = math.cos(yaw_ros), math.sin(yaw_ros)
    # mount above front bumper exterior midline
    bx, by, bz = zd.half_l * 0.3, 0.0, 0.35  # 35 cm AGL on chassis
    cam = np.array(
        [
            chassis_xy[0] + c * bx - s * by,
            chassis_xy[1] + s * bx + c * by,
            bz,
        ]
    )
    # optical looks straight down: ROS +Z_opt = world -Z
    R = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float64)
    # rotate yaw about world Z for forward alignment of cam X
    Rz = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)
    R = Rz @ R
    zones = sample_zone_points(chassis_xy, yaw_ros, zd)
    cov = {
        k: project_coverage(zones[k], cam, R, K, w, h)
        for k in ("exterior", "corridor", "occluded_body", "r0_0p3", "r0p3_0p6")
    }
    return {
        "type": "virtual_chassis_down_cam",
        "camera_ros_pos_agl": cam.tolist(),
        "mount_note": "hypothetical; NOT on current hardware",
        "optical": "world -Z (nadir)",
        "coverage": cov,
        "feasible_on_current_arm": False,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default="/workspace/VLN_Mobilemanipulator/reports/hy1_startup_pose_geometry_20261106",
    )
    ap.add_argument(
        "--force_spawn_json",
        default=(
            "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/"
            "real_wide_hy1_openband_20261105_113724/start_pose.json"
        ),
    )
    ap.add_argument(
        "--ppo_raise_json",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json",
    )
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--robot_scale", type=float, default=0.7)
    ap.add_argument("--n_random", type=int, default=800)
    ap.add_argument("--top_k", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--code_sha", default="99ebb49")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    fp = footprint_at_scale(args.robot_scale)
    zd = ZoneDef(
        robot_scale=float(args.robot_scale),
        half_l=float(fp["chassis_half_length_m"]),
        half_w=float(fp["chassis_half_width_m"]),
    )
    freeze = {
        "task": "HY1_startup_pose_geometry_feasibility",
        "code_sha_requested": args.code_sha,
        "prior_observability_report": "reports/hy1_chassis_observability_20261106.md",
        "prior_observability_dir": "reports/hy1_chassis_observability_20261106/",
        "native_case_c": "reports/hy1_chassis_observability_20261106/native_test_map_pipeline_replay.log",
        "config_frozen": {
            "CHASSIS_LOOK_MODE": "none (unchanged)",
            "ground_free_max_agl": GROUND_FREE_MAX_AGL,
            "filter_min_height": FILTER_MIN,
            "no_force_free": True,
            "no_gt_inject_online": True,
            "no_ppo_train": True,
            "no_15deg": True,
        },
        "zone_definition": asdict(zd),
        "footprint_scaled": fp,
        "joint_limits_urdf": [{"joint": f"cr10_joint{i+1}", "lo": lo, "hi": hi} for i, (lo, hi) in enumerate(JOINT_LIMITS)],
        "search_scope_note": (
            "Finite search over heuristic look-down / fold / random samples within URDF limits; "
            "no_solution ≠ proof that no feasible pose exists outside this sample set."
        ),
    }
    (out / "freeze_manifest.json").write_text(json.dumps(freeze, indent=2) + "\n")

    sp_all = json.loads(Path(args.force_spawn_json).read_text())
    sp = sp_all.get("spawn") or sp_all
    env = RangerCr10KinematicEnv(
        scene=SCENE, gpu_device_id=int(args.gpu), robot_scale=float(args.robot_scale)
    )
    floor_y = float(sp.get("floor_y", 0.06218))
    env.floor_y = floor_y
    env.set_base_pose(
        float(sp["x"]),
        float(sp["z"]),
        float(sp["yaw"]),
        y=float(sp.get("base_y", floor_y + env.default_base_y)),
        floor_y=floor_y,
        snap_wheels=True,
    )
    raise_rep = json.loads(Path(args.ppo_raise_json).read_text())
    apply_raise_to_habitat(env, raise_rep["arm_q_final"])
    q_raised = env.arm_q.copy()
    baseline_contacts = int(env.contact_count())
    base = env.base_xyz
    chassis_ros = hab_pos_to_ros(base, floor_y=floor_y)
    yaw_ros = hab_yaw_to_ros(float(env.base_yaw))
    zones = sample_zone_points(chassis_ros[:2], yaw_ros, zd)
    for k, v in zones.items():
        np.save(out / f"zone_{k}.npy", v)

    # dummy K for phase1 (actual res from a quick observe)
    ee0 = env.observe_ee_only()
    depth0 = np.asarray(ee0["ee_depth"])
    if depth0.ndim == 3:
        depth0 = depth0[..., 0]
    h, w = depth0.shape[:2]
    K = pinhole_from_hfov(w, h, 79.0)

    rng = np.random.default_rng(args.seed)
    cands = build_candidates(q_raised, rng, args.n_random)
    (out / "search_space.json").write_text(
        json.dumps(
            {
                "n_candidates": len(cands),
                "n_random": args.n_random,
                "families": ["raised", "lookdown_j3j5j4", "yaw_j1_lookdown", "fold_j2j3j5", "random"],
                "baseline_contacts": baseline_contacts,
                "q_raised": q_raised.astype(float).tolist(),
            },
            indent=2,
        )
        + "\n"
    )

    phase1 = []
    for i, q in enumerate(cands):
        r = fk_score(env, q, zones, K, w, h, baseline_contacts)
        r["idx"] = i
        phase1.append(r)
        if (i + 1) % 200 == 0:
            print(f"phase1 {i+1}/{len(cands)}", flush=True)

    phase1_sorted = sorted(phase1, key=lambda r: r["score"], reverse=True)
    (out / "phase1_top50.json").write_text(
        json.dumps(phase1_sorted[:50], indent=2) + "\n"
    )

    # Keep candidates with any exterior or corridor FOV
    promising = [
        r
        for r in phase1_sorted
        if r["reject"] is None
        and (
            r["coverage"]["exterior"]["n_in_fov"] > 0
            or r["coverage"]["corridor"]["n_in_fov"] > 0
        )
    ]
    if not promising:
        promising = [r for r in phase1_sorted if r["reject"] is None][: args.top_k]

    top = promising[: args.top_k]
    depth_results = []
    for rank, r in enumerate(top):
        tag = f"cand{rank:02d}"
        ev = depth_eval(
            env,
            np.array(r["arm_q"]),
            zones,
            chassis_ros[:2],
            yaw_ros,
            zd,
            out,
            tag,
        )
        mot = motion_ok(env, q_raised, np.array(r["arm_q"]), baseline_contacts)
        ev["phase1_score"] = r["score"]
        ev["phase1_coverage"] = r["coverage"]
        ev["motion_from_raised"] = mot
        depth_results.append(ev)
        print(
            f"depth {tag} ext_seen={ev['exterior_depth_free']} "
            f"corr_conn={ev['corridor_free_connected_to_goal']} "
            f"rings={ev['ring_cloud_n']}",
            flush=True,
        )

    # Rank feasible: target seen + free formed + motion ok
    def rank_key(e):
        return (
            int(e["target_ground_seen"]),
            int(e["production_free_formed"]),
            int(e["corridor_free_connected_to_goal"]),
            int(e["motion_from_raised"]["ok"]),
            e["exterior_depth_free"]["n_in_sim_free"],
            e["corridor_depth_free"]["n_with_valid_depth_in_fov"],
            -e["motion_from_raised"]["joint_l2"],
        )

    depth_results.sort(key=rank_key, reverse=True)
    (out / "phase2_depth_results.json").write_text(
        json.dumps(depth_results, indent=2) + "\n"
    )

    best = depth_results[0] if depth_results else None
    feasible = bool(
        best
        and best["target_ground_seen"]
        and best["production_free_formed"]
        and best["motion_from_raised"]["ok"]
    )

    # Virtual mount reference (always)
    virt = virtual_mount_geometry(chassis_ros[:2], yaw_ros, zd, K, w, h)
    (out / "virtual_mount_geometry.json").write_text(json.dumps(virt, indent=2) + "\n")

    # Limitation taxonomy if not feasible
    max_ext_fov = max((r["coverage"]["exterior"]["n_in_fov"] for r in phase1), default=0)
    max_corr_fov = max((r["coverage"]["corridor"]["n_in_fov"] for r in phase1), default=0)
    max_ext_depth = max(
        (e["exterior_depth_free"]["n_with_valid_depth_in_fov"] for e in depth_results),
        default=0,
    )

    limitations = {
        "search_n": len(cands),
        "phase1_max_exterior_fov_samples": int(max_ext_fov),
        "phase1_max_corridor_fov_samples": int(max_corr_fov),
        "phase2_max_exterior_valid_depth": int(max_ext_depth),
        "body_occluded_ring0_0p3_note": (
            f"At scale={args.robot_scale}, half_l={zd.half_l:.3f} m; "
            "much of 0–0.3 m disk lies under chassis → not a valid exterior observation target."
        ),
    }
    if max_ext_fov == 0 and max_corr_fov == 0:
        limitations["primary_limit"] = "fov_unreachable_in_search_set"
        limitations["detail"] = (
            "No sampled arm config placed exterior/corridor ground samples into image FOV "
            "with usable optical depth (>0.15 m). Causes may include EE mount forward of "
            "bumper, joint workspace, and self-occlusion — finite search only."
        )
    elif max_ext_depth == 0:
        limitations["primary_limit"] = "fov_ok_but_depth_blocked_or_filtered"
    elif best and not best["corridor_free_connected_to_goal"]:
        limitations["primary_limit"] = "free_cells_not_corridor_connected"
    else:
        limitations["primary_limit"] = "partial_or_motion"

    # Acceptance answers
    acceptance = {
        "Q1_target_ground_actually_seen": bool(best and best["target_ground_seen"])
        if best
        else False,
        "Q2_obs_formed_valid_free_via_production_mirror": bool(
            best and best["production_free_formed"]
        )
        if best
        else False,
        "Q3_native_planner_safe_startup_path": (
            "NOT_RUN — no feasible observe pose for static map seed; "
            "deferred until a covering pose exists or virtual mount is adopted"
            if not feasible
            else "STATIC_REPLAY_ONLY_NEXT — pose found; native planner startup is a separate experiment"
        ),
        "Q4_path_relies_on_near_start_exemption": (
            "N/A — no startup path generated this stage; exemption remains observe-only at 0.25 m"
        ),
        "Q5_pose_switch_and_base_motion_collision": {
            "arm_switch": (best["motion_from_raised"] if best else None),
            "base_execution": "NOT_RUN (no chassis motion this stage)",
        },
        "startup_state_vs_planner_interface": (
            "If coverage improves but start stays UNKNOWN, treat as separate "
            "start-state/planner-interface issue — do not rewrite map."
        ),
    }

    next_plan = {}
    if feasible:
        next_plan = {
            "choice": "feasible_arm_pose_found",
            "best_tag": best["tag"],
            "best_arm_q": best["arm_q"],
            "actions": [
                "Static production-chain replay of this pose into map_ros (single-frame publish; no deploy change).",
                "Independent startup episode experiment with pose switch gated off default CHASSIS_LOOK_MODE.",
            ],
        }
    else:
        next_plan = {
            "choice": "no_feasible_pose_in_search_set",
            "limitations": limitations,
            "virtual_mount": {
                "summary": virt,
                "next": (
                    "Validate virtual chassis-down camera coverage further; "
                    "if exterior/corridor FOV becomes non-zero, propose physical remount / aux sensor "
                    "as a separate hardware task — still no GT inject / no force FREE."
                ),
            },
            "actions": [
                "Do NOT claim absolute impossibility — expand search or add wrist-look-at IK only if needed.",
                "Primary evidence-backed implementation path: aux/chassis-down camera geometric validation → hardware proposal.",
            ],
        }

    summary = {
        "freeze": freeze,
        "spawn": {"x": sp["x"], "z": sp["z"], "yaw": sp["yaw"], "floor_y": floor_y},
        "chassis_ros_xy_agl": chassis_ros.astype(float).tolist(),
        "yaw_ros": float(yaw_ros),
        "q_raised": q_raised.astype(float).tolist(),
        "baseline_contacts": baseline_contacts,
        "n_search": len(cands),
        "n_phase2": len(depth_results),
        "feasible": feasible,
        "best": best,
        "acceptance": acceptance,
        "next_plan": next_plan,
        "elapsed_s": time.time() - t0,
        "B_C_prior_negative_kept": True,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("feasible", "acceptance", "next_plan")}, indent=2)[:5000])
    print("OUT", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
