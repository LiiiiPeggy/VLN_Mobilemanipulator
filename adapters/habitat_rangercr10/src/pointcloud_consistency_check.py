"""Static-object 3D consistency under base/arm motion (adapter diagnostic).

Projects a fixed image patch through dynamic EE FK before/after a base move and
an arm tweak; records Euclidean drift. Does NOT feed GT into ApexNav.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image

from .constants import ARM_APEXNAV_INIT, DEFAULT_OUT_DIR, DEFAULT_SCENE, URDF_HABITAT
from .initial_camera_pose import apply_and_record_initial_camera
from .kinematic_demo import DEFAULT_BASE_Y, RangerCr10KinematicEnv
from .pointcloud_dynamic import object_clouds_from_masks


def _center_patch_mask(h: int, w: int, size: int = 40) -> np.ndarray:
    m = np.zeros((h, w), dtype=np.uint8)
    cy, cx = h // 2, w // 2
    m[cy - size // 2 : cy + size // 2, cx - size // 2 : cx + size // 2] = 1
    return m


def _cloud_centroid(pc_msg) -> np.ndarray:
    raw = np.frombuffer(pc_msg.data, dtype=np.float32)
    if raw.size < 4:
        return np.array([np.nan, np.nan, np.nan])
    pts = raw.reshape(-1, 4)[:, :3]
    if pts.shape[0] == 0:
        return np.array([np.nan, np.nan, np.nan])
    return pts.mean(axis=0)


def run(args: argparse.Namespace) -> dict:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    env = RangerCr10KinematicEnv(scene=args.scene, urdf=args.urdf, gpu_device_id=args.gpu)
    env.set_base_pose(args.x, args.z, 0.0, y=DEFAULT_BASE_Y)
    apply_and_record_initial_camera(env, out / "camera_init")

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
        h, w = depth.shape[:2]
        mask = _center_patch_mask(h, w)
        clouds = object_clouds_from_masks(depth, [mask], obs["ee_T"], hfov_deg=79.0)
        c = _cloud_centroid(clouds[0])
        T = env.camera_world_matrix()
        records.append(
            {
                "tag": tag,
                "centroid_ros": c.tolist(),
                "cam_pos": [T.translation.x, T.translation.y, T.translation.z],
                "arm": env.arm_q.tolist(),
                "base": env.base_xyz.tolist() + [env.base_yaw],
            }
        )

    c0 = np.array(records[0]["centroid_ros"])
    drifts = {}
    for r in records[1:]:
        c = np.array(r["centroid_ros"])
        drifts[r["tag"]] = {
            "delta_m": (c - c0).tolist(),
            "norm_m": float(np.linalg.norm(c - c0)) if np.isfinite(c).all() else None,
        }
    summary = {
        "status": "ok",
        "records": records,
        "drifts_vs_init": drifts,
        "note": "Center-patch proxy; large drift may indicate projection/frame bugs.",
        "out_dir": str(out),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    env.close()
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
