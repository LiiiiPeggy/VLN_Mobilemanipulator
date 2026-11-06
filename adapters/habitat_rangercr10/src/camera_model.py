"""Canonical D455 / Habitat camera intrinsics and ray helpers (adapter-only).

################################
Habitat CameraSensorSpec uses a single HFOV with square pixels. For W×H and
HFOV α (deg):
  fx = fy = (W/2) / tan(α/2)
  VFOV = 2 * atan((H/2) / fy)
Do NOT use VFOV ≈ HFOV * H/W (that yields fy≠fx and understates VFOV).

Optical frame (OpenCV / D455 / map_ros): +X right, +Y down, +Z forward.
Habitat render camera: +X right, +Y up, −Z forward.
Relation: T_render = T_optical @ Rx(π).
################################
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import numpy as np

from .constants import EE_RGB_HFOV_DEG, EE_RGB_RES

# EE_RGB_RES is (H, W) in constants
_DEFAULT_H, _DEFAULT_W = int(EE_RGB_RES[0]), int(EE_RGB_RES[1])


def pinhole_from_hfov(
    width: int = _DEFAULT_W,
    height: int = _DEFAULT_H,
    hfov_deg: float = float(EE_RGB_HFOV_DEG),
    *,
    cx: Optional[float] = None,
    cy: Optional[float] = None,
) -> Dict[str, float]:
    """Square-pixel K from Habitat-style HFOV. Independent of launch fy hacks."""
    w, h = int(width), int(height)
    alpha = math.radians(float(hfov_deg))
    fx = (w / 2.0) / math.tan(alpha / 2.0)
    fy = fx  # square pixels
    cx_v = float(cx) if cx is not None else (w / 2.0)
    cy_v = float(cy) if cy is not None else (h / 2.0)
    vfov = 2.0 * math.atan((h / 2.0) / fy)
    return {
        "fx": float(fx),
        "fy": float(fy),
        "cx": float(cx_v),
        "cy": float(cy_v),
        "width": float(w),
        "height": float(h),
        "hfov_deg": float(hfov_deg),
        "vfov_deg": float(math.degrees(vfov)),
        "pixel_model": "square_pixels_from_hfov",
        "source": "camera_model.pinhole_from_hfov",
    }


# Expected check values @ 640×480, HFOV=79° (task reference).
REF_K_640x480_HFOV79 = pinhole_from_hfov(640, 480, 79.0)


def legacy_broken_fy_from_hfov_aspect(
    width: int = 640, height: int = 480, hfov_deg: float = 79.0
) -> Dict[str, float]:
    """Historical wrong formula (HFOV×H/W) — for regression labels only."""
    w, h = int(width), int(height)
    fx = w / (2.0 * math.tan(hfov_deg * math.pi / 360.0))
    fy = h / (2.0 * math.tan(hfov_deg / w * h * math.pi / 360.0))
    return {
        "fx": float(fx),
        "fy": float(fy),
        "vfov_deg_implied": float(hfov_deg * h / w),
        "note": "LEGACY_WRONG: VFOV≈HFOV*H/W; do not use in production",
    }


def optical_ray_dir(u: float, v: float, K: Dict[str, float]) -> np.ndarray:
    """Unit ray in optical camera frame for pixel (u,v). Depth along +Z."""
    fx, fy, cx, cy = K["fx"], K["fy"], K["cx"], K["cy"]
    x = (float(u) - cx) / fx
    y = (float(v) - cy) / fy
    d = np.array([x, y, 1.0], dtype=np.float64)
    return d / (np.linalg.norm(d) + 1e-12)


def unproject_optical(
    u: float, v: float, depth_m: float, K: Dict[str, float]
) -> np.ndarray:
    """Metric 3D point in optical frame (Z = optical-axis depth)."""
    fx, fy, cx, cy = K["fx"], K["fy"], K["cx"], K["cy"]
    z = float(depth_m)
    return np.array(
        [(float(u) - cx) * z / fx, (float(v) - cy) * z / fy, z], dtype=np.float64
    )


def unproject_habitat_render(
    u: float, v: float, depth_m: float, K: Dict[str, float]
) -> np.ndarray:
    """Metric 3D in Habitat render camera (look −Z, Y up). Depth along look axis."""
    p_opt = unproject_optical(u, v, depth_m, K)
    # optical → render: Rx(π) on local point: (x,y,z)_opt → (x,−y,−z)_render
    return np.array([p_opt[0], -p_opt[1], -p_opt[2]], dtype=np.float64)


def rx_pi() -> np.ndarray:
    return np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]], dtype=np.float64)


def optical_R_from_render_R(R_render: np.ndarray) -> np.ndarray:
    """R_render = R_optical @ Rx(π)  ⇒  R_optical = R_render @ Rx(π)."""
    return np.asarray(R_render, dtype=np.float64).reshape(3, 3) @ rx_pi()


def project_optical(p_cam: np.ndarray, K: Dict[str, float]) -> Tuple[float, float]:
    """Project optical-frame point to pixel; returns (u,v)."""
    x, y, z = float(p_cam[0]), float(p_cam[1]), float(p_cam[2])
    if abs(z) < 1e-9:
        return float("nan"), float("nan")
    u = K["fx"] * (x / z) + K["cx"]
    v = K["fy"] * (y / z) + K["cy"]
    return float(u), float(v)
