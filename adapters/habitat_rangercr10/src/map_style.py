"""Paper-style occupancy map palette (white background) for Demo panels.

################################
Stage-demo only: colors for ApexNav /grid_map visualization.
Does NOT alter ApexNav mapping / planning algorithms.
################################
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np

# ################################
# Paper palette (RGB uint8)
# bg/unknown: white; free: light gray; obstacle: dark; robot: blue; traj: orange
# ################################
PAPER_BG = (255, 255, 255)
PAPER_UNKNOWN = (255, 255, 255)
PAPER_FREE = (220, 220, 220)
PAPER_OCCUPIED = (40, 40, 40)
PAPER_INFLATE = (90, 90, 90)
PAPER_ROBOT = (30, 100, 220)
PAPER_TRAJ = (255, 140, 0)
PAPER_FRONTIER = (0, 170, 90)
PAPER_WAYPOINT = (200, 40, 40)
PAPER_PATH = (120, 60, 200)
PAPER_TEXT = (40, 40, 40)

# ################################
# ApexNav.rviz semantic_score_map (/grid_map/value_map) Intensity palette.
# Min Color 250;255;203 @ 0.10 → Max Color 204;0;0 @ 0.35 (Use rainbow: false).
# ################################
VALUE_MIN_COLOR = (250, 255, 203)  # pale yellow
VALUE_MAX_COLOR = (204, 0, 0)  # red
VALUE_MIN_INTENSITY = 0.10
VALUE_MAX_INTENSITY = 0.35
VALUE_OVERLAY_ALPHA = 0.62  # keep free/occ base visible under heat

# Legacy dark-theme colors written by older map_listener (for offline remap)
LEGACY_COLORS: Dict[str, Tuple[int, int, int]] = {
    "bg": (30, 30, 30),
    "unknown": (70, 70, 70),
    "free": (210, 190, 150),
    "occupied": (40, 40, 220),
    "robot": (50, 220, 255),
    "traj": (255, 180, 40),
    "text": (220, 220, 220),
}

PAPER_FROM_LEGACY: Dict[str, Tuple[int, int, int]] = {
    "bg": PAPER_BG,
    "unknown": PAPER_UNKNOWN,
    "free": PAPER_FREE,
    "occupied": PAPER_OCCUPIED,
    "robot": PAPER_ROBOT,
    "traj": PAPER_TRAJ,
    "text": PAPER_TEXT,
}


def remap_legacy_map_to_paper(
    img: np.ndarray,
    dist_thresh: float = 55.0,
    dilate_px: int = 1,
) -> np.ndarray:
    """Recolor a previously saved dark-theme map PNG to the white paper palette.

    Matching is nearest-palette in RGB; unmatched dark pixels → white bg.
    Optional 1px dilate on free/occ/traj/robot so sparse cloud rasters stay visible.
    """
    rgb = np.asarray(img[..., :3], dtype=np.float32)
    h, w, _ = rgb.shape
    flat = rgb.reshape(-1, 3)
    names = list(LEGACY_COLORS.keys())
    palette = np.asarray([LEGACY_COLORS[n] for n in names], dtype=np.float32)
    d = np.linalg.norm(flat[:, None, :] - palette[None, :, :], axis=2)
    idx = np.argmin(d, axis=1)
    mind = d[np.arange(d.shape[0]), idx]
    out = np.full((h, w, 3), PAPER_BG, dtype=np.uint8)
    layers = {}
    for i, name in enumerate(names):
        # ################################
        # Orange traj is often anti-aliased — slightly looser threshold.
        # ################################
        thr = dist_thresh + (25.0 if name == "traj" else 0.0)
        sel = (idx == i) & (mind <= thr)
        layers[name] = sel.reshape(h, w)

    def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
        if r <= 0:
            return mask
        try:
            import cv2

            k = 2 * r + 1
            return cv2.dilate(mask.astype(np.uint8), np.ones((k, k), np.uint8), iterations=1).astype(
                bool
            )
        except Exception:
            return mask

    # paint order: free → occupied → traj → robot (robot on top)
    for name in ("free", "occupied", "traj", "robot", "text"):
        m = layers.get(name)
        if m is None or not m.any():
            continue
        if name in ("free", "occupied", "traj", "robot"):
            m = _dilate(m, dilate_px)
        out[m] = PAPER_FROM_LEGACY[name]
    return out
