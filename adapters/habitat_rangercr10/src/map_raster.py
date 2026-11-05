"""Resolution-matched rasterization for ApexNav /grid_map Demo panels.

################################
Demo-only. Does NOT change map resolution, occupancy logs, inflation, or
planner inputs. Fills each published cell as a solid footprint matching
sdf_map/resolution (default 0.05 m) so adjacent cells abut without fake
1-pixel "borders". No morphological open/close / large blur.
################################
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

import numpy as np


DEFAULT_MAP_RESOLUTION_M = 0.05  # ApexNav sdf_map/resolution


def estimate_resolution_m(
    *clouds: np.ndarray, default: float = DEFAULT_MAP_RESOLUTION_M
) -> float:
    """Estimate grid resolution from cell-center spacing (positive diffs)."""
    diffs = []
    for xy in clouds:
        if xy is None or len(xy) < 2:
            continue
        arr = np.asarray(xy, dtype=np.float64)
        if arr.ndim != 2 or arr.shape[1] < 2:
            continue
        for col in (0, 1):
            u = np.unique(np.round(arr[:, col], 6))
            d = np.diff(u)
            d = d[d > 1e-4]
            if d.size:
                diffs.append(float(np.min(d)))
    if not diffs:
        return float(default)
    # Prefer values near ApexNav 0.05; clamp outliers.
    r = float(np.median(diffs))
    if r < 0.02 or r > 0.2:
        return float(default)
    return r


def world_to_pix(
    xy: Sequence[float],
    *,
    center_xy: Tuple[float, float],
    scale: float,
    width: int,
    height: int,
) -> Tuple[int, int]:
    px = int((float(xy[0]) - center_xy[0]) * scale + width / 2)
    py = int(-(float(xy[1]) - center_xy[1]) * scale + height / 2)
    return px, py


def cell_pixel_rect(
    x: float,
    y: float,
    *,
    center_xy: Tuple[float, float],
    scale: float,
    width: int,
    height: int,
    resolution_m: float,
) -> Optional[Tuple[int, int, int, int]]:
    """Return inclusive pixel rect (x0,y0,x1,y1) covering one map cell footprint.

    Cell is axis-aligned in world: [x-res/2, x+res/2] × [y-res/2, y+res/2]
    (ApexNav publishes cell centers). Adjacent cells share edges → no gap/border.
    """
    res = float(resolution_m)
    half = 0.5 * res
    # World corners (ROS x-y). Image y flips.
    corners = (
        (x - half, y - half),
        (x - half, y + half),
        (x + half, y - half),
        (x + half, y + half),
    )
    pxs, pys = [], []
    for cx, cy in corners:
        px = (cx - center_xy[0]) * scale + width / 2.0
        py = -(cy - center_xy[1]) * scale + height / 2.0
        pxs.append(px)
        pys.append(py)
    x0 = int(math.floor(min(pxs)))
    x1 = int(math.ceil(max(pxs))) - 1
    y0 = int(math.floor(min(pys)))
    y1 = int(math.ceil(max(pys))) - 1
    # Ensure at least 1×1 when scale is tiny.
    if x1 < x0:
        x1 = x0
    if y1 < y0:
        y1 = y0
    # Clip to canvas
    x0c = max(0, x0)
    y0c = max(0, y0)
    x1c = min(width - 1, x1)
    y1c = min(height - 1, y1)
    if x1c < x0c or y1c < y0c:
        return None
    return x0c, y0c, x1c, y1c


def fill_cells_rgb(
    canvas: np.ndarray,
    xy: np.ndarray,
    color: Tuple[int, int, int],
    *,
    center_xy: Tuple[float, float],
    scale: float,
    resolution_m: float,
    mask: Optional[np.ndarray] = None,
    write_rgb: bool = True,
) -> None:
    """Paint each cell as a solid rectangle (no per-cell outline)."""
    if xy is None or len(xy) == 0:
        return
    h, w = canvas.shape[:2]
    pts = np.asarray(xy, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] < 2:
        return
    # Deduplicate centers on the native grid to avoid redundant fills.
    qx = np.round(pts[:, 0] / resolution_m) * resolution_m
    qy = np.round(pts[:, 1] / resolution_m) * resolution_m
    uniq = {}
    for x, y in zip(qx, qy):
        uniq[(float(x), float(y))] = None
    for x, y in uniq.keys():
        rect = cell_pixel_rect(
            x,
            y,
            center_xy=center_xy,
            scale=scale,
            width=w,
            height=h,
            resolution_m=resolution_m,
        )
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        if write_rgb:
            canvas[y0 : y1 + 1, x0 : x1 + 1] = color
        if mask is not None:
            mask[y0 : y1 + 1, x0 : x1 + 1] = True


def fill_value_cells(
    canvas: np.ndarray,
    xyi: np.ndarray,
    *,
    center_xy: Tuple[float, float],
    scale: float,
    resolution_m: float,
    free_mask: np.ndarray,
    occ_mask: np.ndarray,
    intensity_to_rgb,
    alpha: float,
) -> int:
    """Overlay value heat as filled cells; skip occupied; prefer free."""
    if xyi is None or len(xyi) == 0:
        return 0
    h, w = canvas.shape[:2]
    pts = np.asarray(xyi, dtype=np.float64)
    # Keep max intensity per quantized cell (no averaging that softens peaks).
    best = {}
    for row in pts:
        x, y, inten = float(row[0]), float(row[1]), float(row[2])
        key = (
            round(x / resolution_m) * resolution_m,
            round(y / resolution_m) * resolution_m,
        )
        if key not in best or inten > best[key]:
            best[key] = inten
    n = 0
    a = float(alpha)
    for (x, y), inten in best.items():
        rect = cell_pixel_rect(
            x,
            y,
            center_xy=center_xy,
            scale=scale,
            width=w,
            height=h,
            resolution_m=resolution_m,
        )
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        block_occ = occ_mask[y0 : y1 + 1, x0 : x1 + 1]
        if block_occ.any():
            # Do not paint over occupied pixels inside the footprint.
            pass
        heat = np.asarray(intensity_to_rgb(inten), dtype=np.float64)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if occ_mask[yy, xx]:
                    continue
                if not free_mask[yy, xx]:
                    base = canvas[yy, xx]
                    is_freeish = int(base[0]) < 240 and abs(int(base[0]) - int(base[1])) < 25
                    if not is_freeish:
                        continue
                base = canvas[yy, xx].astype(np.float64)
                canvas[yy, xx] = np.clip((1.0 - a) * base + a * heat, 0, 255).astype(np.uint8)
                n += 1
    return n
