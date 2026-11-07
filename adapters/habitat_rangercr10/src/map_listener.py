"""Subscribe to ApexNav online grid_map PointCloud2 topics for demo panels."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from .map_raster import (
    DEFAULT_MAP_RESOLUTION_M,
    estimate_resolution_m,
    fill_cells_rgb,
    fill_value_cells,
)
from .map_style import (
    PAPER_BG,
    PAPER_FREE,
    PAPER_OCCUPIED,
    PAPER_ROBOT,
    PAPER_TEXT,
    PAPER_TRAJ,
    PAPER_UNKNOWN,
    VALUE_MAX_COLOR,
    VALUE_MAX_INTENSITY,
    VALUE_MIN_COLOR,
    VALUE_MIN_INTENSITY,
    VALUE_OVERLAY_ALPHA,
)

try:
    import rospy
    from sensor_msgs.msg import PointCloud2
    from sensor_msgs import point_cloud2 as pc2
    from std_msgs.msg import Float64
except Exception:  # pragma: no cover
    rospy = None
    PointCloud2 = object  # type: ignore
    pc2 = None
    Float64 = object  # type: ignore


def _cloud_xy(msg) -> np.ndarray:
    if pc2 is None or msg is None or getattr(msg, "width", 0) == 0:
        return np.zeros((0, 2), dtype=np.float64)
    pts = list(pc2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True))
    if not pts:
        return np.zeros((0, 2), dtype=np.float64)
    arr = np.asarray(pts, dtype=np.float64)
    # ApexNav ROS map is Z-up: use x,y as planar
    return arr[:, :2]


def _cloud_xyi(msg) -> np.ndarray:
    """Return Nx3 array of (x, y, intensity) from PointXYZI value_map cloud."""
    if pc2 is None or msg is None or getattr(msg, "width", 0) == 0:
        return np.zeros((0, 3), dtype=np.float64)
    try:
        pts = list(
            pc2.read_points(msg, field_names=("x", "y", "intensity"), skip_nans=True)
        )
    except Exception:
        # Some bags only expose x,y,z — treat z as unused, intensity missing.
        return np.zeros((0, 3), dtype=np.float64)
    if not pts:
        return np.zeros((0, 3), dtype=np.float64)
    return np.asarray(pts, dtype=np.float64)


def value_intensity_to_rgb(intensity: float) -> Tuple[int, int, int]:
    """Map value_map intensity → ApexNav.rviz yellow→red (no rainbow)."""
    lo, hi = float(VALUE_MIN_INTENSITY), float(VALUE_MAX_INTENSITY)
    t = (float(intensity) - lo) / max(hi - lo, 1e-6)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    c0 = np.asarray(VALUE_MIN_COLOR, dtype=np.float64)
    c1 = np.asarray(VALUE_MAX_COLOR, dtype=np.float64)
    rgb = c0 + t * (c1 - c0)
    return int(rgb[0]), int(rgb[1]), int(rgb[2])


class ApexNavMapListener:
    """Caches /grid_map/{occupied,free,unknown,value_map} from exploration_node."""

    TOPICS = {
        "occupied": "/grid_map/occupied",
        "free": "/grid_map/free",
        "unknown": "/grid_map/unknown",
        "occupied_inflate": "/grid_map/occupied_inflate",
        # ################################
        # Native ApexNav semantic value map (PointXYZI intensity).
        # ################################
        "value_map": "/grid_map/value_map",
    }

    def __init__(self):
        self.clouds: Dict[str, Optional[object]] = {k: None for k in self.TOPICS}
        self.counts: Dict[str, int] = {k: 0 for k in self.TOPICS}
        self.last_cosine: Optional[float] = None
        self.cosine_msgs: int = 0
        self._subs = []
        if rospy is None:
            return
        for key, topic in self.TOPICS.items():

            def _cb(msg, k=key):
                self.clouds[k] = msg
                self.counts[k] += 1

            self._subs.append(
                rospy.Subscriber(topic, PointCloud2, _cb, queue_size=1, buff_size=2**24)
            )

        def _cos_cb(msg):
            try:
                self.last_cosine = float(msg.data)
                self.cosine_msgs += 1
            except Exception:
                pass

        self._subs.append(
            rospy.Subscriber("/blip2/cosine_score", Float64, _cos_cb, queue_size=10)
        )

    def stats(self) -> Dict[str, int]:
        out = {}
        for k, msg in self.clouds.items():
            n = 0
            if msg is not None:
                n = int(getattr(msg, "width", 0) or 0) * int(getattr(msg, "height", 1) or 1)
            out[k] = n
            out[k + "_msgs"] = self.counts[k]
        out["cosine_msgs"] = int(self.cosine_msgs)
        if self.last_cosine is not None:
            out["last_cosine_x1000"] = int(round(float(self.last_cosine) * 1000.0))
        return out

    def has_map(self) -> bool:
        return any(self.counts[k] > 0 for k in ("occupied", "free", "unknown"))

    def has_value_map(self) -> bool:
        return self.counts.get("value_map", 0) > 0 and self.clouds.get("value_map") is not None

    def render_panel(
        self,
        size: Tuple[int, int] = (320, 240),
        robot_xy: Optional[Tuple[float, float]] = None,
        robot_yaw: float = 0.0,
        traj_xy: Optional[List[Tuple[float, float]]] = None,
        meters_span: float = 12.0,
        target_label: str = "",
        value_score: Optional[float] = None,
        show_legend: bool = True,
    ) -> np.ndarray:
        """Rasterize occupancy + native value heatmap (ROS planar x-y).

        ################################
        Paper occ base + ApexNav.rviz value heat (yellow→red) on free cells only.
        Each /grid_map cell is filled as a slightly enlarged footprint
        (demo-only; hides 1px white seam grids). Occupied never covered by heat.
        ################################
        """
        h, w = size[1], size[0]
        canvas = np.full((h, w, 3), PAPER_BG, dtype=np.uint8)
        if not self.has_map():
            canvas[:] = PAPER_BG
            self._put_text(canvas, "NO ApexNav /grid_map", (10, 30), (200, 40, 40))
            self._put_text(canvas, "occupied/free/unknown empty", (10, 55), PAPER_TEXT)
            return canvas

        cx, cy = 0.0, 0.0
        if robot_xy is not None:
            cx, cy = float(robot_xy[0]), float(robot_xy[1])
        center_xy = (cx, cy)
        scale = w / meters_span

        def to_pix(xy):
            px = int((xy[0] - cx) * scale + w / 2)
            py = int(-(xy[1] - cy) * scale + h / 2)
            return px, py

        # ################################
        # Layer order: unknown → free → value heat → occupied → traj → robot.
        # Fill cell footprints (resolution-matched); do NOT morphologically
        # grow/smooth away radial structure present in /grid_map.
        # ################################
        free_mask = np.zeros((h, w), dtype=bool)
        occ_mask = np.zeros((h, w), dtype=bool)

        # ################################
        # Unknown stays paper-white BACKGROUND — do not paint unknown cells
        # (avoids white-on-white "grid" speckles). Never morph-fill unknown.
        # ################################
        free = _cloud_xy(self.clouds["free"])
        occ = _cloud_xy(self.clouds["occupied"])
        res_m = estimate_resolution_m(free, occ, default=DEFAULT_MAP_RESOLUTION_M)

        fill_cells_rgb(
            canvas,
            free,
            PAPER_FREE,
            center_xy=center_xy,
            scale=scale,
            resolution_m=res_m,
            mask=free_mask,
        )
        fill_cells_rgb(
            canvas,
            occ,
            PAPER_OCCUPIED,
            center_xy=center_xy,
            scale=scale,
            resolution_m=res_m,
            mask=occ_mask,
            write_rgb=False,
        )

        val = _cloud_xyi(self.clouds.get("value_map"))
        if val.shape[0] > 0:
            fill_value_cells(
                canvas,
                val,
                center_xy=center_xy,
                scale=scale,
                resolution_m=res_m,
                free_mask=free_mask,
                occ_mask=occ_mask,
                intensity_to_rgb=value_intensity_to_rgb,
                alpha=float(VALUE_OVERLAY_ALPHA),
            )

        # Occupied on top — never covered by value heat.
        fill_cells_rgb(
            canvas,
            occ,
            PAPER_OCCUPIED,
            center_xy=center_xy,
            scale=scale,
            resolution_m=res_m,
        )
        if traj_xy:
            for i in range(1, len(traj_xy)):
                self._line(canvas, to_pix(traj_xy[i - 1]), to_pix(traj_xy[i]), PAPER_TRAJ)

        if robot_xy is not None:
            px, py = to_pix((cx, cy))
            self._draw_robot(canvas, px, py, robot_yaw, PAPER_ROBOT)

        if show_legend:
            cos_v = value_score if value_score is not None else self.last_cosine
            self._draw_legend(canvas, target_label=target_label, value_score=cos_v)

        st = self.stats()
        self._put_text(
            canvas,
            f"occ={st.get('occupied',0)} free={st.get('free',0)} val={st.get('value_map',0)}",
            (6, h - 12),
            PAPER_TEXT,
        )
        return canvas

    def _draw_legend(
        self,
        img: np.ndarray,
        *,
        target_label: str,
        value_score: Optional[float],
    ) -> None:
        """Compact Target / Value / Occupancy legend (top-left)."""
        try:
            import cv2
        except Exception:
            return
        h, w = img.shape[:2]
        box_w, box_h = min(168, w - 8), 54
        x0, y0 = 4, 4
        overlay = img.copy()
        cv2.rectangle(overlay, (x0, y0), (x0 + box_w, y0 + box_h), (255, 255, 255), -1)
        cv2.addWeighted(overlay, 0.82, img, 0.18, 0, img)
        cv2.rectangle(img, (x0, y0), (x0 + box_w, y0 + box_h), (180, 180, 180), 1)

        tgt = (target_label or "?").strip()[:18]
        self._put_text(img, f"Target: {tgt}", (x0 + 6, y0 + 14), PAPER_TEXT)
        if value_score is None:
            vs = "Value: n/a"
        else:
            vs = f"Value: {float(value_score):.3f}"
        self._put_text(img, vs, (x0 + 6, y0 + 28), PAPER_TEXT)

        # Mini colorbar + occ swatches
        bar_x, bar_y = x0 + 6, y0 + 36
        for i in range(48):
            t = i / 47.0
            inten = VALUE_MIN_INTENSITY + t * (VALUE_MAX_INTENSITY - VALUE_MIN_INTENSITY)
            c = value_intensity_to_rgb(inten)
            cv2.line(img, (bar_x + i, bar_y), (bar_x + i, bar_y + 8), c, 1)
        cv2.rectangle(
            img,
            (bar_x + 54, bar_y),
            (bar_x + 62, bar_y + 8),
            PAPER_OCCUPIED,
            -1,
        )
        cv2.rectangle(
            img,
            (bar_x + 66, bar_y),
            (bar_x + 74, bar_y + 8),
            PAPER_FREE,
            -1,
        )
        self._put_text(img, "occ", (bar_x + 78, bar_y + 8), PAPER_TEXT)

    @staticmethod
    def _put_text(img, text, org, color):
        try:
            import cv2

            cv2.putText(
                img, text, org, cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA
            )
        except Exception:
            pass

    @staticmethod
    def _line(img, p0, p1, color):
        try:
            import cv2

            cv2.line(img, p0, p1, color, 1, cv2.LINE_AA)
        except Exception:
            pass

    @staticmethod
    def _draw_robot(img, px, py, yaw, color):
        try:
            import cv2

            cv2.circle(img, (px, py), 5, color, -1)
            tip = (int(px + 12 * math.cos(yaw)), int(py - 12 * math.sin(yaw)))
            cv2.line(img, (px, py), tip, color, 2)
        except Exception:
            pass
