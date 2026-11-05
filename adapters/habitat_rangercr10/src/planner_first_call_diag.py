"""Dump / analyze ApexNav /grid_map at first callActionPlanner (adapter-side).

################################
Saves free/occupied/unknown/inflate clouds, robot cell occupancy, a coarse
frontier proxy, and BFS/A* reachability from the base. Does not change ApexNav
C++ planner logic — evidence only for NO_PASSABLE root-cause reports.
################################
"""

from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .map_listener import _cloud_xy


def _voxelize(pts: np.ndarray, res: float = 0.05) -> set:
    if pts.size == 0:
        return set()
    ij = np.floor(pts / res).astype(np.int64)
    return set(map(tuple, ij.tolist()))


def _cell_state(
    ij: Tuple[int, int],
    free: set,
    occ: set,
    unk: set,
    inf: set,
) -> str:
    if ij in inf or ij in occ:
        return "occupied_or_inflate"
    if ij in free:
        return "free"
    if ij in unk:
        return "unknown"
    return "absent"


def _neighbors(ij: Tuple[int, int]) -> List[Tuple[int, int]]:
    i, j = ij
    out = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di == 0 and dj == 0:
                continue
            out.append((i + di, j + dj))
    return out


def _frontier_seeds(free: set, unk: set) -> List[Tuple[int, int]]:
    """Unknown cell with ≥1 free 8-neighbor (ApexNav-like seed)."""
    seeds = []
    for ij in unk:
        if any(n in free for n in _neighbors(ij)):
            seeds.append(ij)
    return seeds


def _cluster_centroids(seeds: List[Tuple[int, int]], res: float, min_size: int = 2) -> List[Dict[str, Any]]:
    """Greedy connected components on frontier seeds (approx cluster)."""
    remain = set(seeds)
    clusters = []
    while remain:
        start = remain.pop()
        q = deque([start])
        cells = [start]
        while q:
            cur = q.popleft()
            for n in _neighbors(cur):
                if n in remain:
                    remain.remove(n)
                    q.append(n)
                    cells.append(n)
        if len(cells) < min_size:
            continue
        # ij = (floor(x/res), floor(y/res))
        mx = float(np.mean([c[0] for c in cells])) * res + 0.5 * res
        my = float(np.mean([c[1] for c in cells])) * res + 0.5 * res
        clusters.append({"n_cells": len(cells), "center_xy": [mx, my]})
    clusters.sort(key=lambda c: -c["n_cells"])
    return clusters


def _astar_reachable(
    start_xy: Tuple[float, float],
    goal_xy: Tuple[float, float],
    free: set,
    blocked: set,
    res: float = 0.05,
    max_expand: int = 80000,
) -> Dict[str, Any]:
    """Grid A* on free cells; blocked = occ∪inflate. Unknown not traversable (NORMAL)."""
    def to_ij(xy):
        return (int(math.floor(xy[0] / res)), int(math.floor(xy[1] / res)))

    s = to_ij(start_xy)
    g = to_ij(goal_xy)
    if s in blocked:
        return {"ok": False, "reason": "start_blocked", "start_ij": list(s), "goal_ij": list(g)}
    if g in blocked:
        return {"ok": False, "reason": "goal_blocked", "start_ij": list(s), "goal_ij": list(g)}

    def passable(ij):
        if ij in blocked:
            return False
        # Allow start bubble / free cells only (unknown unsafe in NORMAL)
        return ij in free or ij == s

    if not passable(s):
        # try nearby free within 0.25 m (matches Astar2D near-start skip)
        found = None
        r = int(math.ceil(0.25 / res))
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                cand = (s[0] + di, s[1] + dj)
                if cand in free and cand not in blocked:
                    found = cand
                    break
            if found:
                break
        if found is None:
            return {
                "ok": False,
                "reason": "start_not_free_no_nearby_free",
                "start_ij": list(s),
                "goal_ij": list(g),
                "start_state_hint": "not_in_free",
            }
        s = found

    open_q = [(0.0 + math.hypot(s[0] - g[0], s[1] - g[1]), 0.0, s)]
    came = {s: None}
    gscore = {s: 0.0}
    expanded = 0
    import heapq

    while open_q and expanded < max_expand:
        _, gs, cur = heapq.heappop(open_q)
        expanded += 1
        if abs(cur[0] - g[0]) <= 1 and abs(cur[1] - g[1]) <= 1:
            return {
                "ok": True,
                "reason": "reach_end",
                "start_ij": list(s),
                "goal_ij": list(g),
                "expanded": expanded,
                "path_cells": int(gs / res) if res > 0 else expanded,
            }
        for n in _neighbors(cur):
            if not passable(n):
                continue
            ng = gscore[cur] + (res * 1.414 if (n[0] != cur[0] and n[1] != cur[1]) else res)
            if n not in gscore or ng < gscore[n]:
                gscore[n] = ng
                came[n] = cur
                heapq.heappush(
                    open_q, (ng + res * math.hypot(n[0] - g[0], n[1] - g[1]), ng, n)
                )
    return {
        "ok": False,
        "reason": "no_path_or_budget",
        "start_ij": list(s),
        "goal_ij": list(g),
        "expanded": expanded,
    }


