"""Habitat (y-up) ↔ ApexNav/ROS world frame transforms.

ApexNav habitat_publisher uses:
  ROS_xyz = (-hab_z, -hab_x, hab_y)
We keep that convention so C++ map_ros depth projection stays consistent.
"""

from __future__ import annotations

from typing import Sequence, Tuple

import numpy as np


def hab_pos_to_ros(p: Sequence[float]) -> np.ndarray:
    x, y, z = float(p[0]), float(p[1]), float(p[2])
    return np.array([-z, -x, y], dtype=np.float64)


def hab_rot_to_ros(R: np.ndarray) -> np.ndarray:
    """R maps habitat vectors; return R in ROS world axes."""
    C = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=np.float64)
    return C @ R @ C.T


def mat4_hab_to_ros_pose(T_flat16_or_mat) -> Tuple[np.ndarray, np.ndarray]:
    """Return (pos_ros xyz, quat_xyzw) from Habitat Matrix4 / 4x4."""
    if hasattr(T_flat16_or_mat, "rotation"):
        # magnum Matrix4
        T = T_flat16_or_mat
        R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
        p = np.array([T.translation.x, T.translation.y, T.translation.z], dtype=np.float64)
    else:
        M = np.asarray(T_flat16_or_mat, dtype=np.float64).reshape(4, 4)
        # Magnum column-major flat → if already 4x4 row-major from list builder, handle both
        R = M[:3, :3]
        p = M[:3, 3]
    R_ros = hab_rot_to_ros(R)
    p_ros = hab_pos_to_ros(p)
    # rotation matrix → xyzw
    q = _rot_to_xyzw(R_ros)
    return p_ros, q


def _rot_to_xyzw(R: np.ndarray) -> np.ndarray:
    tr = float(np.trace(R))
    if tr > 0:
        s = np.sqrt(tr + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x, y, z = (R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x, y, z = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x, y, z = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s
    q = np.array([x, y, z, w], dtype=np.float64)
    q /= np.linalg.norm(q) + 1e-12
    return q


def depth_meters_to_normalized(depth_m: np.ndarray, min_d: float = 0.0, max_d: float = 5.0) -> np.ndarray:
    """ApexNav C++ expects Habitat-normalized float32 depth in [0,1]."""
    d = np.asarray(depth_m, dtype=np.float32)
    if d.ndim == 3:
        d = d[..., 0]
    out = (d - min_d) / max(max_d - min_d, 1e-6)
    return np.clip(out, 0.0, 1.0).astype(np.float32)
