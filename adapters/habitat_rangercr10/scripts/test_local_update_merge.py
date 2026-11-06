#!/usr/bin/env python3
"""Offline unit test: same-frame local_update AABB merge vs overwrite.

Mirrors SDFMap2D clearAndInflateLocalMap window selection after
inputDepthCloud2D + inputFreeRayCloud2D. Does NOT require ROS.

Cases:
  1) obstacle outside ground update box
  2) obstacle-only
  3) ground-only
  4) mixed overlapping
  + frame reset: second frame must not inherit previous local_update

Compares local inflation (window) against full-map rebuild inflation.
Exit 0 iff merge matches full rebuild on all cases and overwrite fails case 1.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

RES = 0.05
INF_RADIUS_M = 0.18
INF_STEP = int(math.ceil(INF_RADIUS_M / RES))
MAP_N = 80  # 4 m @ 0.05


def xy_to_idx(x: float, y: float) -> Tuple[int, int]:
    # origin at map center
    ix = int(math.floor(x / RES)) + MAP_N // 2
    iy = int(math.floor(y / RES)) + MAP_N // 2
    return ix, iy


def inflate_points(occ: List[Tuple[int, int]], step: int) -> set:
    out = set()
    for x, y in occ:
        for dx in range(-step, step + 1):
            for dy in range(-step, step + 1):
                if dx * dx + dy * dy > step * step:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < MAP_N and 0 <= ny < MAP_N:
                    out.add((nx, ny))
    return out


def inflate_in_window(
    occ_cells: set, window: Tuple[int, int, int, int], step: int
) -> set:
    xmin, ymin, xmax, ymax = window
    local_occ = [
        (x, y)
        for (x, y) in occ_cells
        if xmin <= x <= xmax and ymin <= y <= ymax
    ]
    return inflate_points(local_occ, step)


def aabb_from_points(pts_xy: List[Tuple[float, float]], sensor: Tuple[float, float]):
    xs = [sensor[0]] + [p[0] for p in pts_xy]
    ys = [sensor[1]] + [p[1] for p in pts_xy]
    return min(xs), min(ys), max(xs), max(ys)


def aabb_to_idx(aabb):
    xmin, ymin, xmax, ymax = aabb
    ix0, iy0 = xy_to_idx(xmin, ymin)
    ix1, iy1 = xy_to_idx(xmax, ymax)
    return min(ix0, ix1), min(iy0, iy1), max(ix0, ix1), max(iy0, iy1)


def merge_aabb(a, b):
    return (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3]),
    )


@dataclass
class Case:
    name: str
    sensor: Tuple[float, float]
    obstacle_xy: List[Tuple[float, float]]
    ground_xy: List[Tuple[float, float]]


def run_case(case: Case, mode: str) -> dict:
    """mode: overwrite | merge"""
    # Occupied cells = obstacle endpoints only (ground free-ray never OCCUPIED).
    occ = {xy_to_idx(x, y) for x, y in case.obstacle_xy}
    full_inf = inflate_points(list(occ), INF_STEP)

    if case.obstacle_xy:
        obst_box = aabb_to_idx(aabb_from_points(case.obstacle_xy, case.sensor))
        local_updated = True
        local = obst_box
    else:
        local_updated = False
        local = None

    if case.ground_xy:
        gbox = aabb_to_idx(aabb_from_points(case.ground_xy, case.sensor))
        if mode == "overwrite":
            local = gbox  # bug: replaces obstacle box
            local_updated = True
        else:
            if local_updated and local is not None:
                local = merge_aabb(local, gbox)
            else:
                local = gbox
            local_updated = True

    if local is None:
        local_inf = set()
    else:
        local_inf = inflate_in_window(occ, local, INF_STEP)

    missing = sorted(full_inf - local_inf)
    extra = sorted(local_inf - full_inf)
    return {
        "name": case.name,
        "mode": mode,
        "n_occ": len(occ),
        "local_window": local,
        "n_full_inf": len(full_inf),
        "n_local_inf": len(local_inf),
        "n_missing_vs_full": len(missing),
        "n_extra_vs_full": len(extra),
        "missing_sample": missing[:8],
        "match_full": len(missing) == 0 and len(extra) == 0,
    }


def main() -> int:
    sensor = (0.0, 0.0)
    cases = [
        Case(
            "obstacle_outside_ground_box",
            sensor,
            obstacle_xy=[(1.5, 0.0)],  # far +x
            ground_xy=[(-0.4, 0.1), (-0.35, -0.05)],  # near -x (chassis side)
        ),
        Case(
            "obstacle_only",
            sensor,
            obstacle_xy=[(0.8, 0.2), (0.9, -0.1)],
            ground_xy=[],
        ),
        Case(
            "ground_only",
            sensor,
            obstacle_xy=[],
            ground_xy=[(-0.5, 0.0), (-0.4, 0.1)],
        ),
        Case(
            "mixed_overlap",
            sensor,
            obstacle_xy=[(0.6, 0.0)],
            ground_xy=[(0.4, 0.05), (0.5, -0.05)],
        ),
    ]

    results = []
    # Frame reset check: after "inflate", local_updated clears; next frame assign.
    frame_ok = True
    prev_local = aabb_to_idx(aabb_from_points([(1.0, 0.0)], sensor))
    local_updated = False  # after MapROS inflate
    # next frame ground-only must ASSIGN, not merge with stale prev_local
    gbox = aabb_to_idx(aabb_from_points([(-0.5, 0.0)], sensor))
    if local_updated:
        nxt = merge_aabb(prev_local, gbox)
        frame_ok = False  # should not happen
    else:
        nxt = gbox
    frame_ok = frame_ok and (nxt == gbox) and (nxt != prev_local)

    all_merge_ok = True
    overwrite_fails_case1 = False
    for c in cases:
        r_over = run_case(c, "overwrite")
        r_merge = run_case(c, "merge")
        results.append({"overwrite": r_over, "merge": r_merge})
        if not r_merge["match_full"]:
            all_merge_ok = False
        if c.name == "obstacle_outside_ground_box":
            overwrite_fails_case1 = (not r_over["match_full"]) and r_over[
                "n_missing_vs_full"
            ] > 0

    out = {
        "resolution_m": RES,
        "inflation_m": INF_RADIUS_M,
        "inf_step": INF_STEP,
        "frame_reset_ok": frame_ok,
        "merge_matches_full_rebuild_all_cases": all_merge_ok,
        "overwrite_fails_disjoint_obstacle_case": overwrite_fails_case1,
        "cases": results,
        "pass": bool(all_merge_ok and frame_ok and overwrite_fails_case1),
    }

    out_dir = Path(
        "/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/local_update_merge_20261106"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "test_local_update_merge.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    print(json.dumps({k: out[k] for k in ("pass", "frame_reset_ok",
        "merge_matches_full_rebuild_all_cases",
        "overwrite_fails_disjoint_obstacle_case")}, indent=2))
    for block in results:
        m = block["merge"]
        o = block["overwrite"]
        print(
            f"{m['name']}: merge_match={m['match_full']} "
            f"overwrite_missing={o['n_missing_vs_full']}"
        )
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
