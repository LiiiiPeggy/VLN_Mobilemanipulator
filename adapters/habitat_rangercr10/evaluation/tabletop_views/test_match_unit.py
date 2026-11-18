#!/usr/bin/env python3
# ################################
# VLN adapt: unit tests for IoU hit rule (no VLM servers required)
# ################################
from __future__ import annotations

import numpy as np

from match_instance import match_frame, mask_iou


def test_hit_and_other_instance():
    gt = np.zeros((48, 64), dtype=bool)
    gt[10:30, 10:30] = True
    pred_hit = gt.copy()
    pred_other = np.zeros_like(gt)
    pred_other[10:30, 40:60] = True  # same class, wrong instance

    r = match_frame(
        gt_mask=gt,
        pred_masks=[pred_other, pred_hit],
        pred_scores=[0.9, 0.8],
        pred_labels_is_target=[True, True],
    )
    assert r["hit"] is True
    assert r["bucket"] == "hit"
    assert r["best_iou"] >= 0.5

    r2 = match_frame(
        gt_mask=gt,
        pred_masks=[pred_other],
        pred_scores=[0.99],
        pred_labels_is_target=[True],
    )
    assert r2["hit"] is False
    assert r2["bucket"] == "other_instance"
    assert r2["best_iou"] < 0.5


def test_invisible_and_miss():
    gt = np.zeros((32, 32), dtype=bool)  # empty → invisible
    r = match_frame(
        gt_mask=gt,
        pred_masks=[],
        pred_scores=[],
        pred_labels_is_target=[],
    )
    assert r["bucket"] == "target_invisible"

    gt2 = np.zeros((32, 32), dtype=bool)
    gt2[5:25, 5:25] = True
    r2 = match_frame(
        gt_mask=gt2,
        pred_masks=[],
        pred_scores=[],
        pred_labels_is_target=[],
    )
    assert r2["bucket"] == "miss_visible"


def test_iou_basic():
    a = np.zeros((10, 10), dtype=bool)
    b = np.zeros((10, 10), dtype=bool)
    a[:5, :5] = True
    b[2:7, 2:7] = True
    iou = mask_iou(a, b)
    assert 0.0 < iou < 1.0


if __name__ == "__main__":
    test_iou_basic()
    test_hit_and_other_instance()
    test_invisible_and_miss()
    print("test_match_unit: OK")
