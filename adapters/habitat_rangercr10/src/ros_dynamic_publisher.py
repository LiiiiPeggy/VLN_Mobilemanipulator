"""Publish Habitat Ranger observations to ApexNav ROS topics with dynamic EE pose.

Unlike baselines/ApexNav/habitat2ros/habitat_publisher.py (fixed +0.88 m height),
this publishes:
  - /habitat/odom         : base_link pose (ROS world)
  - /habitat/sensor_pose  : d455 optical / Habitat camera pose (ROS world)
  - /habitat/camera_rgb
  - /habitat/camera_depth : normalized float32 [0,1] as ApexNav C++ expects;
    invalid / self-hit pixels are NaN (must be skipped in map_ros).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np
import rospy
from geometry_msgs.msg import Point, Pose, Quaternion
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image

from .coord_habitat_ros import (
    depth_meters_to_normalized,
    hab_pos_to_ros,
    hab_yaw_to_ros,
    mat4_hab_to_ros_pose,
)
from .depth_validity import prepare_depth_for_apexnav


def numpy_to_imgmsg(image: np.ndarray, encoding: str) -> Image:
    img = np.asarray(image)
    msg = Image()
    msg.height = int(img.shape[0])
    msg.width = int(img.shape[1])
    msg.encoding = encoding
    msg.is_bigendian = 0
    channels = 1 if img.ndim == 2 else int(img.shape[2])
    msg.step = msg.width * channels * img.dtype.itemsize
    msg.data = img.tobytes()
    return msg


class DynamicROSPublisher:
    def __init__(
        self,
        depth_min: float = 0.0,
        depth_max: float = 5.0,
        floor_y: float = 0.0,
        robot_scale: float = 1.0,
    ):
        self.depth_min = depth_min
        self.depth_max = depth_max
        # ################################
        # Navigable floor Habitat-Y; ROS Z published as AGL (hab_y - floor_y).
        # ################################
        self.floor_y = float(floor_y)
        self.robot_scale = float(robot_scale)
        self.env = None  # optional RangerCr10KinematicEnv for geometric self-hit
        self.depth_pub = rospy.Publisher("/habitat/camera_depth", Image, queue_size=10)
        self.rgb_pub = rospy.Publisher("/habitat/camera_rgb", Image, queue_size=10)
        self.odom_pub = rospy.Publisher("/habitat/odom", Odometry, queue_size=10)
        self.pose_pub = rospy.Publisher("/habitat/sensor_pose", Odometry, queue_size=10)
        self.last_depth_stats: dict = {}

    def set_floor_y(self, floor_y: float) -> None:
        self.floor_y = float(floor_y)

    def set_env(self, env: Any, robot_scale: Optional[float] = None) -> None:
        self.env = env
        if robot_scale is not None:
            self.robot_scale = float(robot_scale)

    def publish(
        self,
        rgb: np.ndarray,
        depth_m: np.ndarray,
        base_pos_hab: Sequence[float],
        base_yaw_hab: float,
        camera_T_hab,
        stamp: Optional[rospy.Time] = None,
        raw_camera_T_hab=None,
    ) -> dict:
        """Publish one synchronized observation bundle. Returns logged poses."""
        ros_time = stamp or rospy.Time.now()
        rgb = np.asarray(rgb)
        if rgb.ndim == 3 and rgb.shape[-1] == 4:
            rgb = rgb[..., :3]
        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.uint8)

        depth_raw = np.asarray(depth_m, dtype=np.float32)
        if depth_raw.ndim == 3:
            depth_raw = depth_raw[..., 0]

        # ################################
        # Invalid / robot-body pixels → NaN (never rewrite as max-range 5 m).
        # Geometric self-hit preferred; C++ map_ros skips NaN (adapter patch).
        # ################################
        depth_prep, dstats = prepare_depth_for_apexnav(
            depth_raw,
            env=self.env,
            camera_T_hab=raw_camera_T_hab if raw_camera_T_hab is not None else camera_T_hab,
            depth_min=self.depth_min,
            depth_max=self.depth_max,
            robot_scale=self.robot_scale,
            use_geometric_self_hit=self.env is not None,
        )
        self.last_depth_stats = dstats
        depth_norm = depth_meters_to_normalized(depth_prep, self.depth_min, self.depth_max)

        # ################################
        # Base / camera in ApexNav ROS: XY=(-hab_z,-hab_x), Z=hab_y-floor_y (AGL).
        # Ranger MOVE_FORWARD (sin,cos) in Habitat xz → ROS heading = hab_yaw + π.
        # ################################
        base_ros = hab_pos_to_ros(base_pos_hab, floor_y=self.floor_y)
        ros_yaw = float(hab_yaw_to_ros(base_yaw_hab))
        cy, sy = np.cos(ros_yaw * 0.5), np.sin(ros_yaw * 0.5)
        base_q = (0.0, 0.0, float(sy), float(cy))  # xyzw, yaw about ROS +Z

        cam_p, cam_q = mat4_hab_to_ros_pose(camera_T_hab, floor_y=self.floor_y)

        # ################################
        # Arm-mounted D455: plan odom XY = camera XY (ground proxy); yaw=chassis.
        # ################################
        odom_xy = (float(cam_p[0]), float(cam_p[1]))
        odom_z = float(base_ros[2])

        odom = Odometry()
        odom.header.stamp = ros_time
        odom.header.frame_id = "world"
        odom.child_frame_id = "base_link"
        odom.pose.pose = Pose(
            position=Point(odom_xy[0], odom_xy[1], odom_z),
            orientation=Quaternion(*base_q),
        )
        self.odom_pub.publish(odom)

        sensor = Odometry()
        sensor.header.stamp = ros_time
        sensor.header.frame_id = "world"
        sensor.child_frame_id = "d455_depth_optical_frame"
        sensor.pose.pose = Pose(
            position=Point(float(cam_p[0]), float(cam_p[1]), float(cam_p[2])),
            orientation=Quaternion(float(cam_q[0]), float(cam_q[1]), float(cam_q[2]), float(cam_q[3])),
        )
        self.pose_pub.publish(sensor)

        depth_msg = numpy_to_imgmsg(depth_norm, encoding="32FC1")
        depth_msg.header.stamp = ros_time
        depth_msg.header.frame_id = "d455_depth_optical_frame"
        self.depth_pub.publish(depth_msg)

        rgb_msg = numpy_to_imgmsg(rgb, encoding="rgb8")
        rgb_msg.header.stamp = ros_time
        rgb_msg.header.frame_id = "d455_depth_optical_frame"
        self.rgb_pub.publish(rgb_msg)

        finite_norm = depth_norm[np.isfinite(depth_norm)]
        return {
            "stamp": float(ros_time.to_sec()),
            "floor_y_hab": float(self.floor_y),
            "base_ros_chassis": base_ros.tolist(),
            "odom_ros_plan_proxy": [odom_xy[0], odom_xy[1], odom_z],
            "odom_xy_source": "d455_optical_xy_ground_proxy",
            "base_q_xyzw": list(base_q),
            "base_yaw_hab": float(base_yaw_hab),
            "base_yaw_ros": float(ros_yaw),
            "camera_ros": cam_p.tolist(),
            "camera_q_xyzw": cam_q.tolist(),
            "depth_norm_mean": float(np.mean(finite_norm)) if finite_norm.size else float("nan"),
            "depth_m_mean": float(np.nanmean(depth_prep)),
            "depth_validity": dstats,
            "invalid_depth_policy": "nan_skip_not_max_range",
            # backward-compatible alias (plan proxy, not chassis)
            "base_ros": [odom_xy[0], odom_xy[1], odom_z],
        }
