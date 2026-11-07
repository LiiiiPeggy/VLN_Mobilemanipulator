#!/usr/bin/env python3
"""Diagnose where corridor ground is lost in the production gate chain.

Tracks lookdown_C (prior 62→0) and cand05 (3 surviving endpoints) stage-by-stage.
Does NOT relax thresholds. Offline Habitat only — no map write.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from src.camera_model import pinhole_from_hfov, unproject_optical
from src.coord_habitat_ros import (
    hab_optical_rot_to_ros,
    hab_pos_to_ros,
    hab_yaw_to_ros,
    mat4_hab_optical_to_ros_pose,
)
from src.depth_validity import prepare_depth_for_apexnav
from src.kinematic_demo import RangerCr10KinematicEnv
from src.ppo_mujoco_raise import apply_raise_to_habitat

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
HALF_L, HALF_W = 0.4557, 0.30429
GAP, CORR_LEN, CORR_SIDE = 0.05, 0.80, 0.05


def _mat4(T):
    M = np.eye(4)
    M[:3, :3] = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
    M[:3, 3] = [T.translation.x, T.translation.y, T.translation.z]
    return M


def corridor_mask(pw: np.ndarray, chassis_xy: np.ndarray, yaw: float) -> np.ndarray:
    if len(pw) == 0:
        return np.zeros(0, dtype=bool)
    c, s = math.cos(yaw), math.sin(yaw)
    d = pw[:, :2] - chassis_xy.reshape(1, 2)
    bx = c * d[:, 0] + s * d[:, 1]
    by = -s * d[:, 0] + c * d[:, 1]
    return (
        (bx >= HALF_L + GAP)
        & (bx <= HALF_L + GAP + CORR_LEN)
        & (np.abs(by) <= HALF_W + CORR_SIDE)
    )


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


def voxel_downsample(pts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return downsampled pts and mapping count per kept voxel (approx)."""
    if len(pts) == 0:
        return pts, np.zeros(0, dtype=np.int64)
    keys = np.stack(
        [
            np.floor(pts[:, 0] / VOXEL_XY).astype(np.int64),
            np.floor(pts[:, 1] / VOXEL_XY).astype(np.int64),
            np.floor(pts[:, 2] / VOXEL_Z).astype(np.int64),
        ],
        1,
    )
    uniq, inv, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    # keep first of each
    _, idx = np.unique(keys, axis=0, return_index=True)
    order = np.sort(idx)
    # counts aligned to uniq order of first appearance via inv
    kept_counts = []
    for i in order:
        kept_counts.append(int(counts[inv[i]]))
    return pts[order], np.asarray(kept_counts, dtype=np.int64)


def radius_outlier_keep_mask(cloud: np.ndarray) -> np.ndarray:
    keep = np.zeros(len(cloud), dtype=bool)
    r2 = OUTLIER_R * OUTLIER_R
    for i, p in enumerate(cloud):
        n = 0
        for j, q in enumerate(cloud):
            if i == j:
                continue
            if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 <= r2:
                n += 1
                if n >= OUTLIER_MIN:
                    keep[i] = True
                    break
    return keep


def capture_cloud(env, q, fy):
    env.set_arm_joints(q)
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
    us, vs = np.meshgrid(np.arange(w), np.arange(h))
    step = 2
    m = np.isfinite(prep)[::step, ::step]
    uu = us[::step, ::step][m]
    vv = vs[::step, ::step][m]
    dd = prep[::step, ::step][m]
    if len(dd) == 0:
        pw = np.zeros((0, 3))
    else:
        po = np.stack(
            [unproject_optical(float(uu[i]), float(vv[i]), float(dd[i]), K) for i in range(len(dd))],
            0,
        )
        pw = (R @ po.T).T + cam_p
    return pw, dstats, cam_p


