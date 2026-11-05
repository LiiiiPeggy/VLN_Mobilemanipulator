"""Compose 16:9 paper-style Demo frame: main third + EE semantic + occupancy map."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _fit(img: np.ndarray, wh: Tuple[int, int]) -> Image.Image:
    im = Image.fromarray(img[..., :3].astype(np.uint8))
    return im.resize(wh, Image.BILINEAR)


def compose_frame(
    third_rgb: np.ndarray,
    semantic_rgb: np.ndarray,
    map_rgb: np.ndarray,
    *,
    goal: str,
    step: int,
    action: str,
    phase: str,
    control_mode: str,
    status: str,
    out_size: Tuple[int, int] = (1280, 720),
    extra_banner: str = "",
) -> np.ndarray:
    """
    Layout (16:9):
      - Main: third-person (full frame)
      - Bottom-left inset: EE semantic / detections
      - Bottom-right inset: ApexNav online occupancy map
    """
    W, H = out_size
    canvas = _fit(third_rgb, (W, H)).convert("RGB")
    draw = ImageDraw.Draw(canvas, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        font_s = font

    # top banner
    draw.rectangle([0, 0, W, 52], fill=(0, 0, 0, 140))
    banner = (
        f"Object Goal: {goal}   |   Step: {step}   |   Action: {action}   |   "
        f"Phase: {phase}   |   {control_mode}   |   {status}"
    )
    if extra_banner:
        banner = banner + "   |   " + extra_banner
    draw.text((16, 14), banner, fill=(255, 255, 255, 255), font=font_s)

    inset_w, inset_h = 320, 240
    margin = 16
    # left semantic
    sem = _fit(semantic_rgb, (inset_w, inset_h))
    lx, ly = margin, H - inset_h - margin
    canvas.paste(sem, (lx, ly))
    draw.rectangle([lx, ly - 22, lx + inset_w, ly], fill=(0, 0, 0, 160))
    draw.text((lx + 8, ly - 20), "EE D455 + ApexNav detections", fill=(255, 255, 255), font=font_s)

    # right map
    mp = _fit(map_rgb, (inset_w, inset_h))
    rx, ry = W - inset_w - margin, H - inset_h - margin
    canvas.paste(mp, (rx, ry))
    draw.rectangle([rx, ry - 22, rx + inset_w, ry], fill=(0, 0, 0, 160))
    draw.text(
        (rx + 8, ry - 20),
        "ApexNav Occ + Value Map",
        fill=(255, 255, 255),
        font=font_s,
    )

    # borders
    draw.rectangle([lx, ly, lx + inset_w, ly + inset_h], outline=(255, 255, 255, 200), width=2)
    draw.rectangle([rx, ry, rx + inset_w, ry + inset_h], outline=(255, 255, 255, 200), width=2)

    return np.asarray(canvas.convert("RGB"))
