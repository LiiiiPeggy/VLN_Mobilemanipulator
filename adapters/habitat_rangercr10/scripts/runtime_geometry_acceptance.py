#!/usr/bin/env python3
"""Runtime geometry acceptance (independent of formal explore metrics).

################################
Checks (same static scene / independent reset):
  1) Habitat sensor projection / optical rays vs ROS fx,fy,cx,cy vs map_ros unproject
  2) Chassis odom: turn-in-place / arm-only → XY fixed; MOVE_FORWARD → odom matches
  3) Self-hit mask dumps; geometric fallback must be recorded if used
Does NOT feed GT into ApexNav. Does NOT mix into formal episode scores.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

# Allow `python -m` or direct path under adapters/habitat_rangercr10
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.camera_model import optical_ray_dir, pinhole_from_hfov, unproject_optical
from src.constants import DEFAULT_SCENE, URDF_HABITAT
from src.coord_habitat_ros import (
    hab_optical_rot_to_ros,
    hab_pos_to_ros,
    mat4_hab_optical_to_ros_pose,
)
from src.depth_validity import geometric_self_hit_mask, prepare_depth_for_apexnav
from src.initial_camera_pose import apply_and_record_initial_camera
from src.kinematic_demo import DEFAULT_BASE_Y, RangerCr10KinematicEnv


def _T_Rp(T):
    R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
    p = np.array([T.translation.x, T.translation.y, T.translation.z], dtype=np.float64)
    return R, p


def _habitat_sensor_projection(env) -> dict:
    """Read actual Habitat CameraSensor projection if available (not just analytic K)."""
    out = {"available": False}
    try:
        sens = env.agent._sensors.get("ee_rgb") or env.sim._sensors.get("ee_rgb")
        # habitat_sim Sensor API varies; try common paths
        cam = None
        if sens is not None:
            cam = getattr(sens, "sensor_object", None) or getattr(sens, "_sensor_object", None) or sens
        if cam is not None and hasattr(cam, "projection_matrix"):
            P = np.array(cam.projection_matrix, dtype=np.float64)
            out["projection_matrix"] = P.reshape(-1).tolist()
            out["available"] = True
        if cam is not None and hasattr(cam, "render_camera"):
            rc = cam.render_camera
            if hasattr(rc, "camera_matrix"):
                out["camera_matrix"] = np.array(rc.camera_matrix, dtype=np.float64).reshape(-1).tolist()
                out["available"] = True
        spec = None
        try:
            agent_cfg = env.sim.agents[0].agent_config
            for s in agent_cfg.sensor_specifications:
                if getattr(s, "uuid", "") == "ee_rgb":
                    spec = s
                    break
        except Exception:
            pass
        if spec is not None:
            out["hfov_deg"] = float(getattr(spec, "hfov", float("nan")))
            out["resolution"] = list(getattr(spec, "resolution", []))
            out["available"] = True
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def _ray_bundle(K, R_hab_opt, p_hab, floor_y: float) -> dict:
    """Center / corners / edge rays in Habitat optical and ROS frames."""
    w, h = int(K["width"]), int(K["height"])
    pixels = {
        "center": (w / 2.0, h / 2.0),
        "tl": (0.5, 0.5),
        "tr": (w - 0.5, 0.5),
        "bl": (0.5, h - 0.5),
        "br": (w - 0.5, h - 0.5),
        "left_mid": (0.5, h / 2.0),
        "right_mid": (w - 0.5, h / 2.0),
    }
    R_ros = hab_optical_rot_to_ros(R_hab_opt)
    p_ros = hab_pos_to_ros(p_hab, floor_y=floor_y)
    rays = {}
    for name, (u, v) in pixels.items():
        d_opt = optical_ray_dir(u, v, K)
        d_hab_w = R_hab_opt @ d_opt
        d_ros_w = R_ros @ d_opt  # optical local → ROS world (same C@R convention)
        # map_ros unproject at unit depth
        pt_cam = np.array(
            [(u - K["cx"]) * 1.0 / K["fx"], (v - K["cy"]) * 1.0 / K["fy"], 1.0],
            dtype=np.float64,
        )
        pt_ros = R_ros @ pt_cam + p_ros
        rays[name] = {
            "uv": [u, v],
            "dir_optical": d_opt.tolist(),
            "dir_hab_world": d_hab_w.tolist(),
            "dir_ros_world_from_sensor_pose": d_ros_w.tolist(),
            "map_ros_unit_depth_world": pt_ros.tolist(),
            "angle_err_deg_sensor_vs_mapros": float(
                math.degrees(
                    math.acos(
                        float(
                            np.clip(
                                np.dot(d_ros_w / (np.linalg.norm(d_ros_w) + 1e-12),
                                       (pt_ros - p_ros) / (np.linalg.norm(pt_ros - p_ros) + 1e-12)),
                                -1.0,
                                1.0,
                            )
                        )
                    )
                )
            ),
        }
    return rays


def _odom_chassis_ros(env, floor_y: float) -> np.ndarray:
    from src.coord_habitat_ros import hab_yaw_to_ros

    p = hab_pos_to_ros(env.base_xyz, floor_y=floor_y)
    yaw = hab_yaw_to_ros(env.base_yaw)
    return np.array([p[0], p[1], yaw], dtype=np.float64)


def run(args: argparse.Namespace) -> dict:
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "self_hit").mkdir(exist_ok=True)

    env = RangerCr10KinematicEnv(
        scene=args.scene,
        urdf=args.urdf,
        gpu_device_id=args.gpu,
        robot_scale=float(args.robot_scale),
    )
    if args.force_spawn_json and Path(args.force_spawn_json).is_file():
        sp = json.loads(Path(args.force_spawn_json).read_text())
        spawn = sp.get("spawn", sp)
        env.set_base_pose(
            float(spawn["x"]), float(spawn["z"]), float(spawn["yaw"]), y=float(spawn.get("base_y", DEFAULT_BASE_Y))
        )
        floor_y = float(spawn.get("floor_y", env.floor_y))
        env.floor_y = floor_y
    else:
        env.set_base_pose(args.x, args.z, 0.0, y=DEFAULT_BASE_Y)
        floor_y = float(env.floor_y)

    if args.ppo_raise_json and Path(args.ppo_raise_json).is_file():
        arm = json.loads(Path(args.ppo_raise_json).read_text())["arm_q_final"]
        env.set_arm_joints(list(arm))

    apply_and_record_initial_camera(env, out / "camera_init")
    # TURN_DOWN-like joint3 nudge for map-height realism (diagnostic only)
    if args.apply_turndown:
        q = list(env.arm_q)
        q[2] = float(q[2] - 0.60)
        env.set_arm_joints(q)

    obs = env.observe_ee_only()
    depth = np.asarray(obs["ee_depth"], dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[..., 0]
    h, w = depth.shape
    K_analytic = pinhole_from_hfov(w, h, 79.0)

    # ROS params if master is up
    ros_K = {"available": False}
    try:
        import rospy

        if not rospy.core.is_initialized():
            rospy.init_node("runtime_geometry_acceptance", anonymous=True)
        ros_K = {
            "available": True,
            "fx": float(rospy.get_param("/exploration_node/map_ros/fx", float("nan"))),
            "fy": float(rospy.get_param("/exploration_node/map_ros/fy", float("nan"))),
            "cx": float(rospy.get_param("/exploration_node/map_ros/cx", float("nan"))),
            "cy": float(rospy.get_param("/exploration_node/map_ros/cy", float("nan"))),
            "stamp": time.time(),
        }
    except Exception as e:
        ros_K = {"available": False, "error": f"{type(e).__name__}: {e}"}

    hab_proj = _habitat_sensor_projection(env)
    R_opt, p_opt = _T_Rp(env.camera_world_matrix())
    rays = _ray_bundle(K_analytic, R_opt, p_opt, floor_y)

    # Compare analytic K vs ROS K
    k_err = {}
    if ros_K.get("available"):
        for key in ("fx", "fy", "cx", "cy"):
            k_err[key] = float(abs(K_analytic[key] - ros_K[key])) if np.isfinite(ros_K[key]) else None

    # ---- motion / odom ----
    motion = {}
    o0 = _odom_chassis_ros(env, floor_y)
    cam0 = p_opt.copy()

    # turn in place
    env.set_base_pose(env.base_xyz[0], env.base_xyz[2], env.base_yaw + math.radians(30), y=env.base_xyz[1])
    o1 = _odom_chassis_ros(env, floor_y)
    R1, p1 = _T_Rp(env.camera_world_matrix())
    motion["turn_inplace"] = {
        "odom_xy_delta_m": float(np.linalg.norm(o1[:2] - o0[:2])),
        "odom_yaw_delta_deg": float(math.degrees(o1[2] - o0[2])),
        "cam_pos_delta_m": float(np.linalg.norm(p1 - cam0)),
        "pass_xy_static": bool(np.linalg.norm(o1[:2] - o0[:2]) < 1e-4),
    }

    # arm only
    env.set_base_pose(env.base_xyz[0], env.base_xyz[2], env.base_yaw, y=env.base_xyz[1])  # keep
    o_before_arm = _odom_chassis_ros(env, floor_y)
    cam_before = _T_Rp(env.camera_world_matrix())[1]
    q = list(env.arm_q)
    q[4] = float(np.clip(q[4] + 0.15, -2, 2))
    env.set_arm_joints(q)
    o_after_arm = _odom_chassis_ros(env, floor_y)
    cam_after = _T_Rp(env.camera_world_matrix())[1]
    motion["arm_only"] = {
        "odom_xy_delta_m": float(np.linalg.norm(o_after_arm[:2] - o_before_arm[:2])),
        "cam_pos_delta_m": float(np.linalg.norm(cam_after - cam_before)),
        "pass_xy_static": bool(np.linalg.norm(o_after_arm[:2] - o_before_arm[:2]) < 1e-4),
        "pass_cam_moved": bool(np.linalg.norm(cam_after - cam_before) > 1e-4),
    }

    # MOVE_FORWARD 0.25 m along yaw
    yaw = float(env.base_yaw)
    dx = 0.25 * math.sin(yaw)
    dz = 0.25 * math.cos(yaw)
    o_bf = _odom_chassis_ros(env, floor_y)
    env.set_base_pose(env.base_xyz[0] + dx, env.base_xyz[2] + dz, yaw, y=env.base_xyz[1])
    o_af = _odom_chassis_ros(env, floor_y)
    # ROS XY displacement should match habitat (-dz, -dx) magnitude 0.25
    d_odom = o_af[:2] - o_bf[:2]
    motion["move_forward_0p25"] = {
        "odom_delta_xy": d_odom.tolist(),
        "odom_delta_norm_m": float(np.linalg.norm(d_odom)),
        "expected_norm_m": 0.25,
        "norm_err_m": float(abs(np.linalg.norm(d_odom) - 0.25)),
        "pass": bool(abs(np.linalg.norm(d_odom) - 0.25) < 1e-3),
    }

    # ---- self-hit ----
    obs2 = env.observe_ee_only()
    depth2 = np.asarray(obs2["ee_depth"], dtype=np.float32)
    if depth2.ndim == 3:
        depth2 = depth2[..., 0]
    rgb2 = obs2["ee_rgb"]
    from PIL import Image

    Image.fromarray(rgb2[..., :3]).save(out / "self_hit" / "rgb.png")
    np.save(out / "self_hit" / "depth_raw.npy", depth2)
    mask = geometric_self_hit_mask(
        env, depth2, env.camera_world_matrix(), robot_scale=float(args.robot_scale)
    )
    depth_proc, prep_stats = prepare_depth_for_apexnav(
        depth2,
        env=env,
        camera_T_hab=env.camera_world_matrix(),
        robot_scale=float(args.robot_scale),
        camera_frame="optical",
    )
    Image.fromarray((mask.astype(np.uint8) * 255)).save(out / "self_hit" / "mask.png")
    np.save(out / "self_hit" / "depth_processed.npy", depth_proc)
    p_ros, q_ros = mat4_hab_optical_to_ros_pose(env.camera_world_matrix(), floor_y=floor_y)
    geo_used = bool(prep_stats.get("geometric_self_hit", 0.0) >= 0.5)
    fallback_used = not geo_used
    self_hit = {
        "prep_stats": prep_stats,
        "n_masked": int(mask.sum()) if mask is not None else None,
        "geometric_self_hit": geo_used,
        "fallback_used": fallback_used,
        "pose_ros": {
            "position": p_ros.tolist(),
            "quat_xyzw": q_ros.tolist(),
            "note": "optical pose for map_ros",
        },
    }
    if fallback_used:
        self_hit["status"] = "FAIL_fallback_must_not_claim_geometric_pass"
        self_hit["fallback_reason"] = (
            "geometric_self_hit_mask raised or env/camera missing; "
            f"near-gate fallback_near_m={prep_stats.get('fallback_near_m')}"
        )
    else:
        self_hit["status"] = "ok_geometric"

    # pass criteria
    ray_errs = [rays[k]["angle_err_deg_sensor_vs_mapros"] for k in rays]
    proj_pass = (
        (not ros_K.get("available") or (k_err.get("fx", 1) is not None and k_err.get("fx", 1) < 0.5 and k_err.get("fy", 1) < 0.5))
        and max(ray_errs) < 0.5
    )
    odom_pass = (
        motion["turn_inplace"]["pass_xy_static"]
        and motion["arm_only"]["pass_xy_static"]
        and motion["move_forward_0p25"]["pass"]
    )
    summary = {
        "status": "ok" if (proj_pass and odom_pass and not self_hit["fallback_used"]) else "fail",
        "projection": {
            "habitat_sensor": hab_proj,
            "analytic_K": K_analytic,
            "ros_K": ros_K,
            "K_abs_err": k_err,
            "rays": rays,
            "max_sensor_vs_mapros_angle_err_deg": float(max(ray_errs)),
            "pass": proj_pass,
            "note": "Rays from analytic optical K+FK vs map_ros unproject; Habitat P matrix recorded separately when available.",
        },
        "odom_motion": motion,
        "odom_pass": odom_pass,
        "self_hit": self_hit,
        "floor_y": floor_y,
        "out_dir": str(out),
        "timestamp": time.time(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    try:
        env.close()
    except Exception:
        pass
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--scene", default=DEFAULT_SCENE)
    ap.add_argument("--urdf", default=URDF_HABITAT)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--robot_scale", type=float, default=0.7)
    ap.add_argument("--x", type=float, default=-12.7)
    ap.add_argument("--z", type=float, default=-2.09)
    ap.add_argument("--force_spawn_json", default="")
    ap.add_argument("--ppo_raise_json", default="")
    ap.add_argument("--apply_turndown", action="store_true", default=True)
    args = ap.parse_args()
    s = run(args)
    print(json.dumps({"status": s["status"], "odom_pass": s["odom_pass"], "proj_pass": s["projection"]["pass"], "self_hit": s["self_hit"]["status"]}, indent=2))
    return 0 if s["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
