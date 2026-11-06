"""Habitat (y-up) ↔ ApexNav/ROS world frame transforms.

ApexNav habitat_publisher uses:
  ROS_xyz = (-hab_z, -hab_x, hab_y)
We keep that XY convention so C++ map_ros depth projection stays consistent.

################################
ApexNav map_ros height filter assumes floor at ROS z≈0
(filter_min/max_height = 0.28/1.18 AGL; virtual_ground ≈ -0.34).
HM3D episode floors are often Habitat y ≠ 0 (e.g. yr17 ≈ -0.95).
Publishing absolute hab_y put furniture outside the filter band
(AGL≈1.23–2.13 only), so 2D occupied maps were dominated by tall
hits / poor free connectivity → Frontier A* NO_PASSABLE after raise.
Adapter fix: ROS_z = hab_y - floor_y (AGL), with floor_y from spawn.
################################
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np


def hab_pos_to_ros(p: Sequence[float], floor_y: float = 0.0) -> np.ndarray:
    x, y, z = float(p[0]), float(p[1]), float(p[2])
    # ################################
    # XY: ApexNav native (-z,-x). Z: height above local navigable floor.
    # ################################
    return np.array([-z, -x, y - float(floor_y)], dtype=np.float64)


def hab_yaw_to_ros(yaw_hab: float) -> float:
    """Habitat base yaw (about +Y) → ROS yaw (about +Z) for Ranger kinematic SE(2).

    ################################
    With MOVE_FORWARD = (sin(yaw), cos(yaw)) in Habitat xz and pos ROS=(-z,-x),
    the ROS motion heading is yaw_hab + π. Keep odom orientation aligned with motion.
    ################################
    """
    y = float(yaw_hab) + float(np.pi)
    return (y + np.pi) % (2.0 * np.pi) - np.pi


def _C_hab_to_ros() -> np.ndarray:
    # ROS_xyz = (-hab_z, -hab_x, hab_y) as a linear map on vectors.
    return np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=np.float64)


def hab_rot_to_ros(R: np.ndarray) -> np.ndarray:
    """Change-of-world-frame for rotations acting on Habitat-axis vectors.

    ################################
    R_ros = C @ R_hab @ C.T  is correct when both domain and codomain vectors
    are labeled in the SAME world convention (Habitat axes ↔ ROS axes).
    Do NOT use this for camera poses whose LOCAL axes are optical/render —
    use hab_optical_rot_to_ros / mat4_hab_optical_to_ros_pose instead.
    ################################
    """
    C = _C_hab_to_ros()
    return C @ np.asarray(R, dtype=np.float64).reshape(3, 3) @ C.T


def hab_optical_rot_to_ros(R_hab_optical: np.ndarray) -> np.ndarray:
    """Habitat optical pose → ROS world rotation for map_ros projection.

    ################################
    Optical local p_opt = [x, y, depth] (X right, Y down, Z fwd).
    world_hab = R_hab_optical @ p_opt + t_hab
    world_ros = C @ world_hab = (C @ R_hab_optical) @ p_opt + C @ t_hab
    Hence R_ros = C @ R_hab_optical  (no trailing C.T).
    ################################
    """
    C = _C_hab_to_ros()
    return C @ np.asarray(R_hab_optical, dtype=np.float64).reshape(3, 3)


def _mat4_to_Rp(T_flat16_or_mat) -> Tuple[np.ndarray, np.ndarray]:
    if hasattr(T_flat16_or_mat, "rotation"):
        T = T_flat16_or_mat
        R = np.array(T.rotation(), dtype=np.float64).reshape(3, 3)
        p = np.array([T.translation.x, T.translation.y, T.translation.z], dtype=np.float64)
    else:
        M = np.asarray(T_flat16_or_mat, dtype=np.float64).reshape(4, 4)
        R = M[:3, :3]
        p = M[:3, 3]
    return R, p


def mat4_hab_optical_to_ros_pose(
    T_flat16_or_mat, floor_y: float = 0.0
) -> Tuple[np.ndarray, np.ndarray]:
    """Optical Habitat Matrix4 → (pos_ros AGL, quat_xyzw) for /sensor_pose."""
    R, p = _mat4_to_Rp(T_flat16_or_mat)
    R_ros = hab_optical_rot_to_ros(R)
    p_ros = hab_pos_to_ros(p, floor_y=floor_y)
    return p_ros, _rot_to_xyzw(R_ros)


def mat4_hab_to_ros_pose(
    T_flat16_or_mat, floor_y: float = 0.0
) -> Tuple[np.ndarray, np.ndarray]:
    """Legacy world-axis pose convert (NOT for D455 optical → map_ros).

    ################################
    Kept for non-camera SE(3) that truly lives in Habitat world axes.
    Camera / depth projection MUST use mat4_hab_optical_to_ros_pose.
    ################################
    """
    R, p = _mat4_to_Rp(T_flat16_or_mat)
    R_ros = hab_rot_to_ros(R)
    p_ros = hab_pos_to_ros(p, floor_y=floor_y)
    return p_ros, _rot_to_xyzw(R_ros)

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
    """ApexNav C++ expects Habitat-normalized float32 depth in [0,1].

    ################################
    Preserve NaN (invalid / self-hit). Do not clip NaN to 0 — map_ros must skip
    those pixels so they never become max-range occupied spokes.
    ################################
    """
    d = np.asarray(depth_m, dtype=np.float32)
    if d.ndim == 3:
        d = d[..., 0]
    out = (d - min_d) / max(max_d - min_d, 1e-6)
    finite = np.isfinite(out)
    out = out.copy()
    out[finite] = np.clip(out[finite], 0.0, 1.0)
    return out.astype(np.float32)
