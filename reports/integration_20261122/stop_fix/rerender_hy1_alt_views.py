#!/usr/bin/env python3
"""Offline alternate third-person views for hy1 stuck frames.

NOT original-run screenshots: rebuilds Habitat scene, teleports to recorded
base/arm from steps.jsonl, then renders clear external angles. Annotate as
offline reconstruction.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import magnum as mn
import numpy as np
from PIL import Image, ImageDraw

from src.constants import ARM_DEFAULT, URDF_HABITAT
from src.kinematic_demo import RangerCr10KinematicEnv


def scene_glb_from_episode(scene_id: str, hm3d_root: Path) -> str:
    sid = Path(scene_id)
    if sid.is_file():
        return str(sid)
    stem = sid.name.replace(".basis.glb", "").replace(".glb", "")
    matches = list(Path(hm3d_root).glob(f"**/{stem}.basis.glb"))
    if not matches:
        raise FileNotFoundError(f"cannot resolve scene glb for {scene_id}")
    return str(matches[0])


def look_at(eye, target) -> mn.Matrix4:
    return mn.Matrix4.look_at(
        mn.Vector3(*eye), mn.Vector3(*target), mn.Vector3(0.0, 1.0, 0.0)
    )


def alt_eyes(base_xyz, yaw: float):
    """Several clear external viewpoints (demo-only)."""
    x, y, z = map(float, base_xyz)
    fwd = np.array([math.sin(yaw), 0.0, math.cos(yaw)], dtype=np.float64)
    right = np.array([math.cos(yaw), 0.0, -math.sin(yaw)], dtype=np.float64)
    up = np.array([0.0, 1.0, 0.0])
    base = np.array([x, y, z])
    target = base + np.array([0.0, 0.55, 0.0])
    specs = [
        ("side_L_high", base - right * 3.2 + up * 2.4 - fwd * 0.4),
        ("side_R_high", base + right * 3.2 + up * 2.4 - fwd * 0.4),
        ("behind_high", base - fwd * 4.0 + up * 2.8),
        ("front_oblique", base + fwd * 2.8 - right * 2.2 + up * 2.2),
        ("elev45", base - fwd * 2.5 - right * 2.5 + up * 3.2),
    ]
    return [(name, eye.tolist(), target.tolist()) for name, eye in specs]


def load_pose(steps_path: Path, step: int):
    rows = [json.loads(l) for l in steps_path.read_text().splitlines()]
    by = {int(r["step"]): r for r in rows if "step" in r}
    # STOP often lacks exec pose — fall back to previous
    for s in range(step, max(-1, step - 3), -1):
        r = by.get(s)
        if not r:
            continue
        ex = r.get("exec") or {}
        base = ex.get("base_xyz_after")
        yaw = ex.get("base_yaw_after")
        if base is not None and yaw is not None:
            arm = ex.get("arm_q_after") or list(ARM_DEFAULT)
            if len(arm) < 6:
                arm = list(ARM_DEFAULT)
            return {
                "step": step,
                "pose_step": s,
                "base": base,
                "yaw": float(yaw),
                "arm": arm[:6],
                "plan": r.get("planner_action_name"),
                "act": ex.get("actual_action"),
                "blocked": ex.get("blocked"),
                "trunc": ex.get("truncated"),
                "yaw_delta": ex.get("yaw_delta"),
                "moved_m": ex.get("moved_m"),
            }
    raise RuntimeError(f"no pose for step {step} in {steps_path}")


def annotate(im: Image.Image, lines) -> Image.Image:
    draw = ImageDraw.Draw(im)
    draw.rectangle([0, 0, im.width, 24 * len(lines) + 12], fill=(0, 0, 0))
    y = 4
    for line in lines:
        draw.text((8, y), line, fill=(255, 255, 0))
        y += 22
    return im


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--steps", default="94,95,96")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--robot_scale", type=float, default=0.7)
    args = ap.parse_args()

    run = Path(args.run_dir)
    out = Path(args.out_dir)
    raw = out / "raw_alt"
    ann = out / "annotated_alt"
    raw.mkdir(parents=True, exist_ok=True)
    ann.mkdir(parents=True, exist_ok=True)

    ep = json.loads((run / "episode.json").read_text())
    scene = scene_glb_from_episode(
        ep["scene_id"], Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val")
    )
    env = RangerCr10KinematicEnv(
        scene=scene, urdf=URDF_HABITAT, robot_scale=args.robot_scale, gpu_device_id=args.gpu
    )
    env.camera_mode = "fixed_base_gimbal"
    # freeze fixed cam like episode init (ARM_DEFAULT mount)
    if hasattr(env, "fixed_cam_pos_base"):
        pass

    steps = [int(x) for x in args.steps.split(",") if x.strip()]
    index = {"label": args.label, "source_run": str(run), "note": "offline reconstruction", "frames": []}

    for st in steps:
        pose = load_pose(run / "steps.jsonl", st)
        env.set_base_pose(
            float(pose["base"][0]),
            float(pose["base"][2]),
            float(pose["yaw"]),
            y=float(pose["base"][1]),
            snap_wheels=False,
            update_wheel_joints=False,
        )
        env.set_arm_joints(pose["arm"])
        env.sync_agent_sensors()

        for name, eye, target in alt_eyes(pose["base"], pose["yaw"]):
            T = look_at(eye, target)
            env._set_agent_pose(T)
            rgb = env.sim.get_sensor_observations()["third_rgb"][..., :3]
            fname = f"{name}_step{st:03d}.png"
            Image.fromarray(rgb).save(raw / fname)
            lines = [
                f"{args.label} | step {st} | view={name}",
                f"plan={pose['plan']} act={pose['act']} blocked={pose['blocked']} trunc={pose['trunc']}",
                f"yaw_delta={pose['yaw_delta']} moved_m={pose['moved_m']} pose_from_step={pose['pose_step']}",
                "OFFLINE reconstruction (not original-run third frame)",
            ]
            annotate(Image.fromarray(rgb).convert("RGB"), lines).save(ann / fname)
            index["frames"].append({"step": st, "view": name, "file": fname})
            print("wrote", fname)

    (out / "alt_views_index.json").write_text(json.dumps(index, indent=2) + "\n")
    env.close() if hasattr(env, "close") else None
    print("DONE", out)


if __name__ == "__main__":
    main()
