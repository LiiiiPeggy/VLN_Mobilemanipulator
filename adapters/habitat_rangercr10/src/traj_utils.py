"""Trajectory helpers with no Habitat dependency (host MuJoCo can import)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image

from .constants import ARM_DEFAULT


def preset_trajectory(n: int = 40) -> List[dict]:
    frames = []
    for i in range(n):
        t = i / max(n - 1, 1)
        if t < 0.25:
            u = t / 0.25
            x, z, yaw = 0.5 + 1.5 * u, 0.5, 0.0
        elif t < 0.5:
            u = (t - 0.25) / 0.25
            x, z, yaw = 2.0, 0.5 + 1.5 * u, math.pi / 2
        elif t < 0.75:
            u = (t - 0.5) / 0.25
            x, z, yaw = 2.0 - 1.5 * u, 2.0, math.pi
        else:
            u = (t - 0.75) / 0.25
            x, z, yaw = 0.5, 2.0 - 1.5 * u, -math.pi / 2
        q0 = np.array(ARM_DEFAULT)
        q1 = np.array([0.2, 0.6, -1.8, 0.0, 1.0, 0.3])
        blend = 0.5 - 0.5 * math.cos(2 * math.pi * t)
        q = (1 - blend) * q0 + blend * q1
        frames.append({"x": x, "z": z, "yaw": yaw, "arm": q.tolist()})
    return frames


def save_depth_mm(path: Path, depth: np.ndarray) -> None:
    d = np.clip(depth * 1000.0, 0, 65535).astype(np.uint16)
    Image.fromarray(d).save(path)
