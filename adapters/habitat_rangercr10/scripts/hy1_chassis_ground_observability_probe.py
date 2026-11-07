#!/usr/bin/env python3
"""Fixed-pose B/C probe: chassis-ground observability + free-update stage trace.

Does NOT run batch navigation. Does NOT change deploy defaults.
Mirrors map_ros height / planar / outlier gates for diagnosis only.

Run inside vln-rangercr10:
  export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:$PYTHONPATH
  python /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/scripts/hy1_chassis_ground_observability_probe.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

# Production map_ros gates (algorithm_rangercr10.xml) — observe only.
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
OUTLIER_OBST_R = 0.3
OUTLIER_OBST_MIN = 35

SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d_v0.2/val/"
    "00894-HY1NcmCgn3n/HY1NcmCgn3n.basis.glb"
)


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


def chassis_ring_samples(
    chassis_xy: np.ndarray, r0: float, r1: float, n_ang: int = 48, n_rad: int = 8
) -> np.ndarray:
    pts = []
    for i in range(n_rad):
        r = r0 + (r1 - r0) * (i + 0.5) / n_rad
        for j in range(n_ang):
            th = 2.0 * math.pi * j / n_ang
            pts.append(
                [
                    chassis_xy[0] + r * math.cos(th),
                    chassis_xy[1] + r * math.sin(th),
                    0.0,
                ]
            )
    return np.asarray(pts, dtype=np.float64)


def project_ros_points_to_image(
    pts_ros: np.ndarray,
    cam_p_ros: np.ndarray,
    R_ros: np.ndarray,
    K: Dict[str, float],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = pts_ros - cam_p_ros.reshape(1, 3)
    p_cam = (R_ros.T @ d.T).T
    in_front = p_cam[:, 2] > 1e-4
    u = np.full(len(pts_ros), np.nan)
    v = np.full(len(pts_ros), np.nan)
    for i in np.where(in_front)[0]:
        uu, vv = project_optical(p_cam[i], K)
        u[i], v[i] = uu, vv
    return u, v, in_front


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


def segment_hits_annulus(
    cam_xy: np.ndarray,
    end_xy: np.ndarray,
    center: np.ndarray,
    r0: float,
    r1: float,
    n: int = 40,
) -> bool:
    for t in np.linspace(0.0, 1.0, n):
        p = cam_xy + t * (end_xy - cam_xy)
        d = float(np.linalg.norm(p - center))
        if r0 <= d <= r1:
            return True
    return False


def capture_pose(env, label: str, arm_q: np.ndarray, out: Path) -> Dict[str, Any]:
    env.set_arm_joints(arm_q)
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
    cam_p_ros, cam_q = mat4_hab_optical_to_ros_pose(cam_T, floor_y=floor_y)
    R_hab = cam_M[:3, :3]
    R_ros = hab_optical_rot_to_ros(R_hab)
    base = env.base_xyz
    chassis_ros = hab_pos_to_ros(base, floor_y=floor_y)
    yaw_ros = hab_yaw_to_ros(float(env.base_yaw))

    h, w = depth_raw.shape[:2]
    K = pinhole_from_hfov(w, h, 79.0)

    self_hit = np.isfinite(depth_raw) & np.isnan(depth_prep)
    valid_raw = np.isfinite(depth_raw) & (depth_raw > 1e-4) & (depth_raw <= 5.0)
    valid_prep = np.isfinite(depth_prep)

    Image.fromarray(rgb.astype(np.uint8)).save(out / f"{label}_rgb.png")
    dv = depth_raw.copy()
    dv[~np.isfinite(dv)] = 0
    Image.fromarray((np.clip(dv / 5.0, 0, 1) * 255).astype(np.uint8)).save(
        out / f"{label}_depth_raw_u8.png"
    )
    overlay = rgb.astype(np.uint8).copy()
    overlay[self_hit] = (255, 40, 40)
    Image.fromarray(overlay).save(out / f"{label}_selfhit_overlay.png")
    np.save(out / f"{label}_depth_raw.npy", depth_raw)
    np.save(out / f"{label}_depth_prep.npy", depth_prep)
    np.save(out / f"{label}_self_hit_mask.npy", self_hit.astype(np.uint8))

    rings = {
        "r0_0p3": chassis_ring_samples(chassis_ros[:2], 0.0, 0.3),
        "r0p3_0p6": chassis_ring_samples(chassis_ros[:2], 0.3, 0.6),
    }
    cov: Dict[str, Any] = {}
    canvas_img = Image.fromarray(rgb.astype(np.uint8).copy())
    draw = ImageDraw.Draw(canvas_img)
    colors = {"r0_0p3": (0, 255, 0), "r0p3_0p6": (0, 180, 255)}
    for name, pts in rings.items():
        u, v, infra = project_ros_points_to_image(pts, cam_p_ros, R_ros, K)
        in_fov = infra & (u >= 0) & (u < w) & (v >= 0) & (v < h)
        has_depth = np.zeros(len(pts), dtype=bool)
        blocked_self = np.zeros(len(pts), dtype=bool)
        for i in np.where(in_fov)[0]:
            ui, vi = int(round(u[i])), int(round(v[i]))
            if not (0 <= ui < w and 0 <= vi < h):
                continue
            if valid_prep[vi, ui]:
                has_depth[i] = True
            elif self_hit[vi, ui]:
                blocked_self[i] = True
            col = colors[name]
            r = 3 if has_depth[i] else 2
            draw.ellipse(
                [ui - r, vi - r, ui + r, vi + r],
                outline=col,
                fill=col if has_depth[i] else None,
            )
        cov[name] = {
            "n_samples": int(len(pts)),
            "n_in_front": int(infra.sum()),
            "n_in_fov": int(in_fov.sum()),
            "frac_in_fov": float(in_fov.mean()),
            "n_with_valid_prep_depth": int(has_depth.sum()),
            "frac_with_valid_prep_depth": float(has_depth.mean()),
            "n_in_fov_but_self_hit": int(blocked_self.sum()),
            "n_in_fov_no_depth_not_selfhit": int(
                (in_fov & ~has_depth & ~blocked_self).sum()
            ),
        }
    for pt, col in (
        (np.array([[chassis_ros[0], chassis_ros[1], 0.0]]), (255, 255, 0)),
        (cam_p_ros.reshape(1, 3), (255, 0, 255)),
    ):
        uu, vv, infra = project_ros_points_to_image(pt, cam_p_ros, R_ros, K)
        if infra[0] and 0 <= uu[0] < w and 0 <= vv[0] < h:
            ui, vi = int(uu[0]), int(vv[0])
            draw.ellipse([ui - 5, vi - 5, ui + 5, vi + 5], outline=col, width=2)
    canvas_img.save(out / f"{label}_chassis_ground_proj.png")

    # Unproject prep depth → ROS world (subsample stride 2)
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
            axis=0,
        )
        pts_ros = (R_ros @ pts_opt.T).T + cam_p_ros.reshape(1, 3)

    def ring_mask(pts, r0, r1):
        if len(pts) == 0:
            return np.zeros(0, dtype=bool)
        dxy = np.linalg.norm(pts[:, :2] - chassis_ros[:2], axis=1)
        return (dxy >= r0) & (dxy < r1)

    stages: Dict[str, Any] = {
        "raw_valid_px": int(valid_raw.sum()),
        "after_selfhit_valid_px": int(valid_prep.sum()),
        "n_self_hit_px": int(self_hit.sum()),
        "world_cloud_n": int(len(pts_ros)),
        "height_agl_stats": {
            "n": int(len(pts_ros)),
            "min": float(pts_ros[:, 2].min()) if len(pts_ros) else None,
            "max": float(pts_ros[:, 2].max()) if len(pts_ros) else None,
            "mean": float(pts_ros[:, 2].mean()) if len(pts_ros) else None,
            "frac_neg": float((pts_ros[:, 2] < 0).mean()) if len(pts_ros) else None,
            "frac_0_0p03": float(((pts_ros[:, 2] >= 0) & (pts_ros[:, 2] <= 0.03)).mean())
            if len(pts_ros)
            else None,
            "frac_0p03_0p28": float(
                ((pts_ros[:, 2] > 0.03) & (pts_ros[:, 2] <= 0.28)).mean()
            )
            if len(pts_ros)
            else None,
            "hist_edges": [-0.5, -0.1, 0.0, 0.03, 0.1, 0.2, 0.28, 0.5, 1.0, 2.0],
            "hist_counts": (
                np.histogram(
                    pts_ros[:, 2],
                    bins=[-0.5, -0.1, 0.0, 0.03, 0.1, 0.2, 0.28, 0.5, 1.0, 2.0],
                )[0].tolist()
                if len(pts_ros)
                else []
            ),
        },
    }

    down = voxel_downsample(pts_ros, VOXEL_XY, VOXEL_Z)
    stages["after_voxel_n"] = int(len(down))

    # Classify
    under, obst, ground_ok, planar_rej, low_obst, other = [], [], [], [], [], []
    for i in range(len(down)):
        z = float(down[i, 2])
        if z < VIRTUAL_GROUND:
            under.append(i)
        elif FILTER_MIN < z < FILTER_MAX:
            obst.append(i)
        elif 0.0 <= z <= FILTER_MIN:
            if z <= GROUND_FREE_MAX_AGL:
                if is_planar(down, i):
                    ground_ok.append(i)
                else:
                    planar_rej.append(i)
            else:
                low_obst.append(i)
        else:
            other.append(i)
    stages["classify_counts"] = {
        "under_virtual": len(under),
        "obstacle_band": len(obst),
        "ground_planar_ok": len(ground_ok),
        "planar_reject": len(planar_rej),
        "low_obstacle": len(low_obst),
        "other": len(other),
    }

    ground_pts = down[ground_ok] if ground_ok else down[:0]
    obst_pts = (
        down[obst + low_obst] if (obst or low_obst) else down[:0]
    )
    ground_f = radius_outlier(ground_pts, OUTLIER_GROUND_R, OUTLIER_GROUND_MIN)
    obst_f = radius_outlier(obst_pts, OUTLIER_OBST_R, OUTLIER_OBST_MIN)
    stages["ground_after_outlier_n"] = int(len(ground_f))
    stages["obstacle_after_outlier_n"] = int(len(obst_f))

    # Save ring-local height samples
    if len(pts_ros):
        m03 = ring_mask(pts_ros, 0.0, 0.3)
        np.save(out / f"{label}_world_pts_ring0_0p3.npy", pts_ros[m03])
        np.save(
            out / f"{label}_world_pts_ring0p3_0p6.npy",
            pts_ros[ring_mask(pts_ros, 0.3, 0.6)],
        )

    ring_stats = {}
    cam_xy = cam_p_ros[:2]
    for rname, (r0, r1) in (("r0_0p3", (0.0, 0.3)), ("r0p3_0p6", (0.3, 0.6))):
        m_world = ring_mask(pts_ros, r0, r1)
        m_down = ring_mask(down, r0, r1)
        band = {
            "world_n": int(m_world.sum()),
            "voxel_n": int(m_down.sum()),
            "ground_planar_ok": 0,
            "planar_reject": 0,
            "low_obstacle": 0,
            "obstacle_band": 0,
            "under_virtual": 0,
            "other": 0,
            "ground_after_outlier": 0,
            "rays_crossing_ring_from_any_endpoint": 0,
            "rays_crossing_ring_from_ground_endpoint": 0,
            "free_ray_endpoints_in_ring": 0,
            "world_z_agl": {},
        }
        if m_world.sum():
            zz = pts_ros[m_world, 2]
            band["world_z_agl"] = {
                "min": float(zz.min()),
                "max": float(zz.max()),
                "mean": float(zz.mean()),
                "frac_neg": float((zz < 0).mean()),
                "frac_0_0p03": float(((zz >= 0) & (zz <= 0.03)).mean()),
            }
        idxs = np.where(m_down)[0]
        for i in idxs:
            z = float(down[i, 2])
            if z < VIRTUAL_GROUND:
                band["under_virtual"] += 1
            elif FILTER_MIN < z < FILTER_MAX:
                band["obstacle_band"] += 1
            elif 0.0 <= z <= FILTER_MIN:
                if z <= GROUND_FREE_MAX_AGL:
                    if is_planar(down, i):
                        band["ground_planar_ok"] += 1
                    else:
                        band["planar_reject"] += 1
                else:
                    band["low_obstacle"] += 1
            else:
                band["other"] += 1
        if len(ground_f):
            band["ground_after_outlier"] = int(ring_mask(ground_f, r0, r1).sum())
            band["free_ray_endpoints_in_ring"] = band["ground_after_outlier"]
        # Ray XY through ring even without ground endpoints in ring
        ends_any = down if len(down) else pts_ros
        n_cross_any = 0
        if len(ends_any):
            stride = max(1, len(ends_any) // 3000)
            for p in ends_any[::stride]:
                if segment_hits_annulus(cam_xy, p[:2], chassis_ros[:2], r0, r1):
                    n_cross_any += 1
        band["rays_crossing_ring_from_any_endpoint"] = int(n_cross_any)
        n_cross_g = 0
        if len(ground_f):
            for p in ground_f:
                if segment_hits_annulus(cam_xy, p[:2], chassis_ros[:2], r0, r1):
                    n_cross_g += 1
        band["rays_crossing_ring_from_ground_endpoint"] = int(n_cross_g)
        ring_stats[rname] = band

    # Representative cells in 0–0.3 m
    res = 0.05
    unk_trace = []
    for r in np.arange(-0.3, 0.301, res):
        for c in np.arange(-0.3, 0.301, res):
            cell = np.array([chassis_ros[0] + r, chassis_ros[1] + c], dtype=np.float64)
            d = float(np.linalg.norm(cell - chassis_ros[:2]))
            if d > 0.3:
                continue
            hit_miss = False
            for p in ground_f:
                a, b = cam_p_ros[:2], p[:2]
                ab = b - a
                L2 = float(np.dot(ab, ab)) + 1e-12
                t = float(np.clip(np.dot(cell - a, ab) / L2, 0.0, 1.0))
                closest = a + t * ab
                if np.linalg.norm(closest - cell) <= res * 0.75:
                    hit_miss = True
                    break
            ep_in = bool(
                len(ground_f)
                and np.any(np.linalg.norm(ground_f[:, :2] - cell, axis=1) <= res * 0.75)
            )
            occ_hit = bool(
                len(obst_f)
                and np.any(np.linalg.norm(obst_f[:, :2] - cell, axis=1) <= res * 0.75)
            )
            skip_reasons = []
            if not hit_miss and not ep_in:
                skip_reasons.append("no_free_ray_segment_through_cell")
            if occ_hit:
                skip_reasons.append("occupied_endpoint_nearby")
            if not ep_in and hit_miss:
                skip_reasons.append("ray_crosses_but_endpoint_elsewhere")
            unk_trace.append(
                {
                    "cell_xy": cell.tolist(),
                    "dist_chassis_m": d,
                    "free_ray_segment_through": hit_miss,
                    "ground_endpoint_in_cell": ep_in,
                    "occupied_endpoint_nearby": occ_hit,
                    "skip_reasons": skip_reasons,
                    "note": "offline mirror; production log-odds not simulated",
                }
            )

    meta = {
        "label": label,
        "arm_q": arm_q.astype(float).tolist(),
        "base_hab": {
            "x": float(base[0]),
            "y": float(base[1]),
            "z": float(base[2]),
            "yaw": float(env.base_yaw),
        },
        "chassis_ros_xy_agl": chassis_ros.astype(float).tolist(),
        "yaw_ros": float(yaw_ros),
        "camera_ros_pos_agl": cam_p_ros.astype(float).tolist(),
        "camera_ros_quat_xyzw": cam_q.astype(float).tolist(),
        "camera_R_ros_3x3": R_ros.astype(float).tolist(),
        "camera_hab_T_4x4": cam_M.astype(float).tolist(),
        "K": K,
        "depth_validity": dstats,
        "coverage_projection": cov,
        "stages": stages,
        "ring_stage_stats": ring_stats,
        "unknown_cell_trace_n": len(unk_trace),
        "unknown_cell_trace_sample": unk_trace[:60],
        "unknown_cells_with_ray_through": int(
            sum(1 for u in unk_trace if u["free_ray_segment_through"])
        ),
        "unknown_cells_with_ground_endpoint": int(
            sum(1 for u in unk_trace if u["ground_endpoint_in_cell"])
        ),
    }
    (out / f"{label}_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default="/workspace/VLN_Mobilemanipulator/reports/hy1_chassis_observability_20261106",
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
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sp_all = json.loads(Path(args.force_spawn_json).read_text())
    sp = sp_all.get("spawn") or sp_all
    env = RangerCr10KinematicEnv(
        scene=SCENE,
        gpu_device_id=int(args.gpu),
        robot_scale=float(args.robot_scale),
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
    raised = env.arm_q.copy()

    meta_b = capture_pose(env, "B_budget_match_pose", raised, out)
    q_c = raised.copy()
    q_c[2] = float(np.clip(float(q_c[2]) - 0.60, -2.86, 2.86))
    meta_c = capture_pose(env, "C_chassis_ground_pose", q_c, out)

    def pick(m):
        return {
            "coverage": m["coverage_projection"],
            "ring_stage_stats": m["ring_stage_stats"],
            "height_agl_stats": m["stages"]["height_agl_stats"],
            "classify_counts": m["stages"]["classify_counts"],
            "ground_after_outlier_n": m["stages"]["ground_after_outlier_n"],
            "unknown_cells_with_ray_through": m["unknown_cells_with_ray_through"],
            "unknown_cells_with_ground_endpoint": m["unknown_cells_with_ground_endpoint"],
            "camera_ros_pos_agl": m["camera_ros_pos_agl"],
            "arm_q": m["arm_q"],
            "stages_px": {
                "raw_valid_px": m["stages"]["raw_valid_px"],
                "after_selfhit_valid_px": m["stages"]["after_selfhit_valid_px"],
                "n_self_hit_px": m["stages"]["n_self_hit_px"],
                "world_cloud_n": m["stages"]["world_cloud_n"],
                "after_voxel_n": m["stages"]["after_voxel_n"],
            },
        }

    summary = {
        "probe": "fixed_pose_B_C_chassis_ground_observability",
        "baseline_ref": "99ebb49 A/B/C negative kept",
        "spawn": {"x": sp["x"], "z": sp["z"], "yaw": sp["yaw"], "floor_y": floor_y},
        "B": pick(meta_b),
        "C": {
            **pick(meta_c),
            "joint3_delta_from_B": float(q_c[2] - raised[2]),
        },
        "gates_mirrored": {
            "filter_min_height": FILTER_MIN,
            "ground_free_max_agl": GROUND_FREE_MAX_AGL,
            "virtual_ground": VIRTUAL_GROUND,
            "planar": {"r": PLANAR_R, "z_tol": PLANAR_Z_TOL, "min_n": PLANAR_MIN_N},
        },
        "artifacts": {
            "B_proj": "B_budget_match_pose_chassis_ground_proj.png",
            "C_proj": "C_chassis_ground_pose_chassis_ground_proj.png",
            "B_meta": "B_budget_match_pose_meta.json",
            "C_meta": "C_chassis_ground_pose_meta.json",
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2)[:5000])
    print("OUT", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
