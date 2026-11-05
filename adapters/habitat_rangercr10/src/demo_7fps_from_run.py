"""Offline 7 Hz paper Demo from a finished ApexNav real episode.

################################
Reuses recorded steps/actions timestamps + RGB/detections/maps.
Re-renders Habitat third (+ EE RGB) at interpolated SE(2)/arm poses so motion
is smooth at 7 FPS. Detection and map *content* hold the latest real update
(no forged detections / no synthetic occupancy). Map PNGs are remapped to the
white paper palette. Does NOT re-run ApexNav planner or PPO.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from .constants import MODE_KINEMATIC, URDF_HABITAT
from .demo_compose import compose_frame
from .kinematic_demo import RangerCr10KinematicEnv
from .map_style import PAPER_ROBOT, PAPER_TRAJ, remap_legacy_map_to_paper

DEMO_FPS = 7.0
FRAME_DT = 1.0 / DEMO_FPS


def _hab_to_ros_xy(base: dict) -> Tuple[float, float]:
    # Match adapters hab_pos_to_ros planar (-z, -x)
    return (-float(base["z"]), -float(base["x"]))


def _paper_map_with_traj(
    run_dir: Path,
    steps: List[dict],
    hold_i: int,
    size: Tuple[int, int] = (320, 240),
    meters_span: float = 12.0,
) -> np.ndarray:
    """White-bg remap of recorded map PNG + orange traj + blue robot from step poses."""
    from PIL import ImageDraw

    raw = np.asarray(
        Image.open(run_dir / "maps" / f"frame_{hold_i:04d}.png").convert("RGB")
    )
    canvas = remap_legacy_map_to_paper(raw, dilate_px=2)
    h, w = size[1], size[0]
    cx_r, cy_r = _hab_to_ros_xy(steps[hold_i]["base"])
    scale = w / meters_span

    def to_pix(xy):
        px = int((xy[0] - cx_r) * scale + w / 2)
        py = int(-(xy[1] - cy_r) * scale + h / 2)
        return px, py

    im = Image.fromarray(canvas)
    dr = ImageDraw.Draw(im)
    traj = [_hab_to_ros_xy(steps[i]["base"]) for i in range(hold_i + 1)]
    if len(traj) >= 2:
        dr.line([to_pix(p) for p in traj], fill=PAPER_TRAJ, width=2)
    yaw = float(steps[hold_i]["base"]["yaw"])
    px, py = to_pix((cx_r, cy_r))
    tip = (int(px + 12 * math.cos(yaw)), int(py - 12 * math.sin(yaw)))
    dr.ellipse([px - 5, py - 5, px + 5, py + 5], fill=PAPER_ROBOT)
    dr.line([(px, py), tip], fill=PAPER_ROBOT, width=2)
    return np.asarray(im)


def _scene_glb_from_episode(scene_id: str, hm3d_root: Path) -> str:
    """Resolve ObjectNav scene_id without importing ROS-heavy apexnav_real_episode."""
    sid = Path(scene_id)
    stem = sid.name.replace(".basis.glb", "").replace(".glb", "")
    candidates = [
        hm3d_root / sid.name,
        Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets") / scene_id,
    ]
    candidates.extend(Path(hm3d_root).glob(f"**/{stem}.basis.glb"))
    for c in candidates:
        if c is not None and Path(c).is_file():
            return str(c)
    raise FileNotFoundError(f"cannot resolve scene glb for {scene_id}")


def _unwrap_lerp_angle(a0: float, a1: float, u: float) -> float:
    d = (a1 - a0 + math.pi) % (2.0 * math.pi) - math.pi
    return float(a0 + u * d)


def _lerp(a: Sequence[float], b: Sequence[float], u: float) -> List[float]:
    return [float(x) + u * (float(y) - float(x)) for x, y in zip(a, b)]


def _load_jsonl(path: Path) -> List[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _nearest_idx(times: np.ndarray, t: float) -> int:
    return int(np.argmin(np.abs(times - t)))


def _bracket(times: np.ndarray, t: float) -> Tuple[int, int, float]:
    """Return (i0, i1, u) with t in [times[i0], times[i1]]."""
    if t <= times[0]:
        return 0, 0, 0.0
    if t >= times[-1]:
        n = len(times) - 1
        return n, n, 0.0
    i1 = int(np.searchsorted(times, t, side="right"))
    i0 = i1 - 1
    span = float(times[i1] - times[i0])
    u = 0.0 if span <= 1e-9 else float((t - times[i0]) / span)
    return i0, i1, u


def _map_content_change_rate(steps: List[dict], duration: float) -> float:
    prev = None
    changes = 0
    for s in steps:
        ms = s.get("map_stats") or {}
        key = (ms.get("free"), ms.get("occupied"), ms.get("unknown"))
        if prev is None:
            prev = key
            changes = 1
            continue
        if key != prev:
            changes += 1
            prev = key
    return float(changes) / max(duration, 1e-6)


def build_timeline(t0: float, t1: float, fps: float = DEMO_FPS) -> np.ndarray:
    n = int(math.floor((t1 - t0) * fps)) + 1
    return t0 + np.arange(n, dtype=np.float64) / fps


def run(run_dir: Path, *, gpu: int = 0, hm3d_root: str, max_frames: int = 0) -> dict:
    run_dir = Path(run_dir)
    out_frames = run_dir / "demo" / "frames_7fps"
    out_frames.mkdir(parents=True, exist_ok=True)

    steps = _load_jsonl(run_dir / "steps.jsonl")
    acts = _load_jsonl(run_dir / "actions.jsonl")
    assert len(steps) == len(acts), (len(steps), len(acts))
    ep = json.loads((run_dir / "episode.json").read_text())
    spawn = json.loads((run_dir / "start_pose.json").read_text())["spawn"]

    times = np.asarray([float(a["t"]) for a in acts], dtype=np.float64)
    t0, t1 = float(times[0]), float(times[-1])
    duration = t1 - t0
    timeline = build_timeline(t0, t1, DEMO_FPS)
    if max_frames > 0:
        timeline = timeline[:max_frames]

    scene = _scene_glb_from_episode(ep["scene_id"], Path(hm3d_root))
    # ################################
    # Honor recorded robot_scale (0.7 proxy demos must not reload 1.0× URDF).
    # ################################
    start_pose = json.loads((run_dir / "start_pose.json").read_text())
    robot_scale = float(
        start_pose.get("robot_scale")
        or spawn.get("robot_scale")
        or 1.0
    )
    env = RangerCr10KinematicEnv(
        scene=scene, urdf=URDF_HABITAT, gpu_device_id=gpu, robot_scale=robot_scale
    )
    floor_y = float(spawn["floor_y"])
    env.set_base_pose(
        float(spawn["x"]),
        float(spawn["z"]),
        float(spawn["yaw"]),
        y=float(spawn.get("base_y", floor_y + env.default_base_y)),
        floor_y=floor_y,
        snap_wheels=True,
    )
    arm0 = spawn.get("arm_q_used") or steps[0]["arm"]
    env.set_arm_joints(arm0)

    goal = str(ep.get("object_category", "object"))
    n_det = len(list((run_dir / "detections").glob("frame_*.png")))
    det_hz = n_det / max(duration, 1e-6)
    map_hz = _map_content_change_rate(steps, duration)

    meta_rows: List[dict] = []
    t_render0 = time.time()
    try:
        for fi, t in enumerate(timeline):
            i0, i1, u = _bracket(times, float(t))
            s0, s1 = steps[i0], steps[i1]
            # ################################
            # Interpolate base SE(2) + arm for mid-motion third/EE render.
            # ################################
            b0, b1 = s0["base"], s1["base"]
            x = float(b0["x"]) + u * (float(b1["x"]) - float(b0["x"]))
            z = float(b0["z"]) + u * (float(b1["z"]) - float(b0["z"]))
            yaw = _unwrap_lerp_angle(float(b0["yaw"]), float(b1["yaw"]), u)
            arm = _lerp(s0["arm"], s1["arm"], u)
            env.set_base_pose(x, z, yaw, y=float(b0["y"]), floor_y=floor_y, snap_wheels=False)
            env.set_arm_joints(arm)

            # ################################
            # EE first, then third (third moves agent sensors; do not reverse).
            # Left inset uses latest real detection image; EE RGB is fallback only.
            # ################################
            ee = env.observe_ee_only()["ee_rgb"][..., :3]
            third = env.observe_third_only()[..., :3]

            # Hold latest *real* detection / map content (step index floor of time)
            hold_i = i0  # last completed planner step at or before t
            det_path = run_dir / "detections" / f"frame_{hold_i:04d}.png"
            if det_path.is_file():
                sem = np.asarray(Image.open(det_path).convert("RGB"))
            else:
                sem = ee
            map_path = run_dir / "maps" / f"frame_{hold_i:04d}.png"
            if map_path.is_file():
                map_rgb = _paper_map_with_traj(run_dir, steps, hold_i)
            else:
                map_rgb = np.full((240, 320, 3), 255, dtype=np.uint8)

            action = str(s0.get("planner_action_name") or acts[hold_i].get("name") or "")
            phase = str(s0.get("phase") or acts[hold_i].get("phase") or "")
            demo = compose_frame(
                third,
                sem,
                map_rgb,
                goal=goal,
                step=hold_i,
                action=action,
                phase=phase,
                control_mode=MODE_KINEMATIC,
                status="7fps_sync",
                extra_banner=f"video={DEMO_FPS:.0f}Hz det~{det_hz:.2f}Hz map~{map_hz:.2f}Hz",
            )
            Image.fromarray(demo).save(out_frames / f"frame_{fi:04d}.png")
            meta_rows.append(
                {
                    "frame": fi,
                    "t": float(t),
                    "hold_step": hold_i,
                    "u": u,
                    "action": action,
                    "phase": phase,
                }
            )
            if fi % 25 == 0:
                print(f"[7fps] frame {fi}/{len(timeline)} t={t-t0:.2f}s step={hold_i}", flush=True)
    finally:
        try:
            env.close()
        except Exception:
            pass

    mp4 = run_dir / "demo" / "apexnav_ranger_paper_demo_7fps.mp4"
    # ################################
    # Encode at native 7 FPS input rate (NOT a 2fps→speedup remux).
    # ################################
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(DEMO_FPS),
        "-i",
        str(out_frames / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "20",
        str(mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    rates = {
        "run_dir": str(run_dir),
        "video_path": str(mp4),
        "video_fps": DEMO_FPS,
        "frame_dt_s": FRAME_DT,
        "n_video_frames": len(timeline),
        "episode_duration_s": duration,
        "n_planner_steps": len(steps),
        "detection_hz_actual": det_hz,
        "detection_policy": "hold_latest_real_detection_image",
        "map_content_hz_actual": map_hz,
        "map_display_hz": DEMO_FPS,
        "map_policy": "hold_latest_real_grid_map_png_remapped_white_bg",
        "third_ee_render_hz": DEMO_FPS,
        "third_ee_policy": "habitat_fk_pose_interpolation_between_recorded_steps",
        "not_ffmpeg_speedup_of_2fps": True,
        "original_2fps_kept": str(run_dir / "demo" / "apexnav_ranger_paper_demo.mp4"),
        "render_wall_s": time.time() - t_render0,
        "layout": "1280x720 third + EE detections + white ApexNav map",
    }
    (run_dir / "demo" / "demo_7fps_rates.json").write_text(json.dumps(rates, indent=2))
    (run_dir / "demo" / "demo_7fps_frames.jsonl").write_text(
        "\n".join(json.dumps(r) for r in meta_rows) + "\n"
    )
    print(json.dumps(rates, indent=2))
    return rates


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--run_dir",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/20261104_114652",
    )
    p.add_argument(
        "--hm3d_root",
        default="/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val",
    )
    p.add_argument("--gpu", type=int, default=0)
    p.add_argument("--max_frames", type=int, default=0, help="debug truncate")
    args = p.parse_args(argv)
    run(Path(args.run_dir), gpu=args.gpu, hm3d_root=args.hm3d_root, max_frames=args.max_frames)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
