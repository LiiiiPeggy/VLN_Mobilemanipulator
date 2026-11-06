"""Publish Habitat Ranger observations to ApexNav ROS topics with dynamic EE pose.

Unlike baselines/ApexNav/habitat2ros/habitat_publisher.py (fixed +0.88 m height),
this publishes:
  - /habitat/odom         : REAL base_link pose (ROS world) by default
  - /habitat/sensor_pose  : D455 optical pose (ROS world) for map_ros
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
    mat4_hab_optical_to_ros_pose,
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
    # ################################
    # odom_xy_mode:
    #   "chassis" — real base XY + yaw (required default)
    #   "legacy_camera_xy_proxy" — old A/B behavior (camera XY, chassis yaw);
    #       NOT a real base_link; logs explicitly.
    # ################################
    def __init__(
        self,
        depth_min: float = 0.0,
        depth_max: float = 5.0,
        floor_y: float = 0.0,
        robot_scale: float = 1.0,
        odom_xy_mode: str = "chassis",
    ):
        self.depth_min = depth_min
        self.depth_max = depth_max
        self.floor_y = float(floor_y)
        self.robot_scale = float(robot_scale)
        self.odom_xy_mode = str(odom_xy_mode)
        self.env = None
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
        """Publish one synchronized observation bundle.

        ################################
        camera_T_hab MUST be Habitat OPTICAL frame (d455_depth_optical_frame).
        raw_camera_T_hab: same optical (preferred) for self-hit; if omitted,
        camera_T_hab is used. Do not pass Habitat render (optical@Rxπ) here.
        ################################
        """
        ros_time = stamp or rospy.Time.now()
        rgb = np.asarray(rgb)
        if rgb.ndim == 3 and rgb.shape[-1] == 4:
            rgb = rgb[..., :3]
        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.uint8)

        depth_raw = np.asarray(depth_m, dtype=np.float32)
        if depth_raw.ndim == 3:
            depth_raw = depth_raw[..., 0]

        optical_T = raw_camera_T_hab if raw_camera_T_hab is not None else camera_T_hab
        depth_prep, dstats = prepare_depth_for_apexnav(
            depth_raw,
            env=self.env,
            camera_T_hab=optical_T,
            depth_min=self.depth_min,
            depth_max=self.depth_max,
            robot_scale=self.robot_scale,
            use_geometric_self_hit=self.env is not None,
            camera_frame="optical",
        )
        self.last_depth_stats = dstats
        depth_norm = depth_meters_to_normalized(depth_prep, self.depth_min, self.depth_max)

        base_ros = hab_pos_to_ros(base_pos_hab, floor_y=self.floor_y)
        ros_yaw = float(hab_yaw_to_ros(base_yaw_hab))
        cy, sy = np.cos(ros_yaw * 0.5), np.sin(ros_yaw * 0.5)
        base_q = (0.0, 0.0, float(sy), float(cy))

        # ################################
        # sensor_pose: optical → ROS via C @ R_optical (map_ros pinhole).
        # ################################
        cam_p, cam_q = mat4_hab_optical_to_ros_pose(optical_T, floor_y=self.floor_y)

        if self.odom_xy_mode == "legacy_camera_xy_proxy":
            odom_xy = (float(cam_p[0]), float(cam_p[1]))
            odom_xy_source = "legacy_camera_xy_proxy"
        else:
            odom_xy = (float(base_ros[0]), float(base_ros[1]))
            odom_xy_source = "chassis_base_link"
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
            orientation=Quaternion(
                float(cam_q[0]), float(cam_q[1]), float(cam_q[2]), float(cam_q[3])
            ),
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
            "odom_ros": [odom_xy[0], odom_xy[1], odom_z],
            "odom_xy_source": odom_xy_source,
            "odom_xy_mode": self.odom_xy_mode,
            "base_q_xyzw": list(base_q),
            "base_yaw_hab": float(base_yaw_hab),
            "base_yaw_ros": float(ros_yaw),
            "camera_ros": cam_p.tolist(),
            "camera_q_xyzw": cam_q.tolist(),
            "camera_frame_published": "optical",
            "depth_norm_mean": float(np.mean(finite_norm)) if finite_norm.size else float("nan"),
            "depth_m_mean": float(np.nanmean(depth_prep)),
            "depth_validity": dstats,
            "invalid_depth_policy": "nan_skip_not_max_range",
            # planning start uses published odom XY
            "base_ros": [odom_xy[0], odom_xy[1], odom_z],
            # backward-compatible alias (was always the plan proxy)
            "odom_ros_plan_proxy": [odom_xy[0], odom_xy[1], odom_z],
        }
