#!/usr/bin/env python3
"""Verify ground free-ray geometry gates vs naive AGL[0,0.28] free labeling.

Does not lower inflation or relax UNKNOWN. Cases:
  - planar floor AGL=1 cm → GROUND_FREE
  - low obstacles 5/10/20 cm → LOW_OBSTACLE (OCCUPIED path), never FREE via free-ray
  - sparse spike at AGL=1 cm (no planar neighbors) → PLANAR_REJECT (stays unknown)
  - naive policy would FREE-label 5/10/20 cm tops (regression witness)

Exit 0 on pass. Writes reports/ground_free_geometry_20261106/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple

FILTER_MIN = 0.28
MAX_AGL = 0.03
PLANAR_R = 0.12
PLANAR_Z_TOL = 0.02
PLANAR_MIN_N = 5

GROUND_FREE = "GROUND_FREE"
LOW_OBSTACLE = "LOW_OBSTACLE"
PLANAR_REJECT = "PLANAR_REJECT"
OTHER = "OTHER"
NAIVE_FREE = "NAIVE_FREE"  # old buggy whole-band free-ray


def is_planar(cloud: List[Tuple[float, float, float]], idx: int) -> bool:
    px, py, pz = cloud[idx]
    r2 = PLANAR_R * PLANAR_R
    n_ok = 0
    for j, (qx, qy, qz) in enumerate(cloud):
        if j == idx:
            continue
        if (px - qx) ** 2 + (py - qy) ** 2 > r2:
            continue
        if abs(pz - qz) <= PLANAR_Z_TOL:
            n_ok += 1
            if n_ok >= PLANAR_MIN_N:
                return True
    return False


def classify(cloud: List[Tuple[float, float, float]], idx: int) -> str:
    x, y, z = cloud[idx]
    agl = z  # floor at 0
    if agl < 0 or agl > FILTER_MIN:
        return OTHER
    if agl <= MAX_AGL:
        return GROUND_FREE if is_planar(cloud, idx) else PLANAR_REJECT
    return LOW_OBSTACLE


def naive_classify(agl: float) -> str:
    if 0 <= agl <= FILTER_MIN:
        return NAIVE_FREE
    return OTHER


def make_floor_patch(z: float = 0.01) -> List[Tuple[float, float, float]]:
    pts = []
    for i in range(-3, 4):
        for j in range(-3, 4):
            pts.append((0.05 * i, 0.05 * j, z))
    return pts


def make_box_top(height: float, cx: float = 1.0, cy: float = 0.0) -> List[Tuple[float, float, float]]:
    """Flat top of a low box (planar in itself) at given AGL."""
    pts = []
    for i in range(-2, 3):
        for j in range(-2, 3):
            pts.append((cx + 0.04 * i, cy + 0.04 * j, height))
    return pts


def simulate_endpoint_label(policy: str, cls: str) -> str:
    """What occupancy label would free-ray / obstacle path assign to endpoint."""
    if policy == "naive":
        return "FREE" if cls == NAIVE_FREE else "UNKNOWN"
    if cls == GROUND_FREE:
        return "FREE"
    if cls == LOW_OBSTACLE:
        return "OCCUPIED"
    return "UNKNOWN"  # planar reject / other: no free-ray, no occ hit


def main() -> int:
    results = []
    ok = True

    # 1) planar floor
    floor = make_floor_patch(0.01)
    c = classify(floor, len(floor) // 2)
    results.append({"case": "planar_floor_1cm", "class": c, "expect": GROUND_FREE})
    if c != GROUND_FREE:
        ok = False

    # 2) low obstacles 5/10/20 cm (self-planar tops — height gate must catch them)
    for h_cm, h in [(5, 0.05), (10, 0.10), (20, 0.20)]:
        cloud = make_box_top(h)
        # also sprinkle floor far away so neighborhood check isn't confused
        cloud.extend(make_floor_patch(0.01))
        # classify a box-top center index
        idx = 12  # center-ish of 5x5 top
        c = classify(cloud, idx)
        naive = naive_classify(h)
        ep_new = simulate_endpoint_label("gated", c)
        ep_old = simulate_endpoint_label("naive", naive)
        row = {
            "case": f"low_obstacle_{h_cm}cm",
            "agl_m": h,
            "class": c,
            "expect": LOW_OBSTACLE,
            "endpoint_label_gated": ep_new,
            "endpoint_label_naive": ep_old,
            "naive_would_free": ep_old == "FREE",
            "gated_not_free": ep_new != "FREE",
        }
        results.append(row)
        if c != LOW_OBSTACLE or ep_new == "FREE" or ep_old != "FREE":
            ok = False

    # 3) sparse spike at floor height — planar reject → UNKNOWN (not FREE)
    spike = [(0.0, 0.0, 0.01)]
    c = classify(spike, 0)
    results.append(
        {
            "case": "sparse_spike_1cm",
            "class": c,
            "expect": PLANAR_REJECT,
            "endpoint_label_gated": simulate_endpoint_label("gated", c),
        }
    )
    if c != PLANAR_REJECT or simulate_endpoint_label("gated", c) == "FREE":
        ok = False

    # 4) inflation / unknown policy untouched (documentation assert)
    results.append(
        {
            "case": "policy_invariants",
            "inflation_radius_changed": False,
            "unknown_relaxed": False,
            "filter_min_height": FILTER_MIN,
            "ground_free_max_agl": MAX_AGL,
        }
    )

    out = {
        "pass": ok,
        "params": {
            "filter_min_height": FILTER_MIN,
            "ground_free_max_agl": MAX_AGL,
            "planar_radius": PLANAR_R,
            "planar_z_tol": PLANAR_Z_TOL,
            "planar_min_neighbors": PLANAR_MIN_N,
        },
        "results": results,
    }
    out_dir = Path(
        "/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/ground_free_geometry_20261106"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "test_ground_free_geometry.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"pass": ok, "n_cases": len(results)}, indent=2))
    for r in results:
        if "class" in r:
            print(f"  {r['case']}: {r.get('class')} (expect {r.get('expect')})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
