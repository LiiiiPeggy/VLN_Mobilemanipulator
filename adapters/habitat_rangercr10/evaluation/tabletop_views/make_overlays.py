#!/usr/bin/env python3
# ################################
# VLN adapt: RGB + GT mask + pred mask overlay for manual audit
# ################################
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def _load_rgb(path: Path) -> np.ndarray:
    import cv2

    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _load_mask(path: Path) -> np.ndarray:
    from match_instance import load_mask

    m = load_mask(path)
    if m is None:
        raise FileNotFoundError(path)
    return m.astype(bool)


def overlay(
    rgb: np.ndarray,
    gt: np.ndarray | None,
    pred: np.ndarray | None,
    *,
    title: str = "",
) -> np.ndarray:
    import cv2

    out = rgb.copy()
    if gt is not None and gt.shape[:2] == out.shape[:2]:
        out[gt] = (0.55 * out[gt] + 0.45 * np.array([0, 255, 0])).astype(np.uint8)
    if pred is not None and pred.shape[:2] == out.shape[:2]:
        out[pred] = (0.55 * out[pred] + 0.45 * np.array([255, 0, 0])).astype(np.uint8)
    if gt is not None and pred is not None and gt.shape == pred.shape:
        both = np.logical_and(gt, pred)
        out[both] = (0.4 * out[both] + 0.6 * np.array([255, 255, 0])).astype(np.uint8)
    if title:
        cv2.putText(
            out,
            title[:80],
            (8, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rgb", type=Path, required=True)
    ap.add_argument("--gt", type=Path, default=None)
    ap.add_argument("--pred", type=Path, default=None)
    ap.add_argument("--title", default="")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    rgb = _load_rgb(args.rgb)
    gt = _load_mask(args.gt) if args.gt else None
    pred = _load_mask(args.pred) if args.pred else None
    img = overlay(rgb, gt, pred, title=args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    Image.fromarray(img).save(args.out)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
