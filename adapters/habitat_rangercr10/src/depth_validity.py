"""Depth validity / self-hit masking for ApexNav map input (adapter-only).

################################
Do NOT replace invalid / self-hit depths with max-range (e.g. 5 m): ApexNav
map_ros projects those as real endpoints → radial OCCUPIED spokes while the
camera rotates. Invalid pixels must be NaN so C++ processDepthImage skips them
(no occupied endpoint, no free-space ray).
################################
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

# ################################
# Robot self-hit model: link spheres + bone capsules (1.0× radii).
# Scaled by robot_scale at call time. Prefer this over blanket near gates so
# real close furniture is kept while body/arm/chassis are NaN'd.
# ################################
_SELF_HIT_SPHERES_1X: List[Tuple[str, float]] = [
    ("base_link", 0.55),
    ("cr10_base_link", 0.14),
    ("cr10_Link1", 0.12),
    ("cr10_Link2", 0.11),
    ("cr10_Link3", 0.10),
    ("cr10_Link4", 0.09),
    ("cr10_Link5", 0.08),
    ("cr10_Link6", 0.08),
    ("gripper_base_link", 0.10),
    ("d455_link", 0.07),
]

# (parent_link, child_link, radius_1x) — covers elongated arm/mast geometry.
_SELF_HIT_CAPSULES_1X: List[Tuple[str, str, float]] = [
    ("base_link", "cr10_base_link", 0.28),
    ("cr10_base_link", "cr10_Link1", 0.12),
    ("cr10_Link1", "cr10_Link2", 0.11),
    ("cr10_Link2", "cr10_Link3", 0.10),
    ("cr10_Link3", "cr10_Link4", 0.09),
    ("cr10_Link4", "cr10_Link5", 0.08),
    ("cr10_Link5", "cr10_Link6", 0.08),
    ("cr10_Link6", "gripper_base_link", 0.09),
    ("gripper_base_link", "d455_link", 0.07),
]


def finite_metric_valid_mask(
    depth_m: np.ndarray, min_m: float = 1e-4, max_m: float = 5.0
) -> np.ndarray:
    d = np.asarray(depth_m, dtype=np.float32)
    if d.ndim == 3:
        d = d[..., 0]
    return np.isfinite(d) & (d > float(min_m)) & (d <= float(max_m))


def _hab_camera_cw(camera_T_hab) -> Tuple[np.ndarray, np.ndarray]:
    """Return (R_cw 3x3, t_cw 3,) world→camera for Habitat/Magnum camera."""
    if hasattr(camera_T_hab, "inverted"):
        T_cw = camera_T_hab.inverted()
        R_cw = np.array(T_cw.rotation(), dtype=np.float64).reshape(3, 3)
        t_cw = np.array(
            [T_cw.translation.x, T_cw.translation.y, T_cw.translation.z], dtype=np.float64
        )
        return R_cw, t_cw
    M = np.asarray(camera_T_hab, dtype=np.float64).reshape(4, 4)
    R_wc, t_wc = M[:3, :3], M[:3, 3]
    R_cw = R_wc.T
    t_cw = -R_cw @ t_wc
    return R_cw, t_cw


def _link_world_pos(env, name: str) -> Optional[np.ndarray]:
    link_ids = getattr(env, "link_ids", {}) or {}
    ao = getattr(env, "ao", None)
    if ao is None or name not in link_ids:
        return None
    try:
        T = ao.get_link_scene_node(link_ids[name]).absolute_transformation()
        return np.array([T.translation.x, T.translation.y, T.translation.z], dtype=np.float64)
    except Exception:
        return None


def _point_segment_dist2(
    p: np.ndarray, a: np.ndarray, b: np.ndarray
) -> np.ndarray:
    """Squared distance from points (N,3) to segment a–b."""
    ab = b - a
    denom = float(np.dot(ab, ab)) + 1e-12
    ap = p - a
    t = np.clip((ap @ ab) / denom, 0.0, 1.0)
    closest = a + t[:, None] * ab
    d = p - closest
    return np.einsum("ij,ij->i", d, d)


def geometric_self_hit_mask(
    env,
    depth_m: np.ndarray,
    camera_T_hab,
    hfov_deg: float = 79.0,
    depth_agree_m: float = 0.18,
    robot_scale: float = 1.0,
    pixel_stride: int = 2,
) -> np.ndarray:
    """Mask pixels whose back-projected 3D point hits robot spheres/capsules.

    ################################
    Habitat camera looks along -Z; metric depth is -z_cam. Real near furniture
    outside the robot hull is kept (distance-to-capsule test, not blanket near).
    ################################
    """
    d = np.asarray(depth_m, dtype=np.float32)
    if d.ndim == 3:
        d = d[..., 0]
    h, w = d.shape
    mask = np.zeros((h, w), dtype=bool)

    R_cw, t_cw = _hab_camera_cw(camera_T_hab)
    R_wc = R_cw.T
    t_wc = -R_cw.T @ t_cw

    fx = w / (2.0 * math.tan(hfov_deg * math.pi / 360.0))
    fy = h / (2.0 * math.tan(hfov_deg / w * h * math.pi / 360.0))
    cx, cy = (w - 1) * 0.5, (h - 1) * 0.5
    scale = float(robot_scale)

    # Collect robot primitives in world frame.
    spheres: List[Tuple[np.ndarray, float]] = []
    link_pts: List[np.ndarray] = []
    for name, radius_1x in _SELF_HIT_SPHERES_1X:
        p = _link_world_pos(env, name)
        if p is not None:
            spheres.append((p, radius_1x * scale))
            link_pts.append(p)
    # Extra links for AABB coverage (wheels / mast), not all need spheres.
    for extra in (
        "fr_wheel_link",
        "fl_wheel_link",
        "rl_wheel_link",
        "rr_wheel_link",
        "d455_depth_optical_frame",
    ):
        p = _link_world_pos(env, extra)
        if p is not None:
            link_pts.append(p)
    capsules: List[Tuple[np.ndarray, np.ndarray, float]] = []
    for a_name, b_name, radius_1x in _SELF_HIT_CAPSULES_1X:
        pa = _link_world_pos(env, a_name)
        pb = _link_world_pos(env, b_name)
        if pa is not None and pb is not None:
            capsules.append((pa, pb, radius_1x * scale))

    if not spheres and not capsules and not link_pts:
        return mask

    # ################################
    # Coarse robot AABB (link hull + pad). Catches mesh bulk that thin
    # capsules miss, without blanket-masking all near-range furniture.
    # ################################
    aabb_min = aabb_max = None
    if link_pts:
        P = np.stack(link_pts, axis=0)
        pad_aabb = 0.12 * scale + float(depth_agree_m)
        aabb_min = P.min(axis=0) - pad_aabb
        aabb_max = P.max(axis=0) + pad_aabb
        # Keep camera optical origin outside the hit set (depth at ~0).
        # Slightly shrink AABB along camera forward so we don't eat the
        # first centimetres of real scene glued to the lens.
        # (Handled implicitly: dd>0.05 and points at lens aren't in clouds.)

    # Strided candidate pixels with finite positive depth.
    vs = np.arange(0, h, max(1, int(pixel_stride)), dtype=np.int32)
    us = np.arange(0, w, max(1, int(pixel_stride)), dtype=np.int32)
    uu, vv = np.meshgrid(us, vs)
    uu = uu.reshape(-1)
    vv = vv.reshape(-1)
    dd = d[vv, uu].astype(np.float64)
    ok = np.isfinite(dd) & (dd > 0.05) & (dd <= 5.0)
    if not np.any(ok):
        return mask
    uu, vv, dd = uu[ok], vv[ok], dd[ok]

    # Habitat cam: +X right, +Y down, look -Z; depth along optical axis.
    x = (uu.astype(np.float64) - cx) * dd / fx
    y = (vv.astype(np.float64) - cy) * dd / fy
    z = -dd
    p_c = np.stack([x, y, z], axis=1)
    p_w = (p_c @ R_wc.T) + t_wc[None, :]

    hit = np.zeros(len(dd), dtype=bool)
    # ################################
    # Back-projected 3D point inside robot hull ⇒ self-hit. No extra depth-band
    # gate: surface depth already defines p_w; furniture in front lies outside.
    # depth_agree_m pads the collision radius for mesh vs sphere mismatch.
    # ################################
    pad = float(depth_agree_m)

    for center, radius in spheres:
        dist2 = np.sum((p_w - center[None, :]) ** 2, axis=1)
        hit |= dist2 <= (radius + pad) ** 2

    for a, b, radius in capsules:
        dist2 = _point_segment_dist2(p_w, a, b)
        hit |= dist2 <= (radius + pad) ** 2

    if aabb_min is not None and aabb_max is not None:
        inside = np.all((p_w >= aabb_min[None, :]) & (p_w <= aabb_max[None, :]), axis=1)
        hit |= inside

    if not np.any(hit):
        return mask

    mask[vv[hit], uu[hit]] = True

    # Dilate strided hits so neighboring pixels are covered.
    if pixel_stride > 1 and np.any(mask):
        ys, xs = np.where(mask)
        rad = max(1, int(pixel_stride))
        for y0, x0 in zip(ys.tolist(), xs.tolist()):
            mask[
                max(0, y0 - rad) : min(h, y0 + rad + 1),
                max(0, x0 - rad) : min(w, x0 + rad + 1),
            ] = True
        # Only keep dilation where original depth was finite positive (don't
        # invent hits on already-invalid pixels; prepare_depth NaNs those anyway).
        mask &= np.isfinite(d) & (d > 0.05)

    return mask


def prepare_depth_for_apexnav(
    depth_m: np.ndarray,
    *,
    env=None,
    camera_T_hab=None,
    depth_min: float = 0.0,
    depth_max: float = 5.0,
    hfov_deg: float = 79.0,
    robot_scale: float = 1.0,
    use_geometric_self_hit: bool = True,
    fallback_near_m: float = 0.35,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Return metric depth with invalid→NaN, plus filter stats.

    ################################
    Output is still metric metres; caller normalizes to [0,1] for ApexNav.
    NaN survives float32 ROS Image and must be skipped in map_ros.cpp.
    ################################
    """
    d = np.asarray(depth_m, dtype=np.float32).copy()
    if d.ndim == 3:
        d = d[..., 0]
    n_pix = int(d.size)
    valid0 = finite_metric_valid_mask(d, min_m=max(1e-4, float(depth_min)), max_m=float(depth_max))
    n_invalid_range = int((~valid0).sum())

    self_hit = np.zeros(d.shape, dtype=bool)
    geo_used = False
    if use_geometric_self_hit and env is not None and camera_T_hab is not None:
        try:
            self_hit = geometric_self_hit_mask(
                env,
                d,
                camera_T_hab,
                hfov_deg=hfov_deg,
                robot_scale=robot_scale,
            )
            geo_used = True
        except Exception:
            self_hit = np.zeros(d.shape, dtype=bool)
            geo_used = False

    # ################################
    # Fallback: only extremely near returns (lens dirt / mounting) if geometry
    # unavailable — does NOT blanket-mask all <0.65 m furniture.
    # ################################
    if not geo_used:
        self_hit = valid0 & (d > 0.0) & (d < float(fallback_near_m))

    n_self = int(self_hit.sum())
    out = d.copy()
    out[~valid0] = np.nan
    out[self_hit] = np.nan
    n_nan = int(np.isnan(out).sum())
    stats = {
        "n_pixels": float(n_pix),
        "n_invalid_range": float(n_invalid_range),
        "n_self_hit": float(n_self),
        "n_nan_published": float(n_nan),
        "frac_invalid_range": float(n_invalid_range) / max(n_pix, 1),
        "frac_self_hit": float(n_self) / max(n_pix, 1),
        "frac_nan_published": float(n_nan) / max(n_pix, 1),
        "geometric_self_hit": 1.0 if geo_used else 0.0,
        "fallback_near_m": float(fallback_near_m if not geo_used else 0.0),
        "note": "invalid→NaN; never rewritten as max-range",
    }
    return out, stats
