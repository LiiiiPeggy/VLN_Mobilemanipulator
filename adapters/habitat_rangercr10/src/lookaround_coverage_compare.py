"""Mapping-only lookaround yaw-step comparison (diagnostic, not formal eval).

################################
Rotates chassis at fixed arm pose; publishes RGB-D + ITM into live ApexNav
map_ros. Compares yaw steps (e.g. 15/30/45°) at SAME spawn. Does not modify
ApexNav FSM / planner / inflation / scale / PPO.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

import rospy
from std_msgs.msg import Float64

from .constants import MODE_KINEMATIC, URDF_HABITAT
from .coord_habitat_ros import hab_pos_to_ros, hab_yaw_to_ros
from .kinematic_demo import RangerCr10KinematicEnv
from .lookaround_fov_diag import (
    fov_from_intrinsics,
    gt_false_occupied_probe,
    horizontal_overlap_deg,
    quat_xyzw_to_rpy,
)
from .map_listener import ApexNavMapListener
from .ppo_mujoco_raise import apply_raise_to_habitat
from .ros_dynamic_publisher import DynamicROSPublisher
from .spawn_utils import find_adapted_start


def _pub_f64(pub, v: float) -> None:
    msg = Float64()
    msg.data = float(v)
    pub.publish(msg)


def run_one_yaw_step(
    *,
    env: RangerCr10KinematicEnv,
    ros_pub: DynamicROSPublisher,
    map_listener: ApexNavMapListener,
    itm_pub,
    conf_pub=None,
    label: str,
    room: str,
    yaw0: float,
    step_deg: float,
    out_dir: Path,
    settle_s: float = 0.35,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    fov = fov_from_intrinsics()
    n = int(math.ceil(360.0 / float(step_deg)))
    step_rad = math.radians(float(step_deg))
    series: List[Dict[str, Any]] = []
    frames_meta: List[Dict[str, Any]] = []

    x, y, z = env.base_xyz
    floor_y = float(env.floor_y)

    for i in range(n):
        yaw = yaw0 + i * step_rad
        env.set_base_pose(float(x), float(z), float(yaw), y=float(y), floor_y=floor_y, snap_wheels=False)
        ee = env.observe_ee_only()
        rgb, depth = ee["ee_rgb"], ee["ee_depth"]
        cosine = -1.0
        try:
            from vlm.utils.get_itm_message import get_itm_message_cosine  # type: ignore

            cosine = float(get_itm_message_cosine(rgb[..., :3], label, room))
            _pub_f64(itm_pub, cosine)
            rospy.sleep(0.02)
        except Exception:
            (out_dir / f"itm_err_{i:03d}.txt").write_text(traceback.format_exc())

        # ################################
        # Match apexnav_real_episode optical fix: cam_T @ Rx(π) for ROS projection.
        # ################################
        import magnum as mn

        cam_T = env.camera_world_matrix()
        ee_T = cam_T @ mn.Matrix4.rotation_x(mn.Rad(math.pi))
        meta = ros_pub.publish(
            rgb=rgb[..., :3],
            depth_m=depth,
            base_pos_hab=env.base_xyz,
            base_yaw_hab=env.base_yaw,
            camera_T_hab=ee_T,
            raw_camera_T_hab=cam_T,
        )
        if conf_pub is not None:
            _pub_f64(conf_pub, 0.35)
        rospy.sleep(settle_s)
        st = map_listener.stats()
        cam_q = meta.get("camera_q_xyzw")
        rpy = quat_xyzw_to_rpy(cam_q) if cam_q else (None, None, None)
        dv = meta.get("depth_validity") or {}
        row = {
            "i": i,
            "yaw_hab": float(yaw),
            "yaw_ros": float(hab_yaw_to_ros(yaw)),
            "camera_ros": meta.get("camera_ros"),
            "camera_pitch_deg": None if rpy[1] is None else math.degrees(rpy[1]),
            "camera_yaw_deg": None if rpy[2] is None else math.degrees(rpy[2]),
            "stamp_ros": meta.get("stamp"),
            "itm_cosine": cosine,
            "map": {
                "occupied": st.get("occupied"),
                "free": st.get("free"),
                "unknown": st.get("unknown"),
                "value_map": st.get("value_map"),
                "occupied_msgs": st.get("occupied_msgs"),
                "free_msgs": st.get("free_msgs"),
            },
            "frac_nan_published": dv.get("frac_nan_published"),
            "frac_self_hit": dv.get("frac_self_hit"),
        }
        series.append(row)
        frames_meta.append(row)
        # panel
        br = meta.get("base_ros") or hab_pos_to_ros(env.base_xyz, floor_y=floor_y).tolist()
        panel = map_listener.render_panel(
            size=(320, 240),
            robot_xy=(float(br[0]), float(br[1])),
            robot_yaw=float(meta.get("base_yaw_ros", 0.0)),
            target_label=str(label),
            value_score=float(cosine) if cosine >= 0 else None,
        )
        Image.fromarray(panel).save(out_dir / f"map_{i:03d}.png")
        Image.fromarray(rgb[..., :3]).save(out_dir / f"rgb_{i:03d}.png")

    final = series[-1]["map"] if series else {}
    return {
        "step_deg": float(step_deg),
        "n_views": n,
        "overlap": horizontal_overlap_deg(fov["hfov_deg"], float(step_deg)),
        "final_map": final,
        "series": series,
        "fov": fov,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_root", type=Path, required=True)
    ap.add_argument("--scene", type=str, required=True)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--robot_scale", type=float, default=0.7)
    ap.add_argument("--force_spawn_json", type=Path, required=True)
    ap.add_argument("--ppo_raise_json", type=Path, default=None)
    ap.add_argument("--label", type=str, default="chair")
    ap.add_argument("--room", type=str, default="everywhere")
    ap.add_argument("--steps", type=str, default="30,15,45", help="yaw step degrees list")
    ap.add_argument("--urdf", type=str, default=URDF_HABITAT)
    args = ap.parse_args()

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    step_list = [float(x) for x in args.steps.split(",") if x.strip()]

    rospy.init_node("lookaround_coverage_compare", anonymous=True)
    map_listener = ApexNavMapListener()
    itm_pub = rospy.Publisher("/blip2/cosine_score", Float64, queue_size=10)
    rospy.sleep(1.0)

    spawn = json.loads(Path(args.force_spawn_json).read_text())
    sp = spawn.get("spawn") or spawn
    env = RangerCr10KinematicEnv(
        scene=args.scene, urdf=args.urdf, gpu_device_id=args.gpu, robot_scale=float(args.robot_scale)
    )
    floor_y = float(sp["floor_y"])
    env.set_base_pose(
        float(sp["x"]),
        float(sp["z"]),
        float(sp["yaw"]),
        y=float(sp.get("base_y", floor_y + env.default_base_y)),
        floor_y=floor_y,
        snap_wheels=True,
    )
    if args.ppo_raise_json and Path(args.ppo_raise_json).is_file():
        raise_rep = json.loads(Path(args.ppo_raise_json).read_text())
        apply_raise_to_habitat(env, raise_rep["arm_q_final"])
    # ################################
    # Match ApexNav init_lookaround: TURN_DOWN via joint3 −0.60 before yaw
    # sweep. PPO-raised level EE publishes near-identity ROS camera_q
    # (optical ≈ world +Z / looking up) → height filter empties the cloud.
    # ################################
    q_arm = env.arm_q.copy()
    q_arm[2] = float(np.clip(float(q_arm[2]) - 0.60, -2.86, 2.86))
    env.set_arm_joints(q_arm)
    yaw0 = float(env.base_yaw)
    x0, y0, z0 = env.base_xyz
    arm_lookdown = env.arm_q.copy()

    ros_pub = DynamicROSPublisher(0.0, 5.0, floor_y=floor_y, robot_scale=float(args.robot_scale))
    ros_pub.set_env(env, robot_scale=float(args.robot_scale))
    conf_pub = rospy.Publisher("/detector/confidence_threshold", Float64, queue_size=10)
    # ################################
    # Wait for exploration_node subscriptions; warm-up publish so map_ros
    # message_filters sync latches (same as episode handshake republish).
    # ################################
    rospy.sleep(1.0)
    for _ in range(30):
        if ros_pub.depth_pub.get_num_connections() > 0 and ros_pub.pose_pub.get_num_connections() > 0:
            break
        rospy.sleep(0.1)
    ee0 = env.observe_ee_only()
    import magnum as mn

    cam0 = env.camera_world_matrix()
    ee_T0 = cam0 @ mn.Matrix4.rotation_x(mn.Rad(math.pi))
    for _ in range(15):
        ros_pub.publish(
            rgb=ee0["ee_rgb"][..., :3],
            depth_m=ee0["ee_depth"],
            base_pos_hab=env.base_xyz,
            base_yaw_hab=env.base_yaw,
            camera_T_hab=ee_T0,
            raw_camera_T_hab=cam0,
        )
        _pub_f64(conf_pub, 0.35)
        rospy.sleep(0.08)
    rospy.sleep(0.5)
    warm_stats = map_listener.stats()
    print(f"[diag] warm-up map stats={warm_stats}", flush=True)

    results = {
        "note": "DIAGNOSTIC mapping-only lookaround compare — not formal ObjectNav score",
        "control_mode": MODE_KINEMATIC,
        "spawn": sp,
        "label": args.label,
        "steps_deg": step_list,
        "arm_lookdown_joint3_delta": -0.60,
        "arm_q_lookdown": arm_lookdown.tolist(),
        "warmup_map": warm_stats,
        "conditions": {},
        "depth_subscribers": int(ros_pub.depth_pub.get_num_connections()),
        "pose_subscribers": int(ros_pub.pose_pub.get_num_connections()),
    }

    for step_deg in step_list:
        # Reset pose between conditions; map accumulates in exploration_node —
        # restart advice: caller should restart exploration_node between steps
        # for clean maps. We still record; tag as cumulative if node not reset.
        env.set_base_pose(float(x0), float(z0), float(yaw0), y=float(y0), floor_y=floor_y, snap_wheels=False)
        env.set_arm_joints(arm_lookdown)
        cond_dir = out_root / f"yawstep_{int(step_deg):02d}"
        print(
            f"[diag] yaw_step={step_deg} → {cond_dir} "
            f"subs depth={ros_pub.depth_pub.get_num_connections()} "
            f"pose={ros_pub.pose_pub.get_num_connections()} "
            f"warm_free={warm_stats.get('free')}",
            flush=True,
        )
        try:
            cond = run_one_yaw_step(
                env=env,
                ros_pub=ros_pub,
                map_listener=map_listener,
                itm_pub=itm_pub,
                conf_pub=conf_pub,
                label=args.label,
                room=args.room,
                yaw0=yaw0,
                step_deg=step_deg,
                out_dir=cond_dir,
            )
        except Exception:
            (cond_dir / "error.txt").write_text(traceback.format_exc())
            cond = {"error": traceback.format_exc(), "step_deg": step_deg}
        results["conditions"][str(step_deg)] = cond
        # GT false-occupied probe on current occ cloud
        try:
            from sensor_msgs import point_cloud2 as pc2

            msg = map_listener.clouds.get("occupied")
            occ = np.zeros((0, 2))
            if msg is not None and pc2 is not None:
                pts = list(pc2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True))
                if pts:
                    occ = np.asarray(pts, dtype=np.float64)[:, :2]
            br = hab_pos_to_ros(env.base_xyz, floor_y=floor_y)
            gt = gt_false_occupied_probe(env, occ, floor_y, br)
            cond["gt_false_occupied_probe"] = gt
            (cond_dir / "gt_false_occupied.json").write_text(json.dumps(gt, indent=2))
        except Exception:
            (cond_dir / "gt_probe_error.txt").write_text(traceback.format_exc())

        (cond_dir / "summary.json").write_text(json.dumps(cond, indent=2))

    (out_root / "compare_summary.json").write_text(json.dumps(results, indent=2))
    # markdown table
    lines = [
        "# Lookaround yaw-step coverage compare (diagnostic)",
        "",
        "| step_deg | n_views | overlap_deg | final occ | final free | final val |",
        "|---|---|---|---|---|---|",
    ]
    for s in step_list:
        c = results["conditions"].get(str(s)) or {}
        m = c.get("final_map") or {}
        ov = (c.get("overlap") or {}).get("overlap_deg")
        lines.append(
            f"| {s} | {c.get('n_views')} | {ov} | {m.get('occupied')} | {m.get('free')} | {m.get('value_map')} |"
        )
    lines.append("")
    lines.append("Not a formal ApexNav performance claim; mapping-only diagnostic.")
    (out_root / "COMPARE.md").write_text("\n".join(lines) + "\n")
    print("wrote", out_root)
    # Avoid habitat-sim close() abort noise; process exit is enough for diag.
    try:
        del env
    except Exception:
        pass


if __name__ == "__main__":
    main()
