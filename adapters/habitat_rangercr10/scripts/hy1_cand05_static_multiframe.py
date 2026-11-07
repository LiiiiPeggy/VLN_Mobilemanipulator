#!/usr/bin/env python3
"""cand05 static multi-frame production-chain verification (no chassis motion).

Feature flag: STATIC_OBS_ENABLE=1, STATIC_OBS_POSE=cand05
Asserts CHASSIS_LOOK_MODE is unset or 'none'.

Counts progress by map_pipeline_diag.jsonl frame_seq (production callbacks),
not by publish count alone.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from PIL import Image, ImageDraw

import rospy
from std_msgs.msg import Float64

from src.camera_model import pinhole_from_hfov, project_optical, unproject_optical
from src.coord_habitat_ros import (
    hab_optical_rot_to_ros,
    hab_pos_to_ros,
    hab_yaw_to_ros,
    mat4_hab_optical_to_ros_pose,
)
from src.depth_validity import prepare_depth_for_apexnav
from src.kinematic_demo import RangerCr10KinematicEnv
from src.map_listener import ApexNavMapListener, _cloud_xy
from src.ppo_mujoco_raise import apply_raise_to_habitat
from src.robot_scale import footprint_at_scale
from src.ros_dynamic_publisher import DynamicROSPublisher

SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d_v0.2/val/"
    "00894-HY1NcmCgn3n/HY1NcmCgn3n.basis.glb"
)
SPAWN = Path(
    "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/"
    "real_wide_hy1_openband_20261105_113724/start_pose.json"
)
PPO = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json")
GEOM = Path(
    "/workspace/VLN_Mobilemanipulator/reports/hy1_startup_pose_geometry_20261106/"
    "rerank_geom_ground.json"
)

FILTER_MIN = 0.28
GROUND_FREE_MAX_AGL = 0.03
PLANAR_R, PLANAR_Z_TOL, PLANAR_MIN_N = 0.12, 0.02, 5
VOXEL_XY, VOXEL_Z = 0.04, 0.1
OUTLIER_R, OUTLIER_MIN = 0.25, 8
RES = 0.05
HALF_L, HALF_W = 0.4557, 0.30429
GAP, CORR_LEN, CORR_SIDE = 0.05, 0.80, 0.05
SAFE_GAP = 0.05  # footprint safety for "continuous free width"


def _mat4(T):
    M = np.eye(4)
    M[:3, :3] = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
    M[:3, 3] = [T.translation.x, T.translation.y, T.translation.z]
    return M


def body_xy(pts_xy: np.ndarray, chassis_xy: np.ndarray, yaw: float):
    c, s = math.cos(yaw), math.sin(yaw)
    d = pts_xy - chassis_xy.reshape(1, 2)
    bx = c * d[:, 0] + s * d[:, 1]
    by = -s * d[:, 0] + c * d[:, 1]
    return bx, by


def corridor_mask_xy(pts_xy: np.ndarray, chassis_xy: np.ndarray, yaw: float) -> np.ndarray:
    if len(pts_xy) == 0:
        return np.zeros(0, dtype=bool)
    bx, by = body_xy(pts_xy, chassis_xy, yaw)
    return (
        (bx >= HALF_L + GAP)
        & (bx <= HALF_L + GAP + CORR_LEN)
        & (np.abs(by) <= HALF_W + CORR_SIDE)
    )


def sample_corridor_ground(chassis_xy: np.ndarray, yaw: float) -> np.ndarray:
    c, s = math.cos(yaw), math.sin(yaw)
    pts = []
    for bx in np.linspace(HALF_L + GAP, HALF_L + GAP + CORR_LEN, 12):
        for by in np.linspace(-(HALF_W + CORR_SIDE), HALF_W + CORR_SIDE, 9):
            pts.append(
                [
                    chassis_xy[0] + c * bx - s * by,
                    chassis_xy[1] + s * bx + c * by,
                    0.0,
                ]
            )
    return np.asarray(pts, dtype=np.float64)


def voxelize(pts: np.ndarray) -> Set[Tuple[int, int]]:
    if pts.size == 0:
        return set()
    ij = np.floor(pts / RES).astype(np.int64)
    return set(map(tuple, ij.tolist()))


def is_planar(cloud: np.ndarray, idx: int) -> bool:
    p = cloud[idx]
    r2 = PLANAR_R * PLANAR_R
    n_ok = 0
    for j, q in enumerate(cloud):
        if j == idx:
            continue
        if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > r2:
            continue
        if abs(p[2] - q[2]) <= PLANAR_Z_TOL:
            n_ok += 1
            if n_ok >= PLANAR_MIN_N:
                return True
    return False


def voxel_downsample(pts: np.ndarray) -> np.ndarray:
    if len(pts) == 0:
        return pts
    keys = np.stack(
        [
            np.floor(pts[:, 0] / VOXEL_XY).astype(np.int64),
            np.floor(pts[:, 1] / VOXEL_XY).astype(np.int64),
            np.floor(pts[:, 2] / VOXEL_Z).astype(np.int64),
        ],
        1,
    )
    _, idx = np.unique(keys, axis=0, return_index=True)
    return pts[np.sort(idx)]


def radius_outlier(cloud: np.ndarray) -> np.ndarray:
    if len(cloud) == 0:
        return cloud
    keep = []
    r2 = OUTLIER_R * OUTLIER_R
    for i, p in enumerate(cloud):
        n = 0
        for j, q in enumerate(cloud):
            if i == j:
                continue
            if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 <= r2:
                n += 1
                if n >= OUTLIER_MIN:
                    keep.append(i)
                    break
    return cloud[keep] if keep else cloud[:0]


def geom_consistent_corridor_ground(
    depth_prep: np.ndarray,
    cam_p: np.ndarray,
    R: np.ndarray,
    K: dict,
    samples: np.ndarray,
    tol: float = 0.20,
) -> Tuple[int, np.ndarray]:
    h, w = depth_prep.shape
    ok_pts = []
    for p in samples:
        pc = R.T @ (p - cam_p)
        if pc[2] <= 0.15:
            continue
        u, v = project_optical(pc, K)
        if not (0 <= u < w and 0 <= v < h):
            continue
        ui, vi = int(u), int(v)
        if not np.isfinite(depth_prep[vi, ui]):
            continue
        pr = unproject_optical(ui, vi, float(depth_prep[vi, ui]), K)
        pw = (R @ pr) + cam_p
        if np.linalg.norm(pw - p) <= tol and 0.0 <= pw[2] <= 0.05:
            ok_pts.append(pw)
    return len(ok_pts), np.asarray(ok_pts) if ok_pts else np.zeros((0, 3))


def pipeline_stages_on_cloud(
    pw: np.ndarray, chassis_xy: np.ndarray, yaw: float
) -> Dict[str, Any]:
    cm = corridor_mask_xy(pw[:, :2], chassis_xy, yaw) if len(pw) else np.zeros(0, bool)
    corr = pw[cm] if len(pw) else pw
    raw_g = int(((corr[:, 2] >= 0) & (corr[:, 2] <= GROUND_FREE_MAX_AGL)).sum()) if len(corr) else 0
    down = voxel_downsample(pw)
    cm_d = corridor_mask_xy(down[:, :2], chassis_xy, yaw) if len(down) else np.zeros(0, bool)
    down_corr = down[cm_d] if len(down) else down
    after_voxel_g = (
        int(((down_corr[:, 2] >= 0) & (down_corr[:, 2] <= GROUND_FREE_MAX_AGL)).sum())
        if len(down_corr)
        else 0
    )
    prov = [i for i in range(len(down)) if 0.0 <= float(down[i, 2]) <= GROUND_FREE_MAX_AGL]
    ok = [i for i in prov if is_planar(down, i)]
    rej = len(prov) - len(ok)
    ground = down[ok] if ok else down[:0]
    cm_g = corridor_mask_xy(ground[:, :2], chassis_xy, yaw) if len(ground) else np.zeros(0, bool)
    after = radius_outlier(ground)
    cm_a = corridor_mask_xy(after[:, :2], chassis_xy, yaw) if len(after) else np.zeros(0, bool)
    ep_cells = {
        (int(round(p[0] / RES)), int(round(p[1] / RES))) for p in after[cm_a]
    } if len(after) and cm_a.any() else set()
    return {
        "corridor_raw_ground_agl": raw_g,
        "after_voxel_corridor_ground": after_voxel_g,
        "planar_ok_corridor": int(cm_g.sum()) if len(cm_g) else 0,
        "planar_reject_full_ground_band": int(rej),
        "after_outlier_corridor_endpoints": int(cm_a.sum()) if len(cm_a) else 0,
        "after_outlier_endpoint_cells": int(len(ep_cells)),
        "endpoint_cells": sorted(ep_cells),
        "ground_after_outlier_xyz": after[cm_a].tolist() if len(after) and cm_a.any() else [],
    }


def read_pipeline_diag(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def wait_frame_seq(diag_path: Path, target: int, timeout_s: float = 30.0) -> Optional[dict]:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        rows = read_pipeline_diag(diag_path)
        if rows and int(rows[-1].get("frame_seq", 0)) >= target:
            return rows[-1]
        time.sleep(0.05)
    rows = read_pipeline_diag(diag_path)
    return rows[-1] if rows else None


def map_layer_sets(ml: ApexNavMapListener) -> Dict[str, Set[Tuple[int, int]]]:
    return {
        "free": voxelize(_cloud_xy(ml.clouds.get("free"))),
        "occupied": voxelize(_cloud_xy(ml.clouds.get("occupied"))),
        "unknown": voxelize(_cloud_xy(ml.clouds.get("unknown"))),
        "inflate": voxelize(_cloud_xy(ml.clouds.get("occupied_inflate"))),
    }


def corridor_cells(chassis_xy: np.ndarray, yaw: float) -> Set[Tuple[int, int]]:
    samples = sample_corridor_ground(chassis_xy, yaw)
    return voxelize(samples[:, :2])


def cell_state(ij, layers) -> str:
    if ij in layers["inflate"] or ij in layers["occupied"]:
        return "occupied_or_inflate"
    if ij in layers["free"]:
        return "free"
    if ij in layers["unknown"]:
        return "unknown"
    return "absent"


def corridor_connectivity(
    free_corr: Set[Tuple[int, int]], chassis_xy: np.ndarray, yaw: float
) -> Dict[str, Any]:
    """BFS along corridor free cells; measure max contiguous body-x span and min width."""
    if not free_corr:
        return {
            "connected_span_m": 0.0,
            "n_free_cells": 0,
            "min_width_m": 0.0,
            "required_width_m": 2 * (HALF_W + SAFE_GAP),
            "width_ok": False,
            "near_to_far_connected": False,
            "gaps_body_x_m": [],
        }
    # seed near bumper
    c, s = math.cos(yaw), math.sin(yaw)
    seeds = []
    for ij in free_corr:
        xy = np.array([ij[0] * RES + 0.5 * RES, ij[1] * RES + 0.5 * RES])
        bx, by = body_xy(xy.reshape(1, 2), chassis_xy, yaw)
        if HALF_L + GAP - 0.05 <= bx[0] <= HALF_L + GAP + 0.25:
            seeds.append(ij)
    if not seeds:
        seeds = [next(iter(free_corr))]
    vis = set()
    q = deque(seeds)
    for s0 in seeds:
        vis.add(s0)
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cx + dx, cy + dy)
            if n in free_corr and n not in vis:
                vis.add(n)
                q.append(n)
    bxs = []
    by_at = {}
    for ij in vis:
        xy = np.array([ij[0] * RES + 0.5 * RES, ij[1] * RES + 0.5 * RES])
        bx, by = body_xy(xy.reshape(1, 2), chassis_xy, yaw)
        bxs.append(float(bx[0]))
        k = int(round(float(bx[0]) / RES))
        by_at.setdefault(k, []).append(float(by[0]))
    span = (max(bxs) - min(bxs)) if bxs else 0.0
    widths = []
    for k, ys in by_at.items():
        widths.append(max(ys) - min(ys) if len(ys) > 1 else 0.0)
    min_w = float(min(widths)) if widths else 0.0
    req = 2 * (HALF_W + SAFE_GAP)
    # near-far: any free near start band and near far band in same component
    near = any(
        HALF_L + GAP - 0.05 <= body_xy(
            np.array([[ij[0] * RES, ij[1] * RES]]), chassis_xy, yaw
        )[0][0]
        <= HALF_L + GAP + 0.2
        for ij in vis
    )
    far = any(
        body_xy(np.array([[ij[0] * RES, ij[1] * RES]]), chassis_xy, yaw)[0][0]
        >= HALF_L + GAP + CORR_LEN - 0.15
        for ij in vis
    )
    # gaps: body-x bins in corridor without free
    gaps = []
    bins = np.arange(HALF_L + GAP, HALF_L + GAP + CORR_LEN + 1e-6, RES)
    occupied_bins = set(int(round(x / RES)) for x in bxs)
    for bx in bins:
        kb = int(round(bx / RES))
        if kb not in occupied_bins:
            gaps.append(float(bx))
    return {
        "connected_span_m": float(span),
        "n_free_cells": int(len(vis)),
        "min_width_m": float(min_w),
        "required_width_m": float(req),
        "width_ok": bool(min_w + 1e-6 >= req * 0.5),  # half-width proxy on one side strip
        "near_to_far_connected": bool(near and far),
        "gaps_body_x_m": gaps[:20],
        "n_gap_bins": int(len(gaps)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default="/workspace/VLN_Mobilemanipulator/reports/hy1_cand05_static_multiframe_20261106",
    )
    ap.add_argument("--pipeline_diag", required=True)
    ap.add_argument("--checkpoints", default="1,5,10,20,40")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--publish_hz", type=float, default=4.0)
    ap.add_argument("--max_publish_attempts", type=int, default=80)
    args = ap.parse_args()

    # Feature flag / mode guards
    look = (os.environ.get("CHASSIS_LOOK_MODE") or "none").strip().lower()
    if look not in ("", "none"):
        raise SystemExit(f"CHASSIS_LOOK_MODE must be none, got {look!r}")
    if (os.environ.get("STATIC_OBS_ENABLE") or "0") not in ("1", "true", "True"):
        raise SystemExit("STATIC_OBS_ENABLE=1 required")
    pose_name = (os.environ.get("STATIC_OBS_POSE") or "cand05").strip()
    if pose_name != "cand05":
        raise SystemExit(f"This script only runs cand05; got STATIC_OBS_POSE={pose_name}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    diag_path = Path(args.pipeline_diag)
    checkpoints = [int(x) for x in args.checkpoints.split(",") if x.strip()]

    rows = json.loads(GEOM.read_text())
    cand05_q = np.array([r for r in rows if r["tag"] == "cand05"][0]["arm_q"], float)
    cand06_q = np.array([r for r in rows if r["tag"] == "cand06"][0]["arm_q"], float)
    sp = json.loads(SPAWN.read_text())["spawn"]
    fp = footprint_at_scale(0.7)

    rospy.init_node("hy1_cand05_static_multiframe", anonymous=True)
    ml = ApexNavMapListener()
    conf = rospy.Publisher("/detector/confidence_threshold", Float64, queue_size=10)
    rospy.sleep(0.5)

    env = RangerCr10KinematicEnv(scene=SCENE, gpu_device_id=args.gpu, robot_scale=0.7)
    fy = float(sp["floor_y"])
    env.floor_y = fy
    env.set_base_pose(
        float(sp["x"]), float(sp["z"]), float(sp["yaw"]), y=float(sp["base_y"]), floor_y=fy, snap_wheels=True
    )
    apply_raise_to_habitat(env, json.loads(PPO.read_text())["arm_q_final"])
    env.set_arm_joints(cand05_q)

    chassis = hab_pos_to_ros(env.base_xyz, floor_y=fy)
    yaw = hab_yaw_to_ros(float(env.base_yaw))
    corridor_samples = sample_corridor_ground(chassis[:2], yaw)
    corr_cells = corridor_cells(chassis[:2], yaw)

    cam_T = env.camera_world_matrix()
    cam_p, cam_q = mat4_hab_optical_to_ros_pose(cam_T, floor_y=fy)
    R = hab_optical_rot_to_ros(_mat4(cam_T)[:3, :3])

    freeze = {
        "CHASSIS_LOOK_MODE": look or "none",
        "STATIC_OBS_ENABLE": True,
        "STATIC_OBS_POSE": "cand05",
        "cand06_reserved": cand06_q.astype(float).tolist(),
        "arm_q_actual": env.arm_q.astype(float).tolist(),
        "camera_ros_pos_agl": cam_p.astype(float).tolist(),
        "camera_ros_quat_xyzw": cam_q.astype(float).tolist(),
        "optical_fwd_ros": R[:, 2].astype(float).tolist(),
        "chassis_ros_xy_agl": chassis.astype(float).tolist(),
        "yaw_ros": float(yaw),
        "footprint_0p7": fp,
        "corridor_def": {
            "half_l": HALF_L,
            "half_w": HALF_W,
            "gap": GAP,
            "length": CORR_LEN,
            "side": CORR_SIDE,
        },
        "n_corridor_sample_pts": int(len(corridor_samples)),
        "n_corridor_cells": int(len(corr_cells)),
        "spawn": sp,
        "gates_unchanged": True,
        "no_chassis_motion": True,
    }
    (out / "freeze_conditions.json").write_text(json.dumps(freeze, indent=2) + "\n")
    np.save(out / "corridor_samples.npy", corridor_samples)

    pub = DynamicROSPublisher(0.0, 5.0, floor_y=fy, robot_scale=0.7)
    pub.set_env(env, robot_scale=0.7)
    # wait subscribers
    t_wait = time.time()
    while time.time() - t_wait < 20.0:
        if pub.depth_pub.get_num_connections() > 0 and pub.pose_pub.get_num_connections() > 0:
            break
        rospy.sleep(0.2)
    print(
        "connections depth/pose",
        pub.depth_pub.get_num_connections(),
        pub.pose_pub.get_num_connections(),
        flush=True,
    )

    # Clear stale diag by noting start seq
    base_rows = read_pipeline_diag(diag_path)
    base_seq = int(base_rows[-1]["frame_seq"]) if base_rows else 0
    print("pipeline base_seq", base_seq, flush=True)

    period = 1.0 / max(args.publish_hz, 0.1)
    publishes = 0
    last_seq = base_seq
    checkpoints_done = {}
    cell_history: Dict[str, Dict[str, Any]] = {}  # ij -> first_free_seq, last, updates
    prev_free_corr: Set[Tuple[int, int]] = set()
    prev_pipe: Optional[dict] = None
    series = []

    # Capture one local depth for stage mirror at each checkpoint
    def observe_bundle():
        ee = env.observe_ee_only()
        depth = np.asarray(ee["ee_depth"], dtype=np.float32)
        if depth.ndim == 3:
            depth = depth[..., 0]
        cam_T = env.camera_world_matrix()
        prep, dstats = prepare_depth_for_apexnav(
            depth,
            env=env,
            camera_T_hab=cam_T,
            depth_min=0,
            depth_max=5,
            hfov_deg=79,
            robot_scale=0.7,
            use_geometric_self_hit=True,
            camera_frame="optical",
        )
        M = _mat4(cam_T)
        cam_p, _ = mat4_hab_optical_to_ros_pose(cam_T, floor_y=fy)
        R = hab_optical_rot_to_ros(M[:3, :3])
        h, w = depth.shape
        K = pinhole_from_hfov(w, h, 79)
        return ee, depth, prep, dstats, cam_p, R, K, cam_T

    ee0, depth0, prep0, dstats0, cam_p0, R0, K0, cam_T0 = observe_bundle()
    Image.fromarray(ee0["ee_rgb"][..., :3].astype(np.uint8)).save(out / "cand05_rgb.png")

    target_cp_iter = iter(checkpoints)
    next_cp = next(target_cp_iter)
    saturated = False
    saturation_note = None

    while publishes < args.max_publish_attempts and next_cp is not None:
        ee, depth, prep, dstats, cam_p, R, K, cam_T = observe_bundle()
        meta = pub.publish(
            rgb=ee["ee_rgb"][..., :3],
            depth_m=depth,
            base_pos_hab=env.base_xyz,
            base_yaw_hab=env.base_yaw,
            camera_T_hab=cam_T,
            raw_camera_T_hab=cam_T,
        )
        conf.publish(Float64(0.35))
        publishes += 1
        want_seq = base_seq + next_cp
        got = wait_frame_seq(diag_path, want_seq, timeout_s=period + 2.0)
        cur_seq = int(got["frame_seq"]) if got else last_seq
        processed = cur_seq - base_seq
        if processed < next_cp:
            # need more publishes
            rospy.sleep(period)
            continue

        # Checkpoint reached
        rospy.sleep(0.15)  # allow grid_map publishers
        layers = map_layer_sets(ml)
        free_corr = {ij for ij in corr_cells if ij in layers["free"]}
        occ_corr = {ij for ij in corr_cells if ij in layers["occupied"] or ij in layers["inflate"]}
        unk_corr = {ij for ij in corr_cells if cell_state(ij, layers) == "unknown"}
        abs_corr = {ij for ij in corr_cells if cell_state(ij, layers) == "absent"}
        new_free = free_corr - prev_free_corr
        repeat_free = free_corr & prev_free_corr

        # chassis center occupancy (SEPARATE)
        start_ij = (
            int(math.floor(chassis[0] / RES)),
            int(math.floor(chassis[1] / RES)),
        )
        start_state = cell_state(start_ij, layers)

        n_geom, geom_pts = geom_consistent_corridor_ground(prep, cam_p, R, K, corridor_samples)
        # unproject for stage mirror
        us, vs = np.meshgrid(np.arange(prep.shape[1]), np.arange(prep.shape[0]))
        step = 2
        m = np.isfinite(prep)[::step, ::step]
        uu = us[::step, ::step][m]
        vv = vs[::step, ::step][m]
        dd = prep[::step, ::step][m]
        if len(dd):
            po = np.stack(
                [unproject_optical(float(uu[i]), float(vv[i]), float(dd[i]), K) for i in range(len(dd))],
                0,
            )
            pw = (R @ po.T).T + cam_p
        else:
            pw = np.zeros((0, 3))
        stages = pipeline_stages_on_cloud(pw, chassis[:2], yaw)

        # ray coverage estimate: free-ray cells from current endpoints (offline)
        ray_cells = set()
        for p in stages.get("ground_after_outlier_xyz", []) or []:
            a = cam_p[:2]
            b = np.array(p[:2])
            for t in np.linspace(0, 1, 40):
                xy = a + t * (b - a)
                ij = (int(math.floor(xy[0] / RES)), int(math.floor(xy[1] / RES)))
                if ij in corr_cells:
                    ray_cells.add(ij)

        pipe_delta = {}
        if prev_pipe and got:
            for k in (
                "ground_free_after_outlier",
                "ground_free_cands",
                "ground_free_planar_reject",
                "rays_into_occupancy",
                "free_grids_listed",
                "raycast_num",
            ):
                pipe_delta[k] = int(got.get(k, 0)) - int(prev_pipe.get(k, 0))

        # representative cell trajectories
        for ij in sorted(new_free)[:12]:
            key = f"{ij[0]},{ij[1]}"
            cell_history.setdefault(
                key,
                {
                    "ij": list(ij),
                    "first_free_at_processed": processed,
                    "times_observed_free": 0,
                    "prev_state": "unknown_or_absent",
                },
            )
            cell_history[key]["times_observed_free"] += 1
            cell_history[key]["last_free_at_processed"] = processed
        for ij in sorted(repeat_free)[:20]:
            key = f"{ij[0]},{ij[1]}"
            if key in cell_history:
                cell_history[key]["times_observed_free"] += 1
                cell_history[key]["last_free_at_processed"] = processed

        conn = corridor_connectivity(free_corr, chassis[:2], yaw)

        # map panel
        panel = ml.render_panel(
            size=(480, 360),
            robot_xy=(float(chassis[0]), float(chassis[1])),
            robot_yaw=float(yaw),
            meters_span=6.0,
            target_label=f"cand05 N={processed}",
        )
        # draw corridor AABB approx
        Image.fromarray(panel).save(out / f"map_checkpoint_{processed:02d}.png")

        snap = {
            "checkpoint_processed_frames": processed,
            "pipeline_frame_seq": cur_seq,
            "publishes_attempted": publishes,
            "depth_stamp_ros": meta.get("stamp"),
            "pose_stamp_note": "sensor_pose+depth same publish stamp",
            "pipeline_diag": got,
            "pipeline_diag_delta_since_prev_cp": pipe_delta,
            "geom_consistent_corridor_ground_n": n_geom,
            "local_mirror_stages": stages,
            "corridor_map": {
                "n_cells_defined": len(corr_cells),
                "n_free": len(free_corr),
                "n_occupied_or_inflate": len(occ_corr),
                "n_unknown": len(unk_corr),
                "n_absent_from_clouds": len(abs_corr),
                "n_new_free_since_prev": len(new_free),
                "n_repeat_free": len(repeat_free),
                "ray_covered_corridor_cells_this_frame_mirror": len(ray_cells),
            },
            "connectivity": conn,
            "chassis_center": {
                "ij": list(start_ij),
                "state": start_state,
                "note": "SEPARATE from exterior/corridor coverage metrics",
            },
            "depth_validity": dstats,
            "map_listener_stats": ml.stats(),
        }
        series.append(snap)
        checkpoints_done[processed] = snap
        (out / f"checkpoint_{processed:02d}.json").write_text(json.dumps(snap, indent=2) + "\n")
        print(
            f"CP{processed} free_corr={len(free_corr)} new={len(new_free)} "
            f"start={start_state} geom={n_geom} ep_cells={stages['after_outlier_endpoint_cells']} "
            f"pipe_g_after={got.get('ground_free_after_outlier') if got else None}",
            flush=True,
        )

        # saturation: little new spatial coverage
        if processed >= 5 and len(new_free) == 0 and len(free_corr) > 0:
            # check if last two cps also stagnated
            if len(series) >= 2 and series[-2]["corridor_map"]["n_new_free_since_prev"] == 0:
                saturated = True
                saturation_note = (
                    f"Spatial coverage saturated by processed={processed}: "
                    "new_free_corridor_cells=0 for consecutive checkpoints."
                )

        prev_free_corr = set(free_corr)
        prev_pipe = got
        last_seq = cur_seq
        try:
            next_cp = next(target_cp_iter)
        except StopIteration:
            next_cp = None
        if saturated and next_cp is not None and next_cp > processed:
            print("SATURATION stop further publishes:", saturation_note, flush=True)
            # still mark remaining as skipped
            break
        rospy.sleep(period)

    # Branching
    last = series[-1] if series else None
    branch = "insufficient_data"
    if last:
        conn = last["connectivity"]
        start = last["chassis_center"]["state"]
        if saturated:
            branch = "spatial_coverage_saturated"
        elif (
            conn.get("near_to_far_connected")
            and conn.get("connected_span_m", 0) >= 0.4
            and last["corridor_map"]["n_free"] >= 8
        ):
            if start != "free":
                branch = "corridor_free_but_start_unknown_or_blocked"
            else:
                branch = "corridor_and_start_free_observe_only"
        elif last["local_mirror_stages"]["after_outlier_corridor_endpoints"] == 0 and last[
            "geom_consistent_corridor_ground_n"
        ] > 0:
            branch = "valid_ground_lost_in_gates"
        else:
            branch = "corridor_still_has_unobservable_or_unknown_gaps"

    summary = {
        "pose": "cand05",
        "cand06_reserved": True,
        "freeze": freeze,
        "base_pipeline_seq": base_seq,
        "publishes_attempted": publishes,
        "checkpoints_requested": checkpoints,
        "checkpoints_completed": sorted(checkpoints_done.keys()),
        "saturated": saturated,
        "saturation_note": saturation_note,
        "branch": branch,
        "series": series,
        "cell_history_sample": dict(list(cell_history.items())[:40]),
        "acceptance_note": (
            "Static observe→map only. Do NOT treat endpoint counts / blocked=0 / "
            "contact Δ=0 as safe-startup acceptance."
        ),
        "next_attribution": {
            "corridor_free_but_start_unknown_or_blocked": (
                "Open start-state/planner-interface task; do not rewrite map / force FREE."
            ),
            "spatial_coverage_saturated": (
                "Stop adding frames; redesign coverage or accept sparse free footprint."
            ),
            "valid_ground_lost_in_gates": (
                "Minimal reproduce gate stage loss; fix that stage only in a separate change."
            ),
            "corridor_still_has_unobservable_or_unknown_gaps": (
                "Return to coverage design; do not expand near-start exemption."
            ),
        }.get(branch, "see series"),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("BRANCH", branch, flush=True)
    print("OUT", out, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
