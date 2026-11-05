"""Publish Habitat Ranger observations to ApexNav ROS topics with dynamic EE pose.

Unlike baselines/ApexNav/habitat2ros/habitat_publisher.py (fixed +0.88 m height),
this publishes:
  - /habitat/odom         : base_link pose (ROS world)
  - /habitat/sensor_pose  : d455 optical / Habitat camera pose (ROS world)
  - /habitat/camera_rgb
  - /habitat/camera_depth : normalized float32 [0,1] as ApexNav C++ expects
"""

from __future__ import annotations

from typing import Optional, Sequence

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
        self_hit_min_depth_m: float = 0.65,
    ):
        self.depth_min = depth_min
        self.depth_max = depth_max
        # ################################
        # Navigable floor Habitat-Y; ROS Z published as AGL (hab_y - floor_y).
        # ################################
        self.floor_y = float(floor_y)
        # ################################
        # Arm-mounted D455 self-hit gate. ApexNav C++ overrides map_ros/mindist
        # with habitat depth_sensor.min_depth (=0.0), so launch mindist≠0 is
        # ineffective. Mask near metric depth here before normalize; keep
        # decode range [0,5] unchanged. 0.65 m covers 0.7× chassis/arm in FOV.
        # ################################
        self.self_hit_min_depth_m = float(self_hit_min_depth_m)
        self.depth_pub = rospy.Publisher("/habitat/camera_depth", Image, queue_size=10)
        self.rgb_pub = rospy.Publisher("/habitat/camera_rgb", Image, queue_size=10)
        self.odom_pub = rospy.Publisher("/habitat/odom", Odometry, queue_size=10)
        self.pose_pub = rospy.Publisher("/habitat/sensor_pose", Odometry, queue_size=10)

    def set_floor_y(self, floor_y: float) -> None:
        self.floor_y = float(floor_y)

    def publish(
        self,
        rgb: np.ndarray,
        depth_m: np.ndarray,
        base_pos_hab: Sequence[float],
        base_yaw_hab: float,
        camera_T_hab,
        stamp: Optional[rospy.Time] = None,
    ) -> dict:
        """Publish one synchronized observation bundle. Returns logged poses."""
        ros_time = stamp or rospy.Time.now()
        rgb = np.asarray(rgb)
        if rgb.ndim == 3 and rgb.shape[-1] == 4:
            rgb = rgb[..., :3]
        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.uint8)

        depth_m = np.asarray(depth_m, dtype=np.float32)
        if depth_m.ndim == 3:
            depth_m = depth_m[..., 0]
        # ################################
        # Replace self-hit / near-body pixels with max range so they do not
        # become OCCUPIED beside the optical frame (keeps Habitat decode 0–5).
        # ################################
        near_mask = (depth_m > 0.0) & (depth_m < self.self_hit_min_depth_m)
        n_near = int(np.count_nonzero(near_mask))
        if n_near:
            depth_m = depth_m.copy()
            depth_m[near_mask] = float(self.depth_max)

        depth_norm = depth_meters_to_normalized(depth_m, self.depth_min, self.depth_max)

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
        # Arm-mounted D455 is ~0.65 m ahead of base_link. ApexNav carves free
        # space from /map_ros/pose (camera) but plans from /odom_world. Using
        # chassis XY left the start cell UNKNOWN outside the 0.25 m A* bubble →
        # all Frontier A* fail → NO_PASSABLE (extreme search only helped when
        # object clouds existed). Publish odom planar XY = camera XY (ground
        # proxy), Z = base AGL, yaw = chassis yaw. Depth/sensor_pose stay true
        # optical SE3. Not optimistic=true; not inflation shrink; adapter only.
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
        # Keep child_frame_id as original string for planner compatibility, but pose is EE camera.
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
            "depth_norm_mean": float(np.mean(depth_norm)),
            "depth_m_mean": float(np.mean(depth_m)),
            "self_hit_min_depth_m": float(self.self_hit_min_depth_m),
            "self_hit_pixels_masked": int(n_near),
            # backward-compatible alias (plan proxy, not chassis)
            "base_ros": [odom_xy[0], odom_xy[1], odom_z],
        }
