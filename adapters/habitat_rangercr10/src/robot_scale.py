"""Uniform robot scale for Habitat adapter (proxy experiments only).

################################
Does NOT modify LocoManip URDF / MuJoCo / PPO. Scale applies only inside
``adapters/habitat_rangercr10`` via a generated URDF + scaled constants.
Tag all such runs as ``scaled_robot_proxy_070`` — never claim real Ranger safety.
################################
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from . import ranger_footprint as fp
from .constants import APEXNAV_CAM_HEIGHT_M, URDF_HABITAT, URDF_HABITAT_PIN

# ################################
# Fixed proxy scale for this branch; do not scan other ratios here.
# ################################
ROBOT_SCALE_070 = 0.70
PROXY_TAG_070 = "scaled_robot_proxy_070"

# Historical Habitat floor-snap pin (1.0×)
BASE_Y_1X = 0.4419
WHEEL_RADIUS_SNAP_1X = 0.125


def scale_tag(scale: float) -> str:
    s = float(scale)
    if abs(s - 1.0) < 1e-9:
        return "robot_scale_1x_real"
    if abs(s - ROBOT_SCALE_070) < 1e-9:
        return PROXY_TAG_070
    return f"scaled_robot_proxy_{int(round(s * 100)):03d}"


def scaled_urdf_path(scale: float = ROBOT_SCALE_070) -> str:
    """Adapter-owned scaled URDF path (meshes still absolute on shared disk)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "assets" / "urdf"
    root.mkdir(parents=True, exist_ok=True)
    tag = f"s{int(round(float(scale) * 100)):03d}"
    return str(root / f"rangercr10lidar_habitat_{URDF_HABITAT_PIN}_{tag}.urdf")


def resolve_urdf(scale: float, urdf_override: Optional[str] = None) -> str:
    if urdf_override:
        return urdf_override
    if abs(float(scale) - 1.0) < 1e-9:
        return URDF_HABITAT
    from .scale_urdf import ensure_scaled_urdf

    return ensure_scaled_urdf(float(scale))


def footprint_at_scale(scale: float) -> Dict[str, float]:
    s = float(scale)
    half_l = fp.CHASSIS_HALF_L * s
    half_w = fp.CHASSIS_HALF_W * s
    circum = float(math.hypot(half_l, half_w))
    return {
        "robot_scale": s,
        "scale_tag": scale_tag(s),
        "chassis_half_length_m": half_l,
        "chassis_half_width_m": half_w,
        "chassis_length_m": 2.0 * half_l,
        "chassis_width_m": 2.0 * half_w,
        "chassis_circumscribed_radius_m": circum,
        "wheel_track_half_y_m": fp.WHEEL_Y * s,
        "wheel_base_half_x_m": fp.WHEEL_X * s,
        "wheel_radius_mesh_m": fp.WHEEL_RADIUS_MESH * s,
        "wheel_radius_snap_m": WHEEL_RADIUS_SNAP_1X * s,
        "default_base_y_m": BASE_Y_1X * s,
        "arm_home_xy_reach_m": fp.ARM_HOME_XY_REACH_M * s,
        "cam_height_target_m": APEXNAV_CAM_HEIGHT_M * s,
        "min_corridor_width_for_straight_m": 2.0 * half_w + 0.10,
        "min_turn_in_place_diameter_m": 2.0 * circum + 0.10,
        "source_1x": "MuJoCo base_link_col Stage4.10d + URDF wheel origins",
        "note": "proxy geometric scale; not a real Ranger resize",
    }


def wheel_xy_at_scale(scale: float) -> List[Tuple[float, float]]:
    s = float(scale)
    return [(x * s, y * s) for x, y in fp.WHEEL_XY]
