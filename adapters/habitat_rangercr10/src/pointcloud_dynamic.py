"""Object point clouds using full camera SE(3) (adapter layer; does not patch ApexNav)."""

from __future__ import annotations

from typing import List, Sequence

import cv2
import numpy as np
import rospy
from sensor_msgs.msg import PointCloud2, PointField

from .camera_model import pinhole_from_hfov
from .coord_habitat_ros import hab_optical_rot_to_ros, hab_pos_to_ros


def _get_point_cloud(depth: np.ndarray, mask: np.ndarray, K: dict) -> np.ndarray:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return np.zeros((0, 3), dtype=np.float32)
    z = depth[ys, xs]
    # Optical local: +Z = metric depth along optical axis (map_ros convention).
    x = (xs - K["cx"]) * z / K["fx"]
    y = (ys - K["cy"]) * z / K["fy"]
    return np.stack([x, y, z], axis=1).astype(np.float32)


def convert_to_pointcloud2(points: np.ndarray) -> PointCloud2:
    msg = PointCloud2()
    try:
        msg.header.stamp = rospy.Time.now()
    except Exception:
        msg.header.stamp = rospy.Time(0)
    msg.header.frame_id = "world"
    msg.height = 1
    msg.width = points.shape[0]
    msg.fields = [
        PointField("x", 0, PointField.FLOAT32, 1),
        PointField("y", 4, PointField.FLOAT32, 1),
        PointField("z", 8, PointField.FLOAT32, 1),
        PointField("intensity", 12, PointField.FLOAT32, 1),
    ]
    msg.is_bigendian = False
    msg.point_step = 16
    msg.row_step = msg.point_step * points.shape[0]
    msg.is_dense = True
    if points.shape[0] == 0:
        msg.data = b""
        return msg
    if points.shape[1] == 3:
        pts = np.concatenate([points, np.ones((points.shape[0], 1), np.float32)], axis=1)
    else:
        pts = points.astype(np.float32)
    msg.data = pts.astype(np.float32).tobytes()
    return msg


def object_clouds_from_masks(
    depth_m: np.ndarray,
    masks: Sequence[np.ndarray],
    camera_T_hab,
    hfov_deg: float = 79.0,
    min_depth: float = 0.0,
    max_depth: float = 5.0,
    floor_y: float = 0.0,
) -> List[PointCloud2]:
    """Project masks with OPTICAL Habitat T → ROS world (C @ R_optical)."""
    if hasattr(camera_T_hab, "rotation"):
        R_hab = np.array(camera_T_hab.rotation(), dtype=np.float64).reshape(3, 3)
        p_hab = np.array(
            [camera_T_hab.translation.x, camera_T_hab.translation.y, camera_T_hab.translation.z],
            dtype=np.float64,
        )
    else:
        M = np.asarray(camera_T_hab, dtype=np.float64).reshape(4, 4)
        R_hab, p_hab = M[:3, :3], M[:3, 3]
    # ################################
    # camera_T_hab must be optical (not render/ee_T). R_ros = C @ R_optical.
    # ################################
    R_ros = hab_optical_rot_to_ros(R_hab)
    p_ros = hab_pos_to_ros(p_hab, floor_y=floor_y)

    depth = np.asarray(depth_m, dtype=np.float32)
    if depth.ndim == 3:
        depth = depth[..., 0]
    h, w = depth.shape
    K = pinhole_from_hfov(w, h, hfov_deg)

    out = []
    for object_mask in masks:
        mask = object_mask.astype(np.uint8)
        if mask.max() > 1:
            mask = (mask > 0).astype(np.uint8)
        mask = cv2.erode(mask * 255, None, iterations=1)
        valid = depth.copy()
        local = _get_point_cloud(valid, mask, K)
        if local.shape[0] == 0:
            out.append(PointCloud2())
            continue
        keep = (local[:, 2] >= min_depth) & (local[:, 2] <= max_depth * 0.95)
        local = local[keep]
        if local.shape[0] == 0:
            out.append(PointCloud2())
            continue
        world = (R_ros @ local.T).T + p_ros[None, :]
        within = np.ones((world.shape[0], 1), dtype=np.float32)
        pts = np.concatenate([world.astype(np.float32), within], axis=1)
        out.append(convert_to_pointcloud2(pts))
    return out
