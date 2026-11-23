#!/usr/bin/env python3
"""Compare: ARM_DEFAULT+gimbal LOOK_UP vs PPO model_9999 arm raise (real EE lift).

################################
User requirement: 抬相机 should use trained teleop-PPO weights (model_9999),
which lifts the arm end-effector — NOT simulated gimbal pitch alone.
################################
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import magnum as mn
import numpy as np
from PIL import Image, ImageDraw

from src.camera_modes import (
    CAMERA_MODE_FIXED_BASE_GIMBAL,
    CAMERA_MODE_LEGACY_ARM_LOOK,
    activate_camera_mode,
    apply_gimbal_look,
)
from src.constants import ARM_DEFAULT, DEFAULT_TELEOP_CKPT
from src.kinematic_demo import RangerCr10KinematicEnv

OUT = Path("/workspace/VLN_Mobilemanipulator/reports/integration_20261122/pose_look_views")
SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/"
    "00894-HY1NcmCgn3n/HY1NcmCgn3n.basis.glb"
)
# Open-room framing (hy1 step95 SE2)
BASE_XYZ = [25.869729330758922, 0.3715007912838459, -6.046013830259824]
BASE_YAW = 3.0913963488351746
FLOOR_Y = 0.06218
ROBOT_SCALE = 0.7
GPU = 0

# Published raise handover (Habitat 0.7× joints after MuJoCo teleop-PPO +Z).
# Source run used stage410d raise json; contract same as model_9999 teleop raise.
RAISE_JSON = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json")
HANDOVER = Path(
    "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/"
    "real_s070_pporaise_hy1_failframe_20261106_181431/ppo_raise/handover.json"
)


def look_at(eye, target) -> mn.Matrix4:
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


def shoot(env, eye, tgt, o, tip, lines, path):
    T = look_at(eye, tgt)
    env._set_agent_pose(T)
    rgb = env.sim.get_sensor_observations()["third_rgb"][..., :3]
    im = Image.fromarray(rgb).convert("RGB")
    W, H = im.size
    a = project(T, o, W, H)
    b = project(T, tip, W, H)
    annotate(im, lines, (a, b) if a and b else None).save(path)
    print("wrote", path.name)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    raise_rep = json.loads(RAISE_JSON.read_text())
    hand = json.loads(HANDOVER.read_text())
    arm_raised = list(hand["habitat_handover"]["arm_q"])
    assert len(arm_raised) == 6

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
    x, y, z = map(float, env.base_xyz)
    yaw = float(env.base_yaw)
    fwd = np.array([math.sin(yaw), 0.0, math.cos(yaw)])
    right = np.array([math.cos(yaw), 0.0, -math.sin(yaw)])
    up = np.array([0.0, 1.0, 0.0])
    base = np.array([x, y, z])
    look_tgt = (base + up * 0.55).tolist()
    eye_side = (base + right * 3.4 + up * 1.9 - fwd * 0.3).tolist()
    eye_obl = (base - fwd * 3.0 - right * 2.2 + up * 2.2).tolist()

    meta = {
        "DEFAULT_TELEOP_CKPT": DEFAULT_TELEOP_CKPT,
        "raise_json": str(RAISE_JSON),
        "handover": str(HANDOVER),
        "arm_default": list(ARM_DEFAULT),
        "arm_ppo_raised": arm_raised,
        "raise_policy_field": raise_rep.get("policy"),
        "d455_agl_after_raise_m": hand["habitat_handover"].get("d455_optical_agl_m"),
        "tcp_agl_after_raise_m": hand["habitat_handover"].get("tcp_agl_m"),
        "states": [],
    }

    # ----- A) ARM_DEFAULT + gimbal LOOK_UP (current ApexNav LOOK — NO weight) -----
    env.set_arm_joints(list(ARM_DEFAULT))
    activate_camera_mode(env, CAMERA_MODE_FIXED_BASE_GIMBAL, freeze_arm=True)
    apply_gimbal_look(env, "up")
    o, tip, pitch = optical_axis(env)
    for tag, eye in (("side_R", eye_side), ("oblique", eye_obl)):
        shoot(
            env,
            eye,
            look_tgt,
            o,
            tip,
            [
                f"GIMBAL LOOK_UP only | {tag}",
                f"optical≈{pitch:+.1f}deg cam_AGL≈{o[1]-FLOOR_Y:.3f}m | arm STILL ARM_DEFAULT",
                "NOT using trained weights — pitch-only simulated gimbal",
            ],
            OUT / f"compare_gimbal_lookup_{tag}.png",
        )
    meta["states"].append(
        {
            "name": "gimbal_look_up",
            "uses_trained_weights": False,
            "cam_agl_m": float(o[1] - FLOOR_Y),
            "optical_pitch_deg": pitch,
            "arm_q": list(map(float, env.arm_q)),
        }
    )

    # ----- B) PPO raise: lift EE with trained teleop policy joints -----
    env.gimbal_pitch = 0.0
    env.set_arm_joints(arm_raised)
    # Optical follows FK (raised mount), not frozen ARM_DEFAULT gimbal mount.
    activate_camera_mode(env, CAMERA_MODE_LEGACY_ARM_LOOK, freeze_arm=False)
    o, tip, pitch = optical_axis(env)
    for tag, eye in (("side_R", eye_side), ("oblique", eye_obl)):
        shoot(
            env,
            eye,
            look_tgt,
            o,
            tip,
            [
                f"PPO RAISE (trained weights) | {tag}",
                f"optical≈{pitch:+.1f}deg cam_AGL≈{o[1]-FLOOR_Y:.3f}m | arm RAISED by teleop-PPO",
                f"ckpt={DEFAULT_TELEOP_CKPT} | EE lifted (not gimbal-only)",
            ],
            OUT / f"compare_ppo_raise_{tag}.png",
        )
    meta["states"].append(
        {
            "name": "ppo_raise",
            "uses_trained_weights": True,
            "cam_agl_m": float(o[1] - FLOOR_Y),
            "optical_pitch_deg": pitch,
            "arm_q": arm_raised,
        }
    )

    (OUT / "compare_ppo_vs_gimbal_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    env.close()
    print("DONE", OUT)


if __name__ == "__main__":
    main()
