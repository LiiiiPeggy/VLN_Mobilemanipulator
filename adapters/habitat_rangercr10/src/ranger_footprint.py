"""Ranger+CR10 footprint constants from Stage 4.10d MuJoCo / URDF (adapter-only).

################################
Used for offline clearance / oriented-footprint checks. Not fed into ApexNav.
################################
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

# MuJoCo ranger_cr10.xml base_link_col (half-extents, metres)
CHASSIS_HALF_L = 0.651  # along base +X (forward)
CHASSIS_HALF_W = 0.4347  # along base +Y (left)
CHASSIS_HALF_H = 0.21755
CHASSIS_BOX_POS = (0.0, -0.0033, -0.0571)  # MuJoCo base frame

# Wheel layout (URDF steering joint origins / LocoManip articulation_cfg)
WHEEL_X = 0.445
WHEEL_Y = 0.28
WHEEL_XY: List[Tuple[float, float]] = [
    (WHEEL_X, -WHEEL_Y),  # fr
    (WHEEL_X, WHEEL_Y),  # fl
    (-WHEEL_X, WHEEL_Y),  # rl
    (-WHEEL_X, -WHEEL_Y),  # rr
]
# Mesh / LocoManip measured rolling radius (floor-snap in Habitat may still use 0.125)
WHEEL_RADIUS_MESH = 0.1531
# URDF joint axis signs (fr/rr +Z, fl/rl -Z) → opposite roll signs
WHEEL_SIGN = (-1.0, 1.0, 1.0, -1.0)
STEERING_SIGN = -1.0  # LocoManip measured

# Default arm horizontal reach proxy (Stage 4.10d ARM_DEFAULT LOOK home): base XY
# outer camera ≈ 0.6–1.0 m forward of base origin (FK); use conservative circle for sweep.
ARM_HOME_XY_REACH_M = 1.05

CHASSIS_LENGTH = 2.0 * CHASSIS_HALF_L
CHASSIS_WIDTH = 2.0 * CHASSIS_HALF_W
CHASSIS_CIRCUM_R = float(math.hypot(CHASSIS_HALF_L, CHASSIS_HALF_W))


def oriented_rect_corners(
    x: float, z: float, yaw: float, half_l: float = CHASSIS_HALF_L, half_w: float = CHASSIS_HALF_W
) -> np.ndarray:
    """Habitat top-down (x,z) rectangle corners for chassis at pose. Forward=(sin yaw, cos yaw)."""
    fx, fz = math.sin(yaw), math.cos(yaw)
    # right = Y×forward in Hab → (cos, -sin) on xz
    rx, rz = math.cos(yaw), -math.sin(yaw)
    corners = []
    for s_l, s_w in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
        # ROS +Y is left = -right
        corners.append(
            (
                x + s_l * half_l * fx - s_w * half_w * rx,
                z + s_l * half_l * fz - s_w * half_w * rz,
            )
        )
    return np.asarray(corners, dtype=np.float64)


def footprint_report() -> Dict[str, float]:
    return {
        "chassis_half_length_m": CHASSIS_HALF_L,
        "chassis_half_width_m": CHASSIS_HALF_W,
        "chassis_length_m": CHASSIS_LENGTH,
        "chassis_width_m": CHASSIS_WIDTH,
        "chassis_circumscribed_radius_m": CHASSIS_CIRCUM_R,
        "wheel_track_half_y_m": WHEEL_Y,
        "wheel_base_half_x_m": WHEEL_X,
        "wheel_radius_mesh_m": WHEEL_RADIUS_MESH,
        "arm_home_xy_reach_m": ARM_HOME_XY_REACH_M,
        "min_corridor_width_for_straight_m": CHASSIS_WIDTH + 0.10,
        "min_turn_in_place_diameter_m": 2.0 * CHASSIS_CIRCUM_R + 0.10,
        "source": "MuJoCo base_link_col Stage4.10d + URDF wheel origins",
    }
