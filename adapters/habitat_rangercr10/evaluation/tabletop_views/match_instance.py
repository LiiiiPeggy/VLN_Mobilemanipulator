#!/usr/bin/env python3
# ################################
# VLN adapt: instance-level IoU match (detector never sees GT until after inference)
# ################################
"""Primary hit rule (locked before reading full batch):

  pred_class == target_canonical AND max IoU(pred_mask, gt_mask) ≥ 0.5

Accounting buckets (mutually exclusive per frame when GT available):
  - hit: IoU≥0.5 with target instance
  - other_instance: same-class detection exists but best IoU with target < 0.5
  - miss_visible: GT visible (gt_pixels≥min) but no same-class detection
  - target_invisible: GT pixels < min (or visibility flag false)
  - log_missing: RGB / GT / detection log absent
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

IOU_HIT_THR = 0.5
MIN_GT_PIXELS_VISIBLE = 32


def _as_bool_mask(arr: np.ndarray) -> np.ndarray:
    a = np.asarray(arr)
    if a.ndim == 3:
        a = a[..., 0] if a.shape[-1] in (1, 3, 4) else a.max(axis=-1)
    return a.astype(bool)


def load_mask(
    path: Path,
    *,
    resize_hw: Optional[Tuple[int, int]] = None,
) -> Optional[np.ndarray]:
    """Load GT/pred mask. resize_hw=(H,W) nearest-neighbor when aligning to prod RGB."""
    if path is None or not Path(path).is_file():
        return None
    p = Path(path)
    if p.suffix.lower() == ".npy":
        m = _as_bool_mask(np.load(p))
    else:
        # png / jpg via cv2
        try:
            import cv2

            img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            if img is None:
                return None
            if img.ndim == 3 and img.shape[2] == 4:
                m = img[..., 3] > 0
            else:
                m = _as_bool_mask(img > 0)
        except Exception:
            return None
    if resize_hw is not None and m.shape[:2] != tuple(resize_hw):
        import cv2

        m = cv2.resize(
            m.astype(np.uint8),
            (int(resize_hw[1]), int(resize_hw[0])),
            interpolation=cv2.INTER_NEAREST,
        ).astype(bool)
    return m


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    a = _as_bool_mask(a)
    b = _as_bool_mask(b)
    if a.shape != b.shape:
        # refuse silent resize — caller must align; return 0 and note
        return 0.0
    inter = np.logical_and(a, b).sum(dtype=np.int64)
    union = np.logical_or(a, b).sum(dtype=np.int64)
    if union == 0:
        return 0.0
    return float(inter) / float(union)


def match_frame(
    *,
    gt_mask: Optional[np.ndarray],
    pred_masks: Sequence[np.ndarray],
    pred_scores: Sequence[float],
    pred_labels_is_target: Sequence[bool],
    gt_visible: Optional[bool] = None,
    iou_thr: float = IOU_HIT_THR,
    min_gt_pixels: int = MIN_GT_PIXELS_VISIBLE,
    log_missing: bool = False,
) -> Dict[str, Any]:
    """Score one frame. pred_* are already filtered to target-class candidates
    when possible; pred_labels_is_target marks which are target-class.
    """
    if log_missing:
        return {
            "bucket": "log_missing",
            "hit": False,
            "best_iou": None,
            "best_score": None,
            "gt_pixels": None,
            "n_pred_target": None,
            "shape_mismatch": False,
        }

    if gt_mask is None:
        return {
            "bucket": "log_missing",
            "hit": False,
            "best_iou": None,
            "best_score": None,
            "gt_pixels": None,
            "n_pred_target": None,
            "shape_mismatch": False,
        }

    gt = _as_bool_mask(gt_mask)
    gt_pixels = int(gt.sum())
    visible = bool(gt_visible) if gt_visible is not None else (gt_pixels >= min_gt_pixels)

    # target-class predictions only for hit / other_instance
    target_idxs = [i for i, t in enumerate(pred_labels_is_target) if t]
    n_pred_target = len(target_idxs)

    best_iou = None
    best_score = None
    best_i = None
    shape_mismatch = False
    for i in target_idxs:
        pm = pred_masks[i]
        if pm is None:
            continue
        pm = _as_bool_mask(pm)
        if pm.shape != gt.shape:
            shape_mismatch = True
            continue
        iou = mask_iou(pm, gt)
        sc = float(pred_scores[i]) if pred_scores[i] is not None else None
        if best_iou is None or iou > best_iou:
            best_iou = iou
            best_score = sc
            best_i = i

    if not visible:
        return {
            "bucket": "target_invisible",
            "hit": False,
            "best_iou": best_iou,
            "best_score": best_score,
            "best_pred_idx": best_i,
            "gt_pixels": gt_pixels,
            "n_pred_target": n_pred_target,
            "shape_mismatch": shape_mismatch,
        }

    if n_pred_target == 0 or best_iou is None:
        return {
            "bucket": "miss_visible",
            "hit": False,
            "best_iou": best_iou,
            "best_score": best_score,
            "best_pred_idx": best_i,
            "gt_pixels": gt_pixels,
            "n_pred_target": n_pred_target,
            "shape_mismatch": shape_mismatch,
        }

    if best_iou >= iou_thr:
        return {
            "bucket": "hit",
            "hit": True,
            "best_iou": best_iou,
            "best_score": best_score,
            "best_pred_idx": best_i,
            "gt_pixels": gt_pixels,
            "n_pred_target": n_pred_target,
            "shape_mismatch": shape_mismatch,
        }

    return {
        "bucket": "other_instance",
        "hit": False,
        "best_iou": best_iou,
        "best_score": best_score,
        "best_pred_idx": best_i,
        "gt_pixels": gt_pixels,
        "n_pred_target": n_pred_target,
        "shape_mismatch": shape_mismatch,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", type=Path, required=True)
    ap.add_argument("--pred_dir", type=Path, help="dir of pred_mask_*.png/.npy")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    gt = load_mask(args.gt)
    preds = []
    if args.pred_dir and args.pred_dir.is_dir():
        for p in sorted(args.pred_dir.glob("pred_mask_*")):
            m = load_mask(p)
            if m is not None:
                preds.append(m)
    row = match_frame(
        gt_mask=gt,
        pred_masks=preds,
        pred_scores=[1.0] * len(preds),
        pred_labels_is_target=[True] * len(preds),
    )
    text = json.dumps(row, indent=2)
    if args.out:
        args.out.write_text(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
