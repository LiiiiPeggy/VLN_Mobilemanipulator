#!/usr/bin/env python3
# ################################
# VLN adapt: capture one instance under fixed_base_gimbal + arm_view
# ################################
"""Same base pose for both modes; 3 observations each including shared init.

Disk layout matches Cursor D CAPTURE_LAYOUT.md (arm mode folder = arm_ee).
Large files → D disk; thin pointers under reports/tabletop_views_pilot/capture/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

_THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS))
sys.path.insert(0, str(_THIS.parents[1]))

from category_rules import pair_id as make_pair_id  # noqa: E402
from paths import (  # noqa: E402
    BASELINE_SHA,
    CAPTURES_DATA,
    HM3D_DATASET_CFG,
    MODE_ARM_DISK,
    MODE_ARM_NAME,
    MODE_FIXED,
    PROTOCOL,
    REPORT_CAPTURE,
    ROBOT_SCALE,
    scene_basis_glb,
)
from sequences import (  # noqa: E402
    ARM_DELTAS,
    ARM_INIT,
    GIMBAL_LOOKS,
    activate_arm_view,
    activate_fixed_gimbal,
    base_pose_dict,
    optical_pose_dict,
    run_arm_step,
    run_gimbal_step,
)
from spawn_near_object import find_table_edge_spawn  # noqa: E402
from src.constants import EE_RGB_HFOV_DEG, EE_RGB_RES  # noqa: E402
from src.execution_collision import EXECUTOR_VERSION  # noqa: E402
from src.kinematic_demo import RangerCr10KinematicEnv  # noqa: E402
from src.traj_utils import save_depth_mm  # noqa: E402


def _save_mask_png(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((mask.astype(np.uint8) * 255)).save(path)


def _capture_frame(
    env,
    *,
    semantic_id: int,
    out_dir: Path,
    meta_extra: Dict[str, Any],
) -> Dict[str, Any]:
    obs = env.observe_ee_only()
    rgb = obs["ee_rgb"][..., :3]
    depth = obs["ee_depth"]
    sem = obs.get("ee_semantic")
    out_dir.mkdir(parents=True, exist_ok=True)
    rgb_path = out_dir / "rgb.png"
    depth_path = out_dir / "depth_mm.png"
    mask_path = out_dir / "gt_mask.png"
    Image.fromarray(rgb).save(rgb_path)
    save_depth_mm(depth_path, depth)
    gt_pixels = 0
    mask_reliable = False
    mask_reason = None
    if sem is None:
        mask_reason = "semantic_sensor_missing"
        _save_mask_png(mask_path, np.zeros(rgb.shape[:2], dtype=np.uint8))
    else:
        mask = (sem.astype(np.int64) == int(semantic_id))
        gt_pixels = int(mask.sum())
        _save_mask_png(mask_path, mask)
        mask_reliable = True
        if gt_pixels == 0:
            # empty mask is valid (fully occluded / out of view)
            mask_reason = "empty_mask_target_invisible_or_out_of_view"
    optical = optical_pose_dict(env)
    meta = {
        "observation_index": meta_extra.get("observation_index"),
        "camera_mode": meta_extra.get("camera_mode"),
        "camera_mode_disk": meta_extra.get("camera_mode_disk"),
        "camera_mode_alias": meta_extra.get("camera_mode_alias"),
        "instance_id": meta_extra.get("instance_id"),
        "category": meta_extra.get("category"),
        "semantic_id": int(semantic_id),
        "rgb_hw": [int(rgb.shape[0]), int(rgb.shape[1])],
        "hfov_deg": EE_RGB_HFOV_DEG,
        "resolution_hw": list(EE_RGB_RES),
        "target_visible": bool(gt_pixels >= 32),
        "gt_pixels": gt_pixels,
        "gt_mask_reliable": mask_reliable,
        "gt_mask_note": mask_reason,
        "unique_viewpoint": meta_extra.get("unique_viewpoint", True),
        "action_rejected": bool(meta_extra.get("action_rejected", False)),
        "action_truncated": bool(meta_extra.get("action_truncated", False)),
        "action_status": meta_extra.get("action_status"),
        "base_pose": base_pose_dict(env),
        "camera_pose": optical,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    # D also accepts view_meta.json name
    (out_dir / "view_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def _viewpoint_key(meta: dict) -> tuple:
    t = meta["camera_pose"]["translation_world"]
    f = meta["camera_pose"]["forward_hab"]
    return (
        round(t[0], 3),
        round(t[1], 3),
        round(t[2], 3),
        round(f[0], 3),
        round(f[1], 3),
        round(f[2], 3),
    )


def capture_modes(
    env,
    *,
    pair: dict,
    pair_dir: Path,
    base_pose: dict,
) -> Dict[str, Any]:
    sem_id = int(pair["semantic_id"])
    instance_id = f"{pair['canonical']}_{pair['semantic_id']}"
    summary: Dict[str, Any] = {"modes": {}}

    # ---- fixed_base_gimbal ----
    activate_fixed_gimbal(env)
    # restore exact base (activate may have touched arm only)
    env.set_base_pose(
        base_pose["x"],
        base_pose["z"],
        base_pose["yaw"],
        y=base_pose["y"],
        floor_y=base_pose["floor_y"],
        snap_wheels=False,
        update_wheel_joints=False,
    )
    mode_dir = pair_dir / MODE_FIXED
    mode_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    seen = set()
    for i, look in enumerate(GIMBAL_LOOKS):
        act = run_gimbal_step(env, look)
        rejected = bool(act.get("blocked")) and not bool(act.get("executed"))
        truncated = False
        view_dir = mode_dir / f"view_{i:02d}"
        meta = _capture_frame(
            env,
            semantic_id=sem_id,
            out_dir=view_dir,
            meta_extra={
                "observation_index": i,
                "camera_mode": MODE_FIXED,
                "camera_mode_disk": MODE_FIXED,
                "instance_id": instance_id,
                "category": pair["canonical"],
                "action_rejected": rejected,
                "action_truncated": truncated,
                "action_status": act,
                "unique_viewpoint": True,
            },
        )
        key = _viewpoint_key(meta)
        if key in seen:
            meta["unique_viewpoint"] = False
            meta["action_status"] = {
                **(meta.get("action_status") or {}),
                "duplicate_viewpoint": True,
            }
            (view_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
            (view_dir / "view_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        seen.add(key)
        frames.append({"view": f"view_{i:02d}", "meta": meta, "action": act})
        # no retries on reject / duplicate
    summary["modes"][MODE_FIXED] = {
        "n_frames": len(frames),
        "n_unique": sum(1 for f in frames if f["meta"].get("unique_viewpoint", True)),
        "n_rejected": sum(1 for f in frames if f["meta"].get("action_rejected")),
        "frames": [
            {
                "view": f["view"],
                "gt_pixels": f["meta"]["gt_pixels"],
                "action": f["action"].get("action"),
                "blocked": f["action"].get("blocked"),
            }
            for f in frames
        ],
    }
    init_rgb_fixed = mode_dir / "view_00" / "rgb.png"

    # ---- arm_view (disk: arm_ee) ----
    # Reset base + arm to identical init as gimbal start
    env.set_base_pose(
        base_pose["x"],
        base_pose["z"],
        base_pose["yaw"],
        y=base_pose["y"],
        floor_y=base_pose["floor_y"],
        snap_wheels=False,
        update_wheel_joints=False,
    )
    activate_arm_view(env)
    mode_dir = pair_dir / MODE_ARM_DISK
    mode_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    seen = set()
    for i, delta in enumerate(ARM_DELTAS):
        act = run_arm_step(
            env,
            delta,
            action=("hold_init" if i == 0 else f"arm_waypoint_{i}"),
        )
        rejected = bool(act.get("blocked")) and not bool(act.get("executed"))
        truncated = bool(act.get("truncated"))
        view_dir = mode_dir / f"view_{i:02d}"
        meta = _capture_frame(
            env,
            semantic_id=sem_id,
            out_dir=view_dir,
            meta_extra={
                "observation_index": i,
                "camera_mode": MODE_ARM_NAME,
                "camera_mode_disk": MODE_ARM_DISK,
                "camera_mode_alias": MODE_ARM_NAME,
                "instance_id": instance_id,
                "category": pair["canonical"],
                "action_rejected": rejected,
                "action_truncated": truncated,
                "action_status": {
                    k: act.get(k)
                    for k in (
                        "action",
                        "ok",
                        "executed",
                        "blocked",
                        "truncated",
                        "block_reason",
                        "arm_q_after",
                        "target_arm_q",
                        "executor_version",
                    )
                    if k in act or True
                },
                "unique_viewpoint": True,
            },
        )
        key = _viewpoint_key(meta)
        if key in seen:
            meta["unique_viewpoint"] = False
            (view_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
            (view_dir / "view_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        seen.add(key)
        frames.append({"view": f"view_{i:02d}", "meta": meta, "action": act})
    summary["modes"][MODE_ARM_DISK] = {
        "n_frames": len(frames),
        "n_unique": sum(1 for f in frames if f["meta"].get("unique_viewpoint", True)),
        "n_rejected": sum(1 for f in frames if f["meta"].get("action_rejected")),
        "n_truncated": sum(1 for f in frames if f["meta"].get("action_truncated")),
        "frames": [
            {
                "view": f["view"],
                "gt_pixels": f["meta"]["gt_pixels"],
                "action": (f["action"] or {}).get("action"),
                "blocked": (f["action"] or {}).get("blocked"),
                "truncated": (f["action"] or {}).get("truncated"),
            }
            for f in frames
        ],
    }

    # Init-frame consistency check (same optical pose expectation)
    init_rgb_arm = mode_dir / "view_00" / "rgb.png"
    same_init = None
    if init_rgb_fixed.is_file() and init_rgb_arm.is_file():
        a = np.asarray(Image.open(init_rgb_fixed))
        b = np.asarray(Image.open(init_rgb_arm))
        if a.shape == b.shape:
            mae = float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32))))
            same_init = {"mae": mae, "approx_equal": mae < 2.5}
        else:
            same_init = {"error": "shape_mismatch"}
    summary["init_frame_consistency"] = same_init
    summary["base_pose_locked"] = base_pose
    return summary


def run_one(pair: dict, *, gpu: int, force: bool = False) -> Dict[str, Any]:
    pid = pair.get("pair_id") or make_pair_id(
        pair["scene_id"], pair["canonical"], pair["semantic_id"]
    )
    pair_dir = CAPTURES_DATA / pid
    if pair_dir.exists() and not force:
        # allow resume only if incomplete
        need = [
            pair_dir / MODE_FIXED / "view_00" / "rgb.png",
            pair_dir / MODE_ARM_DISK / "view_00" / "rgb.png",
        ]
        if all(p.is_file() for p in need):
            return {"pair_id": pid, "skipped": True, "pair_dir": str(pair_dir)}

    pair_dir.mkdir(parents=True, exist_ok=True)
    scene = str(scene_basis_glb(pair["scene_id"]))
    env = RangerCr10KinematicEnv(
        scene=scene,
        enable_physics=True,
        gpu_device_id=gpu,
        robot_scale=ROBOT_SCALE,
        enable_semantic=True,
        scene_dataset_config=str(HM3D_DATASET_CFG),
    )
    try:
        print(f"  spawn search for {pid} ...", flush=True)
        spawn = find_table_edge_spawn(
            env,
            pair["center_hab"],
            arm_q=ARM_INIT,
            semantic_id=int(pair["semantic_id"]),
            min_visible_pixels=80,
        )
        print(
            f"  spawn done found={spawn.get('found')} "
            f"n_ok={spawn.get('n_ok')} vis_ok={spawn.get('n_visible_ok')} "
            f"pixels={(spawn.get('best') or {}).get('ee_target_pixels')}",
            flush=True,
        )
        if not spawn.get("found"):
            result = {
                "pair_id": pid,
                "ok": False,
                "error": "spawn_not_found",
                "spawn": spawn,
            }
            (pair_dir / "capture_summary.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
            return result
        base_pose = spawn["best"]
        # Capture
        mode_summary = capture_modes(env, pair=pair, pair_dir=pair_dir, base_pose=base_pose)
        # Base drift check: re-read pose
        base_after = base_pose_dict(env)
        manifest = {
            "pair_id": pid,
            "scene": pair["scene_id"],
            "scene_id": pair["scene_id"],
            "instance_id": f"{pair['canonical']}_{pair['semantic_id']}",
            "semantic_id": int(pair["semantic_id"]),
            "category": pair["canonical"],
            "category_raw": pair.get("label"),
            "label": pair.get("label"),
            "center_hab": pair.get("center_hab"),
            "protocol": PROTOCOL,
            "baseline_sha": BASELINE_SHA,
            "robot_scale": ROBOT_SCALE,
            "robot_scale_tag": env.scale_tag,
            "executor_version": EXECUTOR_VERSION,
            "gripper": "fixed",
            "camera_modes": [MODE_FIXED, MODE_ARM_DISK],
            "camera_mode_aliases": {MODE_ARM_DISK: MODE_ARM_NAME},
            "max_views_per_mode": 3,
            "hfov_deg": EE_RGB_HFOV_DEG,
            "resolution_hw": list(EE_RGB_RES),
            "base_pose": base_pose,
            "base_pose_after_capture": base_after,
            "base_moved_during_capture": (
                abs(base_after["x"] - base_pose["x"]) > 1e-4
                or abs(base_after["z"] - base_pose["z"]) > 1e-4
                or abs(base_after["yaw"] - base_pose["yaw"]) > 1e-4
            ),
            "spawn": spawn,
            "notes": pair.get("selection", {}),
        }
        (pair_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (pair_dir / "meta.json").write_text(json.dumps(manifest, indent=2) + "\n")
        result = {
            "pair_id": pid,
            "ok": True,
            "pair_dir": str(pair_dir),
            "manifest": manifest,
            "capture": mode_summary,
        }
        (pair_dir / "capture_summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        try:
            env.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--locked", type=Path, default=REPORT_CAPTURE / "locked_instances.json")
    ap.add_argument("--pair_id", type=str, default=None)
    ap.add_argument("--first_only", action="store_true")
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    locked = json.loads(args.locked.read_text())
    pairs = locked["selected"]
    if args.pair_id:
        pairs = [p for p in pairs if p["pair_id"] == args.pair_id]
    if args.first_only:
        pairs = pairs[:1]
    if not pairs:
        print("no pairs")
        return 2

    CAPTURES_DATA.mkdir(parents=True, exist_ok=True)
    REPORT_CAPTURE.mkdir(parents=True, exist_ok=True)
    # Ensure reports/captures points at data root for D discovery
    link = REPORT_CAPTURE.parent / "captures"
    if not link.exists():
        try:
            link.symlink_to(CAPTURES_DATA, target_is_directory=True)
        except Exception:
            link.mkdir(parents=True, exist_ok=True)

    results = []
    for p in pairs:
        print("CAPTURING", p["pair_id"], flush=True)
        r = run_one(p, gpu=args.gpu, force=args.force)
        results.append(
            {
                "pair_id": r.get("pair_id"),
                "ok": r.get("ok", r.get("skipped")),
                "skipped": r.get("skipped", False),
                "pair_dir": r.get("pair_dir"),
                "error": r.get("error"),
                "init_consistency": (r.get("capture") or {}).get("init_frame_consistency"),
            }
        )
        print(json.dumps(results[-1], indent=2), flush=True)
        # After first success, write handoff for D
        if r.get("ok") and not r.get("skipped"):
            handoff = {
                "protocol": PROTOCOL,
                "baseline_sha": BASELINE_SHA,
                "first_pair_id": r["pair_id"],
                "captures_root": str(CAPTURES_DATA),
                "reports_captures_symlink": str(REPORT_CAPTURE.parent / "captures"),
                "layout_doc": str(
                    _THIS.parents[1]
                    / "evaluation/tabletop_views/CAPTURE_LAYOUT.md"
                ),
                "camera_modes": [MODE_FIXED, MODE_ARM_DISK],
                "arm_mode_alias": MODE_ARM_NAME,
                "frozen": {
                    "robot_scale": ROBOT_SCALE,
                    "executor_version": EXECUTOR_VERSION,
                    "arm_init": list(ARM_INIT),
                    "gimbal_sequence": list(GIMBAL_LOOKS),
                    "arm_deltas": [list(d) for d in ARM_DELTAS],
                    "resolution_hw": list(EE_RGB_RES),
                    "hfov_deg": EE_RGB_HFOV_DEG,
                },
            }
            (REPORT_CAPTURE / "handoff_to_D_first_pair.json").write_text(
                json.dumps(handoff, indent=2) + "\n"
            )
            if args.first_only:
                break

    index = {
        "protocol": PROTOCOL,
        "camera_modes": [MODE_FIXED, MODE_ARM_DISK],
        "max_views_per_mode": 3,
        "captures_data_root": str(CAPTURES_DATA),
        "pairs": [],
    }
    # rebuild index from disk manifests
    for d in sorted(CAPTURES_DATA.iterdir() if CAPTURES_DATA.is_dir() else []):
        man = d / "manifest.json"
        if not man.is_file():
            continue
        m = json.loads(man.read_text())
        index["pairs"].append(
            {
                "pair_id": m["pair_id"],
                "instance_id": m["instance_id"],
                "category": m.get("category_raw") or m.get("category"),
                "scene": m.get("scene") or m.get("scene_id"),
                "reliable_gt": True,
                "notes": "",
            }
        )
    (CAPTURES_DATA / "pairing_index.json").write_text(json.dumps(index, indent=2) + "\n")
    (REPORT_CAPTURE / "pairing_index.json").write_text(json.dumps(index, indent=2) + "\n")
    (CAPTURES_DATA / "manifest_index.json").write_text(
        json.dumps({"pairs": [{"pair_id": p["pair_id"]} for p in index["pairs"]]}, indent=2)
        + "\n"
    )
    (REPORT_CAPTURE / "batch_results.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(x.get("ok") or x.get("skipped") for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
