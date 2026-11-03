"""Subscribe to ApexNav online grid_map PointCloud2 topics for demo panels."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import rospy
    from sensor_msgs.msg import PointCloud2
    from sensor_msgs import point_cloud2 as pc2
except Exception:  # pragma: no cover
    rospy = None
    PointCloud2 = object  # type: ignore
    pc2 = None


def _cloud_xy(msg) -> np.ndarray:
    if pc2 is None or msg is None or getattr(msg, "width", 0) == 0:
        return np.zeros((0, 2), dtype=np.float64)
    pts = list(pc2.read_points(msg, field_names=("x", "y", "z"), skip_nans=True))
    if not pts:
        return np.zeros((0, 2), dtype=np.float64)
    arr = np.asarray(pts, dtype=np.float64)
    # ApexNav ROS map is Z-up: use x,y as planar
    return arr[:, :2]


class ApexNavMapListener:
    """Caches /grid_map/{occupied,free,unknown} from real exploration_node."""

    TOPICS = {
        "occupied": "/grid_map/occupied",
        "free": "/grid_map/free",
        "unknown": "/grid_map/unknown",
        "occupied_inflate": "/grid_map/occupied_inflate",
    }

    def __init__(self):
        self.clouds: Dict[str, Optional[object]] = {k: None for k in self.TOPICS}
        self.counts: Dict[str, int] = {k: 0 for k in self.TOPICS}
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

    def stats(self) -> Dict[str, int]:
        out = {}
        for k, msg in self.clouds.items():
            n = 0
            if msg is not None:
                n = int(getattr(msg, "width", 0) or 0) * int(getattr(msg, "height", 1) or 1)
            out[k] = n
            out[k + "_msgs"] = self.counts[k]
        return out

    def has_map(self) -> bool:
        return any(self.counts[k] > 0 for k in ("occupied", "free", "unknown"))

    def render_panel(
        self,
        size: Tuple[int, int] = (320, 240),
        robot_xy: Optional[Tuple[float, float]] = None,
        robot_yaw: float = 0.0,
        traj_xy: Optional[List[Tuple[float, float]]] = None,
        meters_span: float = 12.0,
    ) -> np.ndarray:
        """Rasterize cached clouds to RGB panel (ROS planar x-y)."""
        h, w = size[1], size[0]
        canvas = np.full((h, w, 3), 30, dtype=np.uint8)
        if not self.has_map():
            canvas[:] = (40, 40, 40)
            self._put_text(canvas, "NO ApexNav /grid_map", (10, 30), (0, 80, 255))
            self._put_text(canvas, "occupied/free/unknown empty", (10, 55), (180, 180, 180))
            return canvas

        cx, cy = 0.0, 0.0
        if robot_xy is not None:
            cx, cy = float(robot_xy[0]), float(robot_xy[1])
        scale = w / meters_span

        def to_pix(xy):
            px = int((xy[0] - cx) * scale + w / 2)
            py = int(-(xy[1] - cy) * scale + h / 2)
            return px, py

        layers = [
            ("unknown", (70, 70, 70), _cloud_xy(self.clouds["unknown"])),
            ("free", (210, 190, 150), _cloud_xy(self.clouds["free"])),
            ("occupied", (40, 40, 220), _cloud_xy(self.clouds["occupied"])),
        ]
        for _name, color, pts in layers:
            if pts.shape[0] == 0:
                continue
            if pts.shape[0] > 20000:
                idx = np.linspace(0, pts.shape[0] - 1, 20000).astype(int)
                pts = pts[idx]
            for p in pts:
                px, py = to_pix(p)
                if 0 <= px < w and 0 <= py < h:
                    canvas[py, px] = color

        if traj_xy:
            for i in range(1, len(traj_xy)):
                self._line(canvas, to_pix(traj_xy[i - 1]), to_pix(traj_xy[i]), (255, 180, 40))

        if robot_xy is not None:
            px, py = to_pix((cx, cy))
            self._draw_robot(canvas, px, py, robot_yaw, (50, 220, 255))

        st = self.stats()
        self._put_text(
            canvas,
            f"occ={st.get('occupied',0)} free={st.get('free',0)}",
            (6, h - 12),
            (220, 220, 220),
        )
        return canvas

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
