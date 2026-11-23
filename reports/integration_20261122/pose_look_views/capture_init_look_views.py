#!/usr/bin/env python3
"""Capture side/top of ApexNav fixed_base_gimbal init / LOOK_UP / LOOK_DOWN.

################################
Fix vs prior: do NOT shift base for framing; use real spawn + clear
external eyes (same family as stop_fix preferred_alt) so the full
0.7× chassis+ARM_DEFAULT is visible. LOOK only changes gimbal pitch.
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
    activate_camera_mode,
    apply_gimbal_look,
    camera_mode_summary,
)
from src.constants import ARM_DEFAULT
from src.kinematic_demo import RangerCr10KinematicEnv

OUT = Path("/workspace/VLN_Mobilemanipulator/reports/integration_20261122/pose_look_views")
SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/"
    "00894-HY1NcmCgn3n/HY1NcmCgn3n.basis.glb"
)
# ################################
# Spawn corridor is too tight for third-person (eye lands in furniture).
# Use hy1 yaw-aware step95 SE(2) — proven clear preferred_alt framing —
# while arm/camera remain ApexNav init (ARM_DEFAULT + fixed_base_gimbal).
# Onboard init RGB: see init_ee_rgb_official_episode.png from real spawn.
# ################################
BASE_XYZ = [25.869729330758922, 0.3715007912838459, -6.046013830259824]
BASE_YAW = 3.0913963488351746
FLOOR_Y = 0.06218
ROBOT_SCALE = 0.7
GPU = 0
POSE_NOTE = "open-room SE2 from hy1 step95 for visibility; arm/cam=ApexNav init"


def look_at(eye, target) -> mn.Matrix4:
    return mn.Matrix4.look_at(
        mn.Vector3(*eye), mn.Vector3(*target), mn.Vector3(0.0, 1.0, 0.0)
    )


def project(T_cam: mn.Matrix4, p_w, W: int, H: int, hfov_deg: float = 90.0):
    pc = T_cam.inverted().transform_point(
        mn.Vector3(float(p_w[0]), float(p_w[1]), float(p_w[2]))
    )
    if pc.z >= -1e-3:
        return None
    fx = (W / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    u = W / 2.0 + fx * (pc.x / (-pc.z))
    v = H / 2.0 - fx * (pc.y / (-pc.z))
    return float(u), float(v)


def optical_axis(env, length: float = 1.2):
    T = env.camera_world_matrix()
    o = np.array([T.translation.x, T.translation.y, T.translation.z], dtype=np.float64)
    R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
    fwd = R[:, 2]
    tip = o + fwd * length
    pitch = math.degrees(math.asin(float(np.clip(fwd[1], -1.0, 1.0))))
    return o, tip, fwd, pitch


def annotate(im: Image.Image, lines, axis_uv=None) -> Image.Image:
    dr = ImageDraw.Draw(im)
    dr.rectangle([0, 0, im.width, 24 * len(lines) + 10], fill=(0, 0, 0))
    y = 4
    for t in lines:
        dr.text((8, y), t, fill=(255, 255, 0))
        y += 22
    if axis_uv is not None:
        (u0, v0), (u1, v1) = axis_uv
        dr.line([u0, v0, u1, v1], fill=(0, 255, 80), width=5)
        dr.ellipse([u0 - 8, v0 - 8, u0 + 8, v0 + 8], outline=(255, 0, 0), width=3)
        dr.ellipse([u1 - 10, v1 - 10, u1 + 10, v1 + 10], outline=(0, 255, 80), width=3)
        dr.text((u1 + 12, v1 - 8), "optical +Z", fill=(0, 255, 80))
    return im


def capture_view(env, eye, target, o, tip, banner_lines, out_path: Path):
    T = look_at(eye, target)
    env._set_agent_pose(T)
    rgb = env.sim.get_sensor_observations()["third_rgb"][..., :3]
    im = Image.fromarray(rgb).convert("RGB")
    W, H = im.size
    uv0 = project(T, o, W, H)
    uv1 = project(T, tip, W, H)
    axis = (uv0, uv1) if (uv0 and uv1) else None
    annotate(im, banner_lines, axis).save(out_path)
    print("wrote", out_path.name, "axis", bool(axis))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    env = RangerCr10KinematicEnv(
        scene=SCENE, robot_scale=ROBOT_SCALE, gpu_device_id=GPU, enable_physics=True
    )
    # ################################
    # Snap wheels to floor at real spawn (same as episode start).
    # ################################
    env.floor_y = float(FLOOR_Y)
    env.set_arm_joints(list(ARM_DEFAULT))
    env.set_base_pose(
        BASE_XYZ[0],
        BASE_XYZ[2],
        BASE_YAW,
        y=float(FLOOR_Y) + float(env.default_base_y),
        floor_y=float(FLOOR_Y),
        snap_wheels=True,
    )
    cam_meta = activate_camera_mode(env, CAMERA_MODE_FIXED_BASE_GIMBAL, freeze_arm=True)

    x, y, z = map(float, env.base_xyz)
    yaw = float(env.base_yaw)
    fwd = np.array([math.sin(yaw), 0.0, math.cos(yaw)])
    right = np.array([math.cos(yaw), 0.0, -math.sin(yaw)])
    up = np.array([0.0, 1.0, 0.0])
    base = np.array([x, y, z])
    # Look at mid chassis / arm root so full robot fills frame.
    look_tgt = (base + up * 0.45).tolist()

    # ################################
    # Eyes that previously framed the white robot body clearly
    # (stop_fix preferred_alt family) — pure side + pure top.
    # ################################
    view_specs = [
        (
            "side",
            (base - right * 3.4 + up * 1.8 - fwd * 0.3).tolist(),
            "SIDE (L) | full robot + optical axis",
        ),
        (
            "side_R",
            (base + right * 3.4 + up * 1.8 - fwd * 0.3).tolist(),
            "SIDE (R) | full robot + optical axis",
        ),
        (
            "oblique",
            (base - fwd * 3.2 - right * 2.4 + up * 2.2).tolist(),
            "OBLIQUE | chassis+arm profile",
        ),
        (
            "top",
            (base - fwd * 0.05 + up * 4.8).tolist(),
            "TOP | footprint + optical heading",
        ),
    ]

    states = [
        ("init", 0.0, None),
        ("look_up", None, "up"),  # filled after apply
        ("look_down", None, "down"),
    ]
    # Build ordered: init, up from reset, down from reset
    ordered = [("init", 0.0, None)]
    g_up = apply_gimbal_look(env, "up")
    ordered.append(("look_up", float(env.gimbal_pitch), g_up))
    env.gimbal_pitch = 0.0
    env._apply_state()
    g_dn = apply_gimbal_look(env, "down")
    ordered.append(("look_down", float(env.gimbal_pitch), g_dn))

    meta = {
        "camera_mode": CAMERA_MODE_FIXED_BASE_GIMBAL,
        "arm_default": list(ARM_DEFAULT),
        "activate": cam_meta,
        "base_xyz": env.base_xyz.tolist(),
        "base_yaw": yaw,
        "floor_y": FLOOR_Y,
        "robot_scale": ROBOT_SCALE,
        "note": POSE_NOTE,
        "framing": "open_room_step95_SE2",
        "arm_camera": "ARM_DEFAULT + fixed_base_gimbal (episode init)",
        "states": [],
    }

    for name, gpitch, gmeta in ordered:
        env.gimbal_pitch = float(gpitch)
        env._apply_state()
        o, tip, fwd_o, opt_pitch = optical_axis(env)

        # ################################
        # onboard RGB: observe_ee_only applies _ee_T (sync alone does not move agent)
        # ################################
        ee = Image.fromarray(env.observe_ee_only()["ee_rgb"][..., :3]).convert("RGB")
        annotate(
            ee,
            [
                f"ApexNav fixed_base_gimbal | {name} | ee_rgb",
                f"gimbal={math.degrees(gpitch):+.1f}deg optical≈{opt_pitch:+.1f}deg",
                f"cam_AGL≈{o[1]-FLOOR_Y:.3f}m | arm=ARM_DEFAULT frozen",
            ],
        ).save(OUT / f"{name}_ee_rgb.png")

        for vname, eye, vlabel in view_specs:
            capture_view(
                env,
                eye,
                look_tgt,
                o,
                tip,
                [
                    f"{vlabel} | {name}",
                    f"gimbal={math.degrees(gpitch):+.1f}deg optical≈{opt_pitch:+.1f}deg | scale=0.7",
                    "green=optical +Z; red=cam origin; REAL spawn (no XY shift)",
                ],
                OUT / f"{name}_{vname}.png",
            )

        # canonical clear aliases for user
        for src, dst in (("side", "side_clear"), ("oblique", "oblique_clear")):
            p = OUT / f"{name}_{src}.png"
            if p.exists():
                Image.open(p).save(OUT / f"{name}_{dst}.png")

        meta["states"].append(
            {
                "name": name,
                "gimbal_pitch_deg": math.degrees(gpitch),
                "optical_pitch_deg": opt_pitch,
                "optical_origin_world": o.tolist(),
                "cam_agl_m": float(o[1] - FLOOR_Y),
                "look_meta": gmeta,
                "camera_summary": camera_mode_summary(env),
            }
        )
        print(
            "state",
            name,
            "gpitch",
            math.degrees(gpitch),
            "opt",
            opt_pitch,
            "agl",
            o[1] - FLOOR_Y,
        )

    (OUT / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    env.close()
    print("DONE", OUT)


if __name__ == "__main__":
    main()
