#!/usr/bin/env python3
"""DIAGNOSTIC: PPO raise + TURN_DOWN then publish → expect non-empty /grid_map."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import magnum as mn
import numpy as np
import rospy
from std_msgs.msg import Float64

from src.kinematic_demo import RangerCr10KinematicEnv
from src.lookaround_fov_diag import quat_xyzw_to_rpy
from src.map_listener import ApexNavMapListener
from src.ppo_mujoco_raise import apply_raise_to_habitat
from src.ros_dynamic_publisher import DynamicROSPublisher

OUT = Path(os.environ["OUT"])
SPAWN = Path(
    "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/"
    "real_wide_yr17_openband_20261105_012302/start_pose.json"
)
PPO = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json")
SCENE = (
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d_v0.2/val/"
    "00831-yr17PDCnDDW/yr17PDCnDDW.basis.glb"
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    spawn = json.loads(SPAWN.read_text())
    sp = spawn.get("spawn") or spawn
    rospy.init_node("td_probe", anonymous=True)
    ml = ApexNavMapListener()
    conf = rospy.Publisher("/detector/confidence_threshold", Float64, queue_size=10)
    rospy.sleep(0.5)

    env = RangerCr10KinematicEnv(scene=SCENE, gpu_device_id=0, robot_scale=0.7)
    fy = float(sp["floor_y"])
    env.set_base_pose(
        float(sp["x"]),
        float(sp["z"]),
        float(sp["yaw"]),
        y=float(sp.get("base_y", fy + env.default_base_y)),
        floor_y=fy,
        snap_wheels=True,
    )
    apply_raise_to_habitat(env, json.loads(PPO.read_text())["arm_q_final"])
    q = env.arm_q.copy()
    q[2] = float(np.clip(float(q[2]) - 0.60, -2.86, 2.86))
    env.set_arm_joints(q)

    pub = DynamicROSPublisher(0.0, 5.0, floor_y=fy, robot_scale=0.7)
    pub.set_env(env, robot_scale=0.7)
    rospy.sleep(1.0)
    print(
        "subs",
        pub.depth_pub.get_num_connections(),
        pub.pose_pub.get_num_connections(),
        flush=True,
    )

    ee = env.observe_ee_only()
    cam = env.camera_world_matrix()  # optical
    meta = None
    for _ in range(20):
        meta = pub.publish(
            rgb=ee["ee_rgb"][..., :3],
            depth_m=ee["ee_depth"],
            base_pos_hab=env.base_xyz,
            base_yaw_hab=env.base_yaw,
            camera_T_hab=cam,
            raw_camera_T_hab=cam,
        )
        conf.publish(Float64(0.35))
        rospy.sleep(0.12)

    assert meta is not None
    rpy = quat_xyzw_to_rpy(meta["camera_q_xyzw"])
    res = {
        "pitch_deg": math.degrees(rpy[1]),
        "roll_deg": math.degrees(rpy[0]),
        "yaw_deg": math.degrees(rpy[2]),
        "camera_ros": meta["camera_ros"],
        "camera_q_xyzw": meta["camera_q_xyzw"],
        "stats": ml.stats(),
        "depth_validity": meta.get("depth_validity"),
    }
    print(json.dumps(res, indent=2), flush=True)
    (OUT / "td.json").write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