def stage_trace(pw: np.ndarray, chassis_xy: np.ndarray, yaw: float) -> Dict[str, Any]:
    stages: Dict[str, Any] = {}
    cm = corridor_mask(pw, chassis_xy, yaw)
    corr = pw[cm]
    stages["0_world_cloud_n"] = int(len(pw))
    stages["1_corridor_xy_n"] = int(len(corr))
    # AGL ground band in corridor
    gband = corr[(corr[:, 2] >= 0.0) & (corr[:, 2] <= GROUND_FREE_MAX_AGL)]
    low = corr[(corr[:, 2] > GROUND_FREE_MAX_AGL) & (corr[:, 2] <= FILTER_MIN)]
    obst = corr[(corr[:, 2] > FILTER_MIN) & (corr[:, 2] < 1.18)]
    other = len(corr) - len(gband) - len(low) - len(obst)
    stages["2_corridor_agl"] = {
        "ground_0_0p03": int(len(gband)),
        "low_0p03_0p28": int(len(low)),
        "obstacle_band": int(len(obst)),
        "other_or_neg": int(other),
        "frac_neg_in_corridor": float((corr[:, 2] < 0).mean()) if len(corr) else None,
    }
    # Voxel on full cloud then re-select corridor (matches production order)
    down, _ = voxel_downsample(pw)
    cm_d = corridor_mask(down, chassis_xy, yaw)
    down_corr = down[cm_d]
    stages["3_after_voxel"] = {
        "full_n": int(len(down)),
        "corridor_n": int(len(down_corr)),
        "corridor_ground_0_0p03": int(
            ((down_corr[:, 2] >= 0) & (down_corr[:, 2] <= GROUND_FREE_MAX_AGL)).sum()
        )
        if len(down_corr)
        else 0,
    }
    # Planar on provisional ground indices in FULL down cloud
    prov = []
    for i in range(len(down)):
        z = float(down[i, 2])
        if 0.0 <= z <= GROUND_FREE_MAX_AGL:
            prov.append(i)
    planar_ok, planar_rej = [], []
    for i in prov:
        if is_planar(down, i):
            planar_ok.append(i)
        else:
            planar_rej.append(i)
    ground_pts = down[planar_ok] if planar_ok else down[:0]
    cm_g = corridor_mask(ground_pts, chassis_xy, yaw) if len(ground_pts) else np.zeros(0, bool)
    stages["4_planar"] = {
        "provisional_ground_full": int(len(prov)),
        "planar_ok_full": int(len(planar_ok)),
        "planar_reject_full": int(len(planar_rej)),
        "planar_ok_in_corridor": int(cm_g.sum()) if len(cm_g) else 0,
    }
    # Outlier on ground_pts
    keep = radius_outlier_keep_mask(ground_pts) if len(ground_pts) else np.zeros(0, bool)
    after = ground_pts[keep] if len(ground_pts) else ground_pts
    cm_a = corridor_mask(after, chassis_xy, yaw) if len(after) else np.zeros(0, bool)
    stages["5_outlier"] = {
        "ground_before": int(len(ground_pts)),
        "ground_after": int(len(after)),
        "dropped": int(len(ground_pts) - len(after)),
        "corridor_before": int(cm_g.sum()) if len(cm_g) else 0,
        "corridor_after": int(cm_a.sum()) if len(cm_a) else 0,
    }
    # Earliest loss attribution for corridor ground
    loss_path = []
    n = stages["2_corridor_agl"]["ground_0_0p03"]
    loss_path.append(("corridor_raw_ground_agl", n))
    n2 = stages["3_after_voxel"]["corridor_ground_0_0p03"]
    loss_path.append(("after_voxel_corridor_ground", n2))
    n3 = stages["4_planar"]["planar_ok_in_corridor"]
    loss_path.append(("after_planar_corridor", n3))
    n4 = stages["5_outlier"]["corridor_after"]
    loss_path.append(("after_outlier_corridor", n4))
    earliest = None
    prev = None
    for name, v in loss_path:
        if prev is not None and v < prev and earliest is None:
            earliest = {"stage": name, "from": prev, "to": v, "delta": prev - v}
        prev = v
    if n > 0 and n4 == 0 and earliest is None:
        # find largest drop
        drops = []
        for i in range(1, len(loss_path)):
            a, b = loss_path[i - 1][1], loss_path[i][1]
            if b < a:
                drops.append((loss_path[i][0], a, b, a - b))
        if drops:
            drops.sort(key=lambda t: -t[3])
            earliest = {
                "stage": drops[0][0],
                "from": drops[0][1],
                "to": drops[0][2],
                "delta": drops[0][3],
            }
    stages["loss_path"] = [{"name": a, "n": b} for a, b in loss_path]
    stages["earliest_corridor_ground_loss"] = earliest
    stages["endpoint_cells_after_outlier"] = int(
        len(
            {
                (int(round(p[0] / 0.05)), int(round(p[1] / 0.05)))
                for p in after[cm_a]
            }
        )
    ) if len(after) and cm_a.any() else 0
    return stages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default="/workspace/VLN_Mobilemanipulator/reports/hy1_cand05_static_multiframe_20261106",
    )
    ap.add_argument("--gpu", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = json.loads(GEOM.read_text())
    cand05 = np.array([r for r in rows if r["tag"] == "cand05"][0]["arm_q"], float)
    sp = json.loads(SPAWN.read_text())["spawn"]
    env = RangerCr10KinematicEnv(scene=SCENE, gpu_device_id=args.gpu, robot_scale=0.7)
    fy = float(sp["floor_y"])
    env.floor_y = fy
    env.set_base_pose(
        float(sp["x"]), float(sp["z"]), float(sp["yaw"]), y=float(sp["base_y"]), floor_y=fy, snap_wheels=True
    )
    apply_raise_to_habitat(env, json.loads(PPO.read_text())["arm_q_final"])
    q0 = env.arm_q.copy()
    q_c = q0.copy()
    q_c[2] -= 0.60
    chassis = hab_pos_to_ros(env.base_xyz, floor_y=fy)[:2]
    yaw = hab_yaw_to_ros(float(env.base_yaw))

    report = {"spawn": sp, "chassis_ros_xy": chassis.tolist(), "yaw_ros": yaw, "poses": {}}
    for tag, q in (("lookdown_C", q_c), ("cand05", cand05)):
        pw, dstats, cam = capture_cloud(env, q, fy)
        st = stage_trace(pw, chassis, yaw)
        report["poses"][tag] = {
            "arm_q": q.astype(float).tolist(),
            "cam_ros": cam.tolist(),
            "depth_validity": dstats,
            "stages": st,
        }
        print(tag, json.dumps(st["loss_path"]), "earliest", st["earliest_corridor_ground_loss"], flush=True)

    (out / "gate_stage_loss_diag.json").write_text(json.dumps(report, indent=2) + "\n")
    print("OUT", out / "gate_stage_loss_diag.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
