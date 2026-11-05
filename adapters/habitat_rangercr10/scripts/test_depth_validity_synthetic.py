#!/usr/bin/env python3
"""Synthetic depth validity checks (no Habitat / no ROS).

################################
Confirms invalid pixels become NaN and are never rewritten as max-range.
################################
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.coord_habitat_ros import depth_meters_to_normalized  # noqa: E402
from src.depth_validity import prepare_depth_for_apexnav  # noqa: E402


def main() -> int:
    h, w = 48, 64
    # 1) all-valid fixed depth
    d1 = np.full((h, w), 2.0, np.float32)
    p1, s1 = prepare_depth_for_apexnav(d1, use_geometric_self_hit=False, fallback_near_m=0.35)
    assert np.isfinite(p1).all() and abs(float(np.nanmean(p1)) - 2.0) < 1e-5
    n1 = depth_meters_to_normalized(p1)
    assert np.isfinite(n1).all() and abs(float(n1.mean()) - 0.4) < 1e-5

    # 2) invalid region (zeros + inf)
    d2 = np.full((h, w), 2.0, np.float32)
    d2[10:20, 10:20] = 0.0
    d2[30:35, 40:50] = np.inf
    p2, s2 = prepare_depth_for_apexnav(d2, use_geometric_self_hit=False, fallback_near_m=0.35)
    assert np.isnan(p2[10:20, 10:20]).all()
    assert np.isnan(p2[30:35, 40:50]).all()
    assert np.isfinite(p2[0, 0])
    n2 = depth_meters_to_normalized(p2)
    assert np.isnan(n2[10:20, 10:20]).all()
    # never max-range fill
    assert not np.any(np.nan_to_num(p2, nan=-1) >= 4.99)

    # 3) near obstacle band (0.2 m) with fallback — becomes NaN, not 5 m
    d3 = np.full((h, w), 2.0, np.float32)
    d3[5:15, 5:15] = 0.2
    p3, s3 = prepare_depth_for_apexnav(d3, use_geometric_self_hit=False, fallback_near_m=0.35)
    assert np.isnan(p3[5:15, 5:15]).all()
    assert float(s3["n_self_hit"]) == 100.0
    assert not np.any((np.nan_to_num(p3, nan=0) > 4.9))

    print("OK synthetic depth validity:", {"s1": s1, "s2_frac_nan": s2["frac_nan_published"], "s3": s3})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