def analyze_map_listener(
    map_listener,
    base_ros_xy: Tuple[float, float],
    base_yaw_ros: float,
    out_dir: Path,
    res: float = 0.05,
    max_frontier_astar: int = 30,
) -> Dict[str, Any]:
    """Build diagnostic JSON + visualization from cached ApexNav clouds."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    layers = {}
    for key in ("free", "occupied", "unknown", "occupied_inflate"):
        pts = _cloud_xy(map_listener.clouds.get(key))
        layers[key] = pts
        np.save(out_dir / f"{key}_xy.npy", pts)

    free = _voxelize(layers["free"], res)
    occ = _voxelize(layers["occupied"], res)
    unk = _voxelize(layers["unknown"], res)
    inf = _voxelize(layers["occupied_inflate"], res)
    blocked = occ | inf

    sij = (
        int(math.floor(base_ros_xy[0] / res)),
        int(math.floor(base_ros_xy[1] / res)),
    )
    start_state = _cell_state(sij, free, occ, unk, inf)

    # free component size from start (or nearest free)
    seed = sij if sij in free else None
    if seed is None:
        r = int(math.ceil(0.5 / res))
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                cand = (sij[0] + di, sij[1] + dj)
                if cand in free and cand not in blocked:
                    seed = cand
                    break
            if seed:
                break
    free_comp = 0
    if seed is not None:
        q = deque([seed])
        seen = {seed}
        while q:
            cur = q.popleft()
            free_comp += 1
            for n in _neighbors(cur):
                if n in free and n not in blocked and n not in seen:
                    seen.add(n)
                    q.append(n)

    seeds = _frontier_seeds(free, unk)
    clusters = _cluster_centroids(seeds, res, min_size=2)
    astar_trials = []
    n_ok = 0
    for c in clusters[:max_frontier_astar]:
        goal = (float(c["center_xy"][0]), float(c["center_xy"][1]))
        trial = _astar_reachable(base_ros_xy, goal, free, blocked, res=res)
        trial["frontier_center_xy"] = list(goal)
        trial["frontier_n_cells"] = c["n_cells"]
        astar_trials.append(trial)
        if trial.get("ok"):
            n_ok += 1

    # Render diagnostic panel
    try:
        import cv2

        panel = map_listener.render_panel(
            size=(640, 480),
            robot_xy=base_ros_xy,
            robot_yaw=base_yaw_ros,
            meters_span=14.0,
        )
        # mark frontier centers
        h, w = panel.shape[:2]
        cx, cy = base_ros_xy
        scale = w / 14.0

        def to_pix(xy):
            px = int((xy[0] - cx) * scale + w / 2)
            py = int(-(xy[1] - cy) * scale + h / 2)
            return px, py

        for t in astar_trials[:20]:
            p = to_pix(t["frontier_center_xy"])
            color = (40, 180, 40) if t.get("ok") else (40, 40, 200)
            cv2.circle(panel, p, 4, color, -1)
        cv2.putText(
            panel,
            f"start={start_state} free_comp={free_comp} ftr={len(clusters)} astar_ok={n_ok}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
        cv2.imwrite(str(out_dir / "first_plan_map_diag.png"), panel[:, :, ::-1])
    except Exception as e:
        (out_dir / "render_error.txt").write_text(str(e))

    report = {
        "resolution_m": res,
        "base_ros_xy": [float(base_ros_xy[0]), float(base_ros_xy[1])],
        "base_yaw_ros": float(base_yaw_ros),
        "base_grid_ij": list(sij),
        "base_cell_state": start_state,
        "counts": {
            "free_pts": int(layers["free"].shape[0]),
            "occupied_pts": int(layers["occupied"].shape[0]),
            "unknown_pts": int(layers["unknown"].shape[0]),
            "inflate_pts": int(layers["occupied_inflate"].shape[0]),
            "free_voxels": len(free),
            "occ_voxels": len(occ),
            "unk_voxels": len(unk),
            "inflate_voxels": len(inf),
        },
        "free_component_from_start": free_comp,
        "frontier_seed_cells": len(seeds),
        "frontier_clusters": len(clusters),
        "frontier_clusters_top": clusters[:20],
        "astar_trials_n": len(astar_trials),
        "astar_ok_n": n_ok,
        "astar_trials": astar_trials,
        "hypothesis": (
            "If base_cell_state!=free or free_component small and astar_ok_n==0, "
            "NO_PASSABLE is map connectivity / start occupancy — not missing frontiers."
        ),
    }
    (out_dir / "first_plan_diag.json").write_text(json.dumps(report, indent=2))
    return report
