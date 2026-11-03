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

from .coord_habitat_ros import depth_meters_to_normalized, hab_pos_to_ros, mat4_hab_to_ros_pose


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
    def __init__(self, depth_min: float = 0.0, depth_max: float = 5.0):
        self.depth_min = depth_min
        self.depth_max = depth_max
        self.depth_pub = rospy.Publisher("/habitat/camera_depth", Image, queue_size=10)
        self.rgb_pub = rospy.Publisher("/habitat/camera_rgb", Image, queue_size=10)
        self.odom_pub = rospy.Publisher("/habitat/odom", Odometry, queue_size=10)
        self.pose_pub = rospy.Publisher("/habitat/sensor_pose", Odometry, queue_size=10)

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

        depth_norm = depth_meters_to_normalized(depth_m, self.depth_min, self.depth_max)

        # Base odom: Habitat yaw about +Y → ROS yaw about +Z with axis remap.
        # Using same convention as original: orientation yaw = compass only about Z in ROS.
        # Original used quaternion_from_euler(0,0,compass) with ROS pose (-z,-x,y).
        # Habitat yaw (about Y): rotating +yaw moves +X toward -Z in hab → ROS yaw ≈ -hab_yaw
        # Empirically match original gps/compass path: compass was habitat rotation about Y.
        base_ros = hab_pos_to_ros(base_pos_hab)
        # Match habitat_publisher robot odom: yaw = compass (hab yaw) about ROS Z
        cy, sy = np.cos(base_yaw_hab * 0.5), np.sin(base_yaw_hab * 0.5)
        base_q = (0.0, 0.0, float(sy), float(cy))  # xyzw, yaw about Z

        odom = Odometry()
        odom.header.stamp = ros_time
        odom.header.frame_id = "world"
        odom.child_frame_id = "base_link"
        odom.pose.pose = Pose(
            position=Point(float(base_ros[0]), float(base_ros[1]), float(base_ros[2])),
            orientation=Quaternion(*base_q),
        )
        self.odom_pub.publish(odom)

        cam_p, cam_q = mat4_hab_to_ros_pose(camera_T_hab)
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
            "base_ros": base_ros.tolist(),
            "base_q_xyzw": list(base_q),
            "camera_ros": cam_p.tolist(),
            "camera_q_xyzw": cam_q.tolist(),
            "depth_norm_mean": float(np.mean(depth_norm)),
            "depth_m_mean": float(np.mean(depth_m)),
        }
