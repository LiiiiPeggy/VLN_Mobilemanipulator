#!/usr/bin/env python3
# ################################
# VLN adapt: deployability check for independent list (NOT score filtering)
# ################################
"""Validate scene/goal/spawn/initial contact/camera/log hooks for each candidate.

Rules:
- Keep original list intact; record valid/invalid/pending + reason per id.
- Do NOT filter by SR / SEARCH / visibility.
- Full-robot penetration check; navmesh disk pass ≠ valid spawn.
- No full lookaround required.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def _hab_quat_yaw(q) -> float:
    import math

    # Habitat quat [w somehow stored as list x,y,z,w or w,x,y,z] — match apexnav helper if present
    try:
        from src.apexnav_real_episode import hab_quat_yaw  # type: ignore

        return float(hab_quat_yaw(q))
    except Exception:
        # fallback: treat as [x,y,z,w]
        x, y, z, w = [float(v) for v in q]
        return math.atan2(2.0 * (w * y + x * z), 1.0 - 2.0 * (y * y + z * z))


def _validate_one(ep: dict, args, env=None, owns_env: bool = True) -> dict:
    from src.camera_modes import (  # type: ignore
        CAMERA_MODE_FIXED_BASE_GIMBAL,
        activate_camera_mode,
        camera_mode_summary,
    )
    from src.constants import ARM_APEXNAV_INIT  # type: ignore
    from src.execution_collision import EXECUTOR_VERSION, report_initial_penetration  # type: ignore
    from src.kinematic_demo import RangerCr10KinematicEnv  # type: ignore
    from src.spawn_utils import find_adapted_start  # type: ignore

    out = {
        "id": ep["id"],
        "scene_filter": ep["scene_filter"],
        "category": ep["category"],
        "episode_id": str(ep["episode_id"]),
        "closest_goal_object_id": ep.get("closest_goal_object_id"),
        "n_view_points": ep.get("n_view_points"),
        "status": "pending",
        "reasons": [],
        "executor_version": None,
        "camera_mode": None,
        "simulated_gimbal": None,
        "robot_scale": args.robot_scale,
        "initial_penetration": None,
        "spawn_source": None,
        "code_git_sha": args.code_git_sha or None,
    }

    if not ep.get("n_view_points"):
        out["status"] = "invalid"
        out["reasons"].append("missing_or_zero_view_points")
        return out
    if ep.get("goal_position") is None:
        out["status"] = "invalid"
        out["reasons"].append("missing_goal_position")
        return out

    scene_root = Path(args.scene_root)
    hits = list(scene_root.glob(f"*-{ep['scene_filter']}/{ep['scene_filter']}.basis.glb"))
    if not hits:
        hits = list(scene_root.glob(f"**/{ep['scene_filter']}.basis.glb"))
    if not hits:
        out["status"] = "invalid"
        out["reasons"].append(f"scene_glb_not_found:{ep['scene_filter']}")
        return out

    objnav = Path(args.objnav_dir) / f"{ep['scene_filter']}.json"
    if not objnav.is_file():
        out["status"] = "invalid"
        out["reasons"].append("objectnav_json_missing")
        return out

    created = False
    try:
        if env is None:
            env = RangerCr10KinematicEnv(
                scene=str(hits[0]),
                robot_scale=float(args.robot_scale),
                gpu_device_id=int(args.gpu),
            )
            created = True
            owns_env = True
        out["executor_version"] = EXECUTOR_VERSION
        force = ep.get("force_spawn_json")
        if force and Path(force).is_file():
            prev = json.loads(Path(force).read_text())
            sp = prev.get("spawn") or prev
            fy = float(sp.get("floor_y", 0.0))
            env.set_base_pose(
                float(sp["x"]),
                float(sp["z"]),
                float(sp.get("yaw", 0.0)),
                y=fy + float(env.default_base_y),
                floor_y=fy,
                snap_wheels=True,
                update_wheel_joints=False,
            )
            out["spawn_source"] = "force_spawn_json"
            out["spawn"] = {
                "x": float(env.base_xyz[0]),
                "z": float(env.base_xyz[2]),
                "yaw": float(sp.get("yaw", 0.0)),
                "floor_y": fy,
                "base_y": float(env.base_xyz[1]),
            }
        else:
            data = json.loads(objnav.read_text())
            ep_row = None
            for e in data.get("episodes") or []:
                if str(e.get("episode_id")) == str(ep["episode_id"]) and e.get(
                    "object_category"
                ) == ep["category"]:
                    ep_row = e
                    break
            if ep_row is None:
                out["status"] = "invalid"
                out["reasons"].append("episode_not_found_in_objectnav")
                return out
            sp = ep_row["start_position"]
            yaw = _hab_quat_yaw(ep_row["start_rotation"])
            floor_y = float(sp[1])
            spawn = find_adapted_start(
                env, (float(sp[0]), float(sp[2])), yaw, floor_y=floor_y
            )
            out["spawn_source"] = "find_adapted_start"
            out["spawn"] = {
                k: spawn.get(k)
                for k in ("x", "z", "yaw", "floor_y", "base_y", "adapted_episode", "ok")
            }
            if spawn.get("ok") is False:
                out["reasons"].append("adapted_start_not_ok_flag")

        env.set_arm_joints(ARM_APEXNAV_INIT)
        cam_meta = activate_camera_mode(env, CAMERA_MODE_FIXED_BASE_GIMBAL, freeze_arm=True)
        out["camera_mode"] = cam_meta.get("camera_mode")
        out["simulated_gimbal"] = cam_meta.get("simulated_gimbal")
        out["camera_runtime"] = camera_mode_summary(env)

        pen = report_initial_penetration(env)
        out["initial_penetration"] = bool(pen.get("initial_penetration"))
        out["initial_penetration_detail"] = {
            "blocking": (pen.get("contacts") or {}).get("blocking"),
            "robot_env": (pen.get("contacts") or {}).get("robot_env"),
            "min_robot_env_distance": (pen.get("contacts") or {}).get(
                "min_robot_env_distance"
            ),
        }
        out["log_hooks"] = {
            "has_report_initial_penetration": True,
            "has_camera_mode_json_fields": bool(cam_meta.get("camera_mode")),
            "executor_version": EXECUTOR_VERSION,
        }

        if out["camera_mode"] != "fixed_base_gimbal":
            out["status"] = "invalid"
            out["reasons"].append(f"camera_mode_mismatch:{out['camera_mode']}")
        elif out["initial_penetration"] is True:
            out["status"] = "invalid"
            out["reasons"].append("initial_robot_env_penetration")
        else:
            out["status"] = "valid"
            out["reasons"].append("ok_scene_goal_spawn_camera_no_init_pen")
    except Exception as e:
        out["status"] = "invalid"
        out["reasons"].append(f"exception:{type(e).__name__}:{e}")
        out["traceback"] = traceback.format_exc(limit=5)
    finally:
        if owns_env and created:
            try:
                env.close()
            except Exception:
                pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--list",
        type=Path,
        default=ROOT
        / "adapters/habitat_rangercr10/evaluation/lists/independent_test_list_v1.json",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT
        / "reports/ranger_category_eval_20261116/lists/independent_list_validity_v1.json",
    )
    ap.add_argument(
        "--objnav_dir",
        type=Path,
        default=Path("/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2/val/content_json"),
    )
    ap.add_argument(
        "--scene_root",
        type=Path,
        default=Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val"),
    )
    ap.add_argument("--robot_scale", type=float, default=0.7)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--code_git_sha", default="")
    ap.add_argument(
        "--replacement_policy",
        default="none",
        help="none|predeclared_only — never score-based",
    )
    args = ap.parse_args()

    doc = json.loads(args.list.read_text())
    eps = doc["episodes"][args.offset :]
    if args.limit > 0:
        eps = eps[: args.limit]

    from collections import defaultdict

    from src.kinematic_demo import RangerCr10KinematicEnv  # type: ignore

    by_scene = defaultdict(list)
    for ep in eps:
        by_scene[ep["scene_filter"]].append(ep)

    results = []
    t0 = time.time()
    total = len(eps)
    done = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)

    def _flush():
        payload = {
            "list_name": doc.get("name"),
            "list_path": str(args.list),
            "code_git_sha": args.code_git_sha or None,
            "robot_scale": args.robot_scale,
            "camera_mode_required": "fixed_base_gimbal",
            "replacement_policy": args.replacement_policy,
            "note": (
                "Deployability only. Original list retained. "
                "Invalid samples not dropped from the list file; status recorded here. "
                "Do not filter by SR/SEARCH/visibility. "
                "Env reused per scene for speed; penetration uses full robot scale."
            ),
            "n_checked": len(results),
            "counts": {
                "valid": sum(1 for r in results if r["status"] == "valid"),
                "invalid": sum(1 for r in results if r["status"] == "invalid"),
                "pending": sum(1 for r in results if r["status"] == "pending"),
            },
            "elapsed_sec": time.time() - t0,
            "episodes": results,
        }
        args.out.write_text(json.dumps(payload, indent=2) + "\n")
        return payload

    for scene, group in by_scene.items():
        scene_root = Path(args.scene_root)
        hits = list(scene_root.glob(f"*-{scene}/{scene}.basis.glb"))
        if not hits:
            hits = list(scene_root.glob(f"**/{scene}.basis.glb"))
        env = None
        if hits:
            try:
                print(f"[scene] load {scene} ({len(group)} eps)", flush=True)
                env = RangerCr10KinematicEnv(
                    scene=str(hits[0]),
                    robot_scale=float(args.robot_scale),
                    gpu_device_id=int(args.gpu),
                )
            except Exception as e:
                print(f"[scene] load failed {scene}: {e}", flush=True)
                env = None
        for ep in group:
            done += 1
            print(f"[{done}/{total}] {ep['id']}", flush=True)
            if env is None and hits:
                # load failed → still record per-ep invalid via _validate_one creating own/failing
                results.append(_validate_one(ep, args, env=None, owns_env=True))
            elif env is None:
                results.append(_validate_one(ep, args, env=None, owns_env=True))
            else:
                results.append(_validate_one(ep, args, env=env, owns_env=False))
            _flush()
        if env is not None:
            try:
                env.close()
            except Exception:
                pass

    payload = _flush()
    print("DONE", payload["counts"])
    return 0


if __name__ == "__main__":
    # Ensure adapter package importable
    sys.path.insert(0, str(ROOT / "adapters/habitat_rangercr10"))
    raise SystemExit(main())
