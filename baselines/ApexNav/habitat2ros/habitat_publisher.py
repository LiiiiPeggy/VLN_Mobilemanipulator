import rospy
from sensor_msgs.msg import Image
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Pose, Quaternion, Point
from habitat.core.simulator import Observations
import numpy as np
from copy import deepcopy


def quaternion_from_euler(roll, pitch, yaw):
    """Minimal replacement for tf.transformations.quaternion_from_euler (xyzw)."""
    cy = np.cos(yaw * 0.5)
    sy = np.sin(yaw * 0.5)
    cp = np.cos(pitch * 0.5)
    sp = np.sin(pitch * 0.5)
    cr = np.cos(roll * 0.5)
    sr = np.sin(roll * 0.5)
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    w = cr * cp * cy + sr * sp * sy
    return (float(x), float(y), float(z), float(w))


def numpy_to_imgmsg(image: np.ndarray, encoding: str) -> Image:
    """Build sensor_msgs/Image without cv_bridge (Noetic cv_bridge needs py3.8 boost)."""
    img = np.asarray(image)
    msg = Image()
    msg.height = int(img.shape[0])
    msg.width = int(img.shape[1])
    msg.encoding = encoding
    msg.is_bigendian = 0
    if img.ndim == 2:
        channels = 1
    else:
        channels = int(img.shape[2])
    msg.step = msg.width * channels * img.dtype.itemsize
    msg.data = img.tobytes()
    return msg


class ROSPublisher:
    def __init__(self):
        # Create ROS publishers
        self.depth_pub = rospy.Publisher("/habitat/camera_depth", Image, queue_size=10)
        self.rgb_pub = rospy.Publisher("/habitat/camera_rgb", Image, queue_size=10)
        self.odom_pub = rospy.Publisher("/habitat/odom", Odometry, queue_size=10)
        self.pose_pub = rospy.Publisher("/habitat/sensor_pose", Odometry, queue_size=10)

    def publish_depth(self, ros_time, depth_image):
        depth = np.asarray(depth_image)
        # Habitat depth is often float32 HxW or HxWx1 meters
        if depth.ndim == 3 and depth.shape[-1] == 1:
            depth = depth[..., 0]
        if depth.dtype != np.float32:
            depth = depth.astype(np.float32)
        depth_msg = numpy_to_imgmsg(depth, encoding="32FC1")
        depth_msg.header.stamp = ros_time
        depth_msg.header.frame_id = "world"
        self.depth_pub.publish(depth_msg)

    def publish_rgb(self, ros_time, rgb_image):
        rgb = np.asarray(rgb_image)
        if rgb.ndim == 3 and rgb.shape[-1] == 4:
            rgb = rgb[..., :3]
        if rgb.dtype != np.uint8:
            rgb = rgb.astype(np.uint8)
        rgb_msg = numpy_to_imgmsg(rgb, encoding="rgb8")
        rgb_msg.header.stamp = ros_time
        rgb_msg.header.frame_id = "world"
        self.rgb_pub.publish(rgb_msg)

    def publish_robot_odom(self, ros_time, gps, compass):
        copy_compass = deepcopy(compass)
        if isinstance(copy_compass, (list, tuple, np.ndarray)):
            copy_compass = float(np.asarray(copy_compass).reshape(-1)[0])
        gps = np.asarray(gps).reshape(-1)
        odom = Odometry()
        odom.header.stamp = ros_time
        odom.header.frame_id = "world"
        odom.child_frame_id = "base_link"
        odom.pose.pose = Pose(
            position=Point(-float(gps[2]), -float(gps[0]), float(gps[1])),
            orientation=Quaternion(*quaternion_from_euler(0, 0, copy_compass)),
        )
        self.odom_pub.publish(odom)

    def publish_camera_odom(self, ros_time, gps, compass, pitch):
        copy_compass = deepcopy(compass)
        copy_pitch = deepcopy(pitch)
        if isinstance(copy_compass, (list, tuple, np.ndarray)):
            copy_compass = float(np.asarray(copy_compass).reshape(-1)[0])
        copy_pitch = float(copy_pitch)
        gps = np.asarray(gps).reshape(-1)
        sensor_pose = Odometry()
        sensor_pose.header.stamp = ros_time
        sensor_pose.header.frame_id = "world"
        sensor_pose.child_frame_id = "base_link"
        sensor_pose.pose.pose = Pose(
            position=Point(-float(gps[2]), -float(gps[0]), float(gps[1]) + 0.88),
            orientation=Quaternion(
                *quaternion_from_euler(
                    copy_pitch + np.pi / 2.0, np.pi, copy_compass + np.pi / 2.0
                )
            ),
        )
        self.pose_pub.publish(sensor_pose)

    def habitat_publish_ros_topic(self, observations: Observations):
        depth_image = observations["depth"]
        rgb_image = observations["rgb"]
        gps = observations["gps"]
        compass = observations["compass"]
        camera_pitch = observations["camera_pitch"]
        ros_time = rospy.Time.now()
        self.publish_depth(ros_time, depth_image)
        self.publish_camera_odom(ros_time, gps, compass, camera_pitch)
        self.publish_rgb(ros_time, rgb_image)
        self.publish_robot_odom(ros_time, gps, compass)
