#!/usr/bin/env python3
"""Side + onboard views: raised level / LOOK_UP / LOOK_DOWN via teleop-PPO joints.

################################
Uses host-written ppo_look_bundle_model9999/*.json (arm_q_final). Habitat FK cam.
################################
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import magnum as mn
import numpy as np
from PIL import Image, ImageDraw

from src.camera_modes import CAMERA_MODE_LEGACY_ARM_LOOK, activate_camera_mode
from src.constants import ARM_DEFAULT
from src.kinematic_demo import RangerCr10KinematicEnv
from src.ppo_mujoco_raise import apply_raise_to_habitat, habitat_tcp_and_camera_metrics

OUT = Path("/workspace/VLN_Mobilemanipulator/reports/integration_20261122/pose_look_views")
LOOK_DIR = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_look_bundle_model9999")
SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/"
    "00894-HY1NcmCgn3n/HY1NcmCgn3n.basis.glb"
)
BASE_XYZ = [25.869729330758922, 0.3715007912838459, -6.046013830259824]
BASE_YAW = 3.0913963488351746
FLOOR_Y = 0.06218
ROBOT_SCALE = 0.7
GPU = 0


def look_at(eye, target):
    return mn.Matrix4.look_at(
        mn.Vector3(*eye), mn.Vector3(*target), mn.Vector3(0.0, 1.0, 0.0)
    )


def project(T_cam, p_w, W, H, hfov_deg=90.0):
    pc = T_cam.inverted().transform_point(mn.Vector3(*map(float, p_w)))
    if pc.z >= -1e-3:
        return None
    fx = (W / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return W / 2.0 + fx * (pc.x / (-pc.z)), H / 2.0 - fx * (pc.y / (-pc.z))


def optical_axis(env, length=1.2):
    T = env.camera_world_matrix()
    o = np.array([T.translation.x, T.translation.y, T.translation.z], dtype=np.float64)
    R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
    fwd = R[:, 2]
    tip = o + fwd * length
    pitch = math.degrees(math.asin(float(np.clip(fwd[1], -1.0, 1.0))))
    return o, tip, pitch


def annotate(im, lines, axis_uv=None):
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, im.width, 24 * len(lines) + 10], fill=(0, 0, 0))
    y = 4
    for t in lines:
        dr.text((8, y), t, fill=(255, 255, 0))
        y += 22
    if axis_uv:
        (u0, v0), (u1, v1) = axis_uv
        dr.line([u0, v0, u1, v1], fill=(0, 255, 80), width=5)
        dr.ellipse([u0 - 8, v0 - 8, u0 + 8, v0 + 8], outline=(255, 0, 0), width=3)
        dr.ellipse([u1 - 10, v1 - 10, u1 + 10, v1 + 10], outline=(0, 255, 80), width=3)
        dr.text((u1 + 12, v1 - 8), "optical +Z", fill=(0, 255, 80))
    return im


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    targets = {}
    for name in ("look_level", "look_up", "look_down"):
        p = LOOK_DIR / f"{name}.json"
        if not p.is_file():
            raise FileNotFoundError(p)
        targets[name] = json.loads(p.read_text())["arm_q_final"]

    env = RangerCr10KinematicEnv(
        scene=SCENE, robot_scale=ROBOT_SCALE, gpu_device_id=GPU, enable_physics=True
    )
    env.floor_y = FLOOR_Y
    env.set_base_pose(
        BASE_XYZ[0],
        BASE_XYZ[2],
        BASE_YAW,
        y=FLOOR_Y + env.default_base_y,
        floor_y=FLOOR_Y,
        snap_wheels=True,
    )
    activate_camera_mode(env, CAMERA_MODE_LEGACY_ARM_LOOK, freeze_arm=False)

    x, y, z = map(float, env.base_xyz)
    yaw = float(env.base_yaw)
    fwd = np.array([math.sin(yaw), 0.0, math.cos(yaw)])
    right = np.array([math.cos(yaw), 0.0, -math.sin(yaw)])
    up = np.array([0.0, 1.0, 0.0])
    base = np.array([x, y, z])
    look_tgt = (base + up * 0.55).tolist()
    eye_side = (base + right * 3.5 + up * 1.9 - fwd * 0.25).tolist()

    meta = {"look_dir": str(LOOK_DIR), "states": []}
    # ################################
    # Labels = optical intent (ee pitch sign is opposite; see look_offset_rpy).
    # ################################
    for name, label in (
        ("look_level", "PPO raised LEVEL (z_hold, rpy=0)"),
        ("look_up", "PPO LOOK_UP (optical ~+30deg)"),
        ("look_down", "PPO LOOK_DOWN (optical ~-30deg)"),
    ):
        apply_raise_to_habitat(env, targets[name])
        o, tip, pitch = optical_axis(env)
        cam = habitat_tcp_and_camera_metrics(env)

        # ################################
        # Must observe_ee_only(): sync_agent_sensors only fills _ee_T;
        # without _set_agent_pose, ee_rgb stays at stale/default (floor) pose.
        # ################################
        ee = Image.fromarray(env.observe_ee_only()["ee_rgb"][..., :3]).convert("RGB")
        annotate(
            ee,
            [
                f"{label} | ee_rgb (onboard)",
                f"optical≈{pitch:+.1f}deg cam_AGL≈{cam['d455_optical_agl_m']:.3f}m",
                "trained teleop-PPO EE orient | model_9999",
            ],
        ).save(OUT / f"ppo_{name}_ee_rgb.png")

        T = look_at(eye_side, look_tgt)
        env._set_agent_pose(T)
        rgb = env.sim.get_sensor_observations()["third_rgb"][..., :3]
        im = Image.fromarray(rgb).convert("RGB")
        W, H = im.size
        a = project(T, o, W, H)
        b = project(T, tip, W, H)
        annotate(
            im,
            [
                f"{label} | SIDE",
                f"optical≈{pitch:+.1f}deg cam_AGL≈{cam['d455_optical_agl_m']:.3f}m",
                "green=optical +Z; arm joints from teleop-PPO (not gimbal)",
            ],
            (a, b) if a and b else None,
        ).save(OUT / f"ppo_{name}_side.png")
        print("wrote", name, "pitch", pitch, "agl", cam["d455_optical_agl_m"])
        meta["states"].append(
            {
                "name": name,
                "optical_pitch_deg": pitch,
                "cam_agl_m": cam["d455_optical_agl_m"],
                "arm_q": targets[name],
            }
        )

    # also ARM_DEFAULT side for reference
    apply_raise_to_habitat(env, list(ARM_DEFAULT))
    o, tip, pitch = optical_axis(env)
    cam = habitat_tcp_and_camera_metrics(env)
    T = look_at(eye_side, look_tgt)
    env._set_agent_pose(T)
    rgb = env.sim.get_sensor_observations()["third_rgb"][..., :3]
    im = Image.fromarray(rgb).convert("RGB")
    W, H = im.size
    a = project(T, o, W, H)
    b = project(T, tip, W, H)
    annotate(
        im,
        [
            "ARM_DEFAULT (before PPO raise) | SIDE",
            f"optical≈{pitch:+.1f}deg cam_AGL≈{cam['d455_optical_agl_m']:.3f}m",
            "reference compact-ish home before Z-raise + LOOK",
        ],
        (a, b) if a and b else None,
    ).save(OUT / "ppo_arm_default_side.png")

    (OUT / "ppo_look_capture_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    env.close()
    print("DONE", OUT)


if __name__ == "__main__":
    main()
