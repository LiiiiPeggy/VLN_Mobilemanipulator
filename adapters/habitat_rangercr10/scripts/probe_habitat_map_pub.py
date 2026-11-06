#!/usr/bin/env python3
"""DIAGNOSTIC: Habitat observe + publish → check /grid_map integration."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import magnum as mn
import rospy
from std_msgs.msg import Float64

from src.kinematic_demo import RangerCr10KinematicEnv
from src.map_listener import ApexNavMapListener
from src.ppo_mujoco_raise import apply_raise_to_habitat
from src.ros_dynamic_publisher import DynamicROSPublisher


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--scene", type=str, required=True)
    ap.add_argument("--spawn_json", type=Path, required=True)
    ap.add_argument("--ppo_raise_json", type=Path, required=True)
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    spawn = json.loads(args.spawn_json.read_text())
    sp = spawn.get("spawn") or spawn
    rospy.init_node("hab_pub_probe", anonymous=True)
    ml = ApexNavMapListener()
    conf = rospy.Publisher("/detector/confidence_threshold", Float64, queue_size=10)
    rospy.sleep(0.5)

    env = RangerCr10KinematicEnv(scene=args.scene, gpu_device_id=args.gpu, robot_scale=0.7)
    fy = float(sp["floor_y"])
    env.set_base_pose(
        float(sp["x"]),
        float(sp["z"]),
        float(sp["yaw"]),
        y=float(sp.get("base_y", fy + env.default_base_y)),
        floor_y=fy,
        snap_wheels=True,
    )
    apply_raise_to_habitat(env, json.loads(args.ppo_raise_json.read_text())["arm_q_final"])
    pub = DynamicROSPublisher(0.0, 5.0, floor_y=fy, robot_scale=0.7)
    pub.set_env(env, robot_scale=0.7)
    rospy.sleep(1.0)
    print(
        "subs",
        pub.depth_pub.get_num_connections(),
        pub.pose_pub.get_num_connections(),
        flush=True,
    )
    series = []
    for i in range(int(args.n)):
        ee = env.observe_ee_only()
        cam = env.camera_world_matrix()  # optical for map_ros
        meta = pub.publish(
            rgb=ee["ee_rgb"][..., :3],
            depth_m=ee["ee_depth"],
            base_pos_hab=env.base_xyz,
            base_yaw_hab=env.base_yaw,
            camera_T_hab=cam,
            raw_camera_T_hab=cam,
        )
        conf.publish(Float64(0.35))
        rospy.sleep(0.15)
        st = ml.stats()
        series.append({"i": i, "map": st, "stamp": meta.get("stamp"), "dv": meta.get("depth_validity")})
        if i in (0, 5, 10, args.n - 1):
            print(i, st, flush=True)
    out = {"final": ml.stats(), "series": series}
    (args.out / "probe_stats.json").write_text(json.dumps(out, indent=2))
    print("FINAL", out["final"], flush=True)


if __name__ == "__main__":
    main()
