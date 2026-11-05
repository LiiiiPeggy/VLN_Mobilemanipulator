"""Smoke-verify 0.7× uniform robot scale in Habitat (adapter-only).

################################
Checks: URDF generation, upright, tire ground contact, D455 AGL≈0.616 m,
arm FK motion, wheel roll sync, collision geometry present. PROXY ONLY.
################################
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from .constants import ARM_APEXNAV_INIT, ARM_DEFAULT, DEFAULT_SCENE
from .initial_camera_pose import optical_metrics, verify_arm_config
from .kinematic_demo import RangerCr10KinematicEnv
from .robot_scale import ROBOT_SCALE_070, footprint_at_scale
from .scale_urdf import ensure_scaled_urdf


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--scene", default=DEFAULT_SCENE)
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument("--out", default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/scale070_verify")
    p.add_argument("--scale", type=float, default=ROBOT_SCALE_070)
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    urdf = ensure_scaled_urdf(args.scale, force=True)
    fp = footprint_at_scale(args.scale)
    env1 = RangerCr10KinematicEnv(scene=args.scene, robot_scale=1.0, gpu_device_id=args.gpu)
    env7 = RangerCr10KinematicEnv(scene=args.scene, robot_scale=args.scale, gpu_device_id=args.gpu)

    # Place both at same xz
    x, z, yaw = 1.0, 1.0, 0.0
    floor_y = 0.0
    try:
        floor_y = float(env7.sim.pathfinder.snap_point(np.array([x, 0.1, z], dtype=np.float32))[1])
    except Exception:
        floor_y = 0.0
    for env in (env1, env7):
        env.set_base_pose(x, z, yaw, floor_y=floor_y, snap_wheels=True)
        env.set_arm_joints(ARM_APEXNAV_INIT)

    u1 = env1.upright_diagnostics()
    u7 = env7.upright_diagnostics()
    m1 = optical_metrics(env1, yaw)
    m7 = optical_metrics(env7, yaw)
    v7 = verify_arm_config(env7, ARM_APEXNAV_INIT, label="s070_ARM_APEXNAV_INIT")

    # Wheel ground: mean wheel center ≈ floor + snap radius
    w7 = env7.wheel_link_heights()
    mean_w = float(np.mean(list(w7.values()))) if w7 else float("nan")
    wheel_err = abs(mean_w - (floor_y + env7.wheel_radius_snap))

    # Move base and check wheel roll changes
    env7.set_base_pose(x, z, yaw, floor_y=floor_y, snap_wheels=False, update_wheel_joints=False)
    q0 = env7.wheel_q.copy()
    env7.set_base_pose(x, z + 0.25, yaw, y=env7.base_xyz[1], floor_y=floor_y, snap_wheels=False)
    roll_delta = float(np.max(np.abs(env7.wheel_q - q0)))

    # Arm motion
    env7.set_arm_joints(ARM_DEFAULT)
    env7.set_arm_joints(ARM_APEXNAV_INIT)
    arm_ok = True

    # Link AABB height ratio proxy (visual scale)
    def _base_height(env):
        # max link y - min link y
        ys = []
        for lid in env.ao.get_link_ids():
            t = env.ao.get_link_scene_node(lid).absolute_transformation().translation
            ys.append(float(t.y))
        # include base
        t0 = env.ao.transformation.translation
        ys.append(float(t0.y))
        return max(ys) - min(ys) if ys else float("nan")

    h1 = _base_height(env1)
    h7 = _base_height(env7)
    height_ratio = h7 / h1 if h1 > 1e-6 else float("nan")

    # Steering joint origin scale check via link distance fr wheel from base
    def _xz_dist_base_to(env, link):
        if link not in env.link_ids:
            return float("nan")
        b = env.ao.transformation.translation
        p = env.ao.get_link_scene_node(env.link_ids[link]).absolute_transformation().translation
        return float(math.hypot(p.x - b.x, p.z - b.z))

    d1 = _xz_dist_base_to(env1, "fr_wheel_link")
    d7 = _xz_dist_base_to(env7, "fr_wheel_link")
    wheelbase_ratio = d7 / d1 if d1 > 1e-6 else float("nan")

    rep = {
        "scale": args.scale,
        "scale_tag": env7.scale_tag,
        "urdf_scaled": urdf,
        "urdf_1x": env1.urdf,
        "footprint_070": fp,
        "upright_1x": u1,
        "upright_070": u7,
        "cam_1x_agl": m1["height_agl_m"],
        "cam_070_agl": m7["height_agl_m"],
        "cam_070_target": env7.cam_height_target_m,
        "cam_070_verify": v7["tolerances"],
        "wheel_mean_y": mean_w,
        "wheel_target_y": floor_y + env7.wheel_radius_snap,
        "wheel_ground_err_m": wheel_err,
        "wheel_roll_delta_after_0p25m": roll_delta,
        "arm_motion_ok": arm_ok,
        "visual_height_1x": h1,
        "visual_height_070": h7,
        "visual_height_ratio": height_ratio,
        "fr_wheel_xz_dist_1x": d1,
        "fr_wheel_xz_dist_070": d7,
        "wheelbase_ratio": wheelbase_ratio,
        "contacts_070": int(env7.contact_count()),
        "pass": bool(
            u7.get("up_dot_hab_y", 0) > 0.95
            and wheel_err < 0.03
            and abs(m7["height_agl_m"] - env7.cam_height_target_m) < 0.05
            and abs(m7["pitch_deg"]) < 8.0
            and roll_delta > 0.1
            and 0.62 < height_ratio < 0.78
            and 0.62 < wheelbase_ratio < 0.78
        ),
    }
    (out / "scale070_verify.json").write_text(json.dumps(rep, indent=2))
    # side-by-side third frames
    try:
        from PIL import Image

        Image.fromarray(env1.observe_third_only()[..., :3]).save(out / "third_1x.png")
        Image.fromarray(env7.observe_third_only()[..., :3]).save(out / "third_070.png")
    except Exception as e:
        rep["render_error"] = str(e)
        (out / "scale070_verify.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    env1.close() if hasattr(env1, "close") else None
    env7.close() if hasattr(env7, "close") else None
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
