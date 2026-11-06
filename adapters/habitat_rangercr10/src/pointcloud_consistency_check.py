"""Same static 3D point consistency under base/arm motion (adapter diagnostic).

################################
Uses ONE world point chosen at init (center pixel unprojected via OPTICAL pose),
then reprojects that same point into later views. Does NOT treat different
center image patches as the same object. Does NOT feed GT into ApexNav.
################################
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

from .camera_model import pinhole_from_hfov, project_optical, unproject_optical
from .constants import DEFAULT_OUT_DIR, DEFAULT_SCENE, URDF_HABITAT
from .initial_camera_pose import apply_and_record_initial_camera
from .kinematic_demo import DEFAULT_BASE_Y, RangerCr10KinematicEnv
from .pointcloud_dynamic import object_clouds_from_masks


def _optical_Rp(env):
    T = env.camera_world_matrix()
    R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
    p = np.array([T.translation.x, T.translation.y, T.translation.z], dtype=np.float64)
    return R, p


def _world_from_optical(R_hab, p_hab, p_opt):
    return R_hab @ p_opt + p_hab


def _project_world_to_optical_uv(R_hab, p_hab, p_w, K):
    R_cw = R_hab.T
    t_cw = -R_cw @ p_hab
    p_opt = R_cw @ p_w + t_cw
    if p_opt[2] <= 1e-6:
        return float("nan"), float("nan"), float(p_opt[2])
    u, v = project_optical(p_opt, K)
    return u, v, float(p_opt[2])


def run(args: argparse.Namespace) -> dict:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    env = RangerCr10KinematicEnv(scene=args.scene, urdf=args.urdf, gpu_device_id=args.gpu)
    env.set_base_pose(args.x, args.z, 0.0, y=DEFAULT_BASE_Y)
    apply_and_record_initial_camera(env, out / "camera_init")

    obs0 = env.observe_ee_only()
    depth0 = np.asarray(obs0["ee_depth"], dtype=np.float32)
    if depth0.ndim == 3:
        depth0 = depth0[..., 0]
    h, w = depth0.shape
    K = pinhole_from_hfov(w, h, 79.0)
    u0, v0 = w / 2.0, h / 2.0
    d0 = float(depth0[int(v0), int(u0)])
    R0, p0 = _optical_Rp(env)
    if not np.isfinite(d0) or d0 < 0.2:
        # fall back: scan for a finite center neighborhood depth
        d0 = float("nan")
        for rad in range(0, 40):
            for vv in range(max(0, int(v0) - rad), min(h, int(v0) + rad + 1)):
                for uu in range(max(0, int(u0) - rad), min(w, int(u0) + rad + 1)):
                    dd = float(depth0[vv, uu])
                    if np.isfinite(dd) and dd > 0.2:
                        u0, v0, d0 = float(uu), float(vv), dd
                        break
                if np.isfinite(d0):
                    break
            if np.isfinite(d0):
                break
    if not np.isfinite(d0):
        summary = {"status": "fail", "error": "no_finite_seed_depth"}
        (out / "summary.json").write_text(json.dumps(summary, indent=2))
        return summary

    p_opt0 = unproject_optical(u0, v0, d0, K)
    p_world = _world_from_optical(R0, p0, p_opt0)
    # also project a 3×3 mask around seed for cloud sanity (optical pose)
    mask = np.zeros((h, w), dtype=np.uint8)
    ui, vi = int(u0), int(v0)
    mask[max(0, vi - 1) : vi + 2, max(0, ui - 1) : ui + 2] = 1
    clouds0 = object_clouds_from_masks(depth0, [mask], env.camera_world_matrix(), hfov_deg=79.0)

    records = []
    for tag, mover in [
        ("init", None),
        ("after_base_forward", lambda: env.set_base_pose(args.x, args.z + 0.25, 0.0, y=DEFAULT_BASE_Y)),
        (
            "after_arm_look",
            lambda: env.set_arm_joints(
                list(env.arm_q[:4]) + [float(np.clip(env.arm_q[4] + 0.2, -2, 2))] + [env.arm_q[5]]
            ),
        ),
    ]:
        if mover:
            mover()
        obs = env.observe_ee_only()
        rgb, depth = obs["ee_rgb"], obs["ee_depth"]
        Image.fromarray(rgb[..., :3]).save(out / f"{tag}_rgb.png")
        R, p = _optical_Rp(env)
        uu, vv, z_cam = _project_world_to_optical_uv(R, p, p_world, K)
        records.append(
            {
                "tag": tag,
                "reproject_uv": [uu, vv],
                "optical_z": z_cam,
                "cam_pos_hab": p.tolist(),
                "arm": env.arm_q.tolist(),
                "base": env.base_xyz.tolist() + [env.base_yaw],
            }
        )

    drifts = {}
    u_ref, v_ref = records[0]["reproject_uv"]
    for r in records[1:]:
        uu, vv = r["reproject_uv"]
        drifts[r["tag"]] = {
            "du_px": None if not np.isfinite(uu) else float(uu - u_ref),
            "dv_px": None if not np.isfinite(vv) else float(vv - v_ref),
            "pixel_err": None
            if not (np.isfinite(uu) and np.isfinite(vv))
            else float(math.hypot(uu - u_ref, vv - v_ref)),
        }
    summary = {
        "status": "ok",
        "method": "same_world_point_reprojection",
        "seed_uvd": [u0, v0, d0],
        "seed_world_hab": p_world.tolist(),
        "seed_cloud_width": int(getattr(clouds0[0], "width", 0) or 0),
        "records": records,
        "drifts_vs_init_px": drifts,
        "note": (
            "Same Habitat world point reprojected via OPTICAL FK+K. "
            "Not center-patch-as-same-object."
        ),
        "out_dir": str(out),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    try:
        env.close()
    except Exception:
        pass
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--urdf", default=URDF_HABITAT)
    p.add_argument("--out_dir", default=os.path.join(DEFAULT_OUT_DIR, "pc_consistency"))
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument("--x", type=float, default=1.0)
    p.add_argument("--z", type=float, default=1.0)
    args = p.parse_args()
    print(json.dumps(run(args), indent=2))


if __name__ == "__main__":
    main()
