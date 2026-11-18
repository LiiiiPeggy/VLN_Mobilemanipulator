#!/usr/bin/env python3
# ################################
# Offline P0/P1/P2 planning compare on a frozen plan_seq local_map (+ optional traj).
# Hard inflate reinflated from OCC (circular, matches SDFMap2D::inflatePoint).
# Soft cost: length × [1 + w × max(0, 1 − d/R)²], d from inflate-only EDT.
# Does NOT change Habitat geometry / execution collision.
# ################################
from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None

RES = 0.05
RAW_UNK, RAW_FREE, RAW_OCC = 0, 1, 2


def footprint_half_w(scale: float) -> float:
    import sys

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from src.robot_scale import footprint_at_scale

    return float(footprint_at_scale(scale)["chassis_half_width_m"])


def load_local_map(path: Path) -> Dict:
    return json.loads(path.read_text())


def cells_to_grid(cells: List, pad: float = 0.6):
    xs = np.array([c[0] for c in cells], dtype=float)
    ys = np.array([c[1] for c in cells], dtype=float)
    xmin, xmax = xs.min() - pad, xs.max() + pad
    ymin, ymax = ys.min() - pad, ys.max() + pad
    # snap to RES
    ox = math.floor(xmin / RES) * RES
    oy = math.floor(ymin / RES) * RES
    nx = int(math.ceil((xmax - ox) / RES)) + 1
    ny = int(math.ceil((ymax - oy) / RES)) + 1
    raw = np.full((nx, ny), RAW_UNK, dtype=np.int8)
    for x, y, r, _i in cells:
        ix = int(round((x - ox) / RES))
        iy = int(round((y - oy) / RES))
        if 0 <= ix < nx and 0 <= iy < ny:
            raw[ix, iy] = int(r)
    return raw, ox, oy


def circular_inflate(raw: np.ndarray, inflate_m: float) -> np.ndarray:
    """Match SDFMap2D::inflatePoint: circular disk of radius inflate_m around OCC."""
    inf = np.zeros_like(raw, dtype=np.int8)
    step = int(math.ceil(inflate_m / RES))
    occ = np.argwhere(raw == RAW_OCC)
    for ix, iy in occ:
        for dx in range(-step, step + 1):
            for dy in range(-step, step + 1):
                jx, jy = ix + dx, iy + dy
                if jx < 0 or jy < 0 or jx >= raw.shape[0] or jy >= raw.shape[1]:
                    continue
                if math.hypot(dx * RES, dy * RES) > inflate_m + 1e-9:
                    continue
                inf[jx, jy] = 1
    return inf


def inflate_only_edt(inf: np.ndarray) -> np.ndarray:
    """Distance (m) to nearest inflate==1 cell; large inside inflate."""
    from scipy import ndimage

    free = inf == 0
    # distance in free cells to nearest obstacle (inflate)
    dist_px = ndimage.distance_transform_edt(free)
    return dist_px * RES


def world_to_ix(x: float, y: float, ox: float, oy: float) -> Tuple[int, int]:
    return int(round((x - ox) / RES)), int(round((y - oy) / RES))


def ix_to_world(ix: int, iy: int, ox: float, oy: float) -> Tuple[float, float]:
    return ox + ix * RES, oy + iy * RES


def astar(
    raw: np.ndarray,
    inf: np.ndarray,
    dist_obs: np.ndarray,
    ox: float,
    oy: float,
    start: Tuple[float, float],
    goal: Tuple[float, float],
    soft_R: float = 0.0,
    soft_w: float = 0.0,
    f0: Optional[Dict] = None,
    success_dist: float = 0.25,
) -> Optional[List[Tuple[float, float]]]:
    """8-connected A* at map RES; NORMAL safety (inflate/OCC block; UNKNOWN only in F0)."""
    sx, sy = world_to_ix(*start, ox, oy)
    gx, gy = world_to_ix(*goal, ox, oy)
    nx, ny = raw.shape

    def in_f0(ix: int, iy: int) -> bool:
        if not f0:
            return False
        wx, wy = ix_to_world(ix, iy, ox, oy)
        # oriented rect in world (yaw about +Z), approx axis-aligned if yaw~0 handled via rot
        cx, cy = f0["cx"], f0["cy"]
        yaw = f0["yaw"]
        hl, hw = f0["hl"], f0["hw"]
        dx, dy = wx - cx, wy - cy
        c, s = math.cos(yaw), math.sin(yaw)
        lx = c * dx + s * dy
        ly = -s * dx + c * dy
        return abs(lx) <= hl and abs(ly) <= hw

    def safe(ix: int, iy: int) -> bool:
        if ix < 0 or iy < 0 or ix >= nx or iy >= ny:
            return False
        if inf[ix, iy] == 1:
            return False
        r = int(raw[ix, iy])
        if r == RAW_OCC:
            return False
        if r == RAW_UNK:
            return in_f0(ix, iy)
        return True

    if not safe(sx, sy):
        # try nearby free like planner
        found = None
        for rad in range(1, 8):
            for dx in range(-rad, rad + 1):
                for dy in range(-rad, rad + 1):
                    if safe(sx + dx, sy + dy):
                        found = (sx + dx, sy + dy)
                        break
                if found:
                    break
            if found:
                break
        if not found:
            return None
        sx, sy = found

    def soft_factor(ix: int, iy: int) -> float:
        if soft_w <= 0 or soft_R <= 1e-9:
            return 1.0
        d = float(dist_obs[ix, iy])
        t = 1.0 - d / soft_R
        if t <= 0:
            return 1.0
        return 1.0 + soft_w * (t * t)

    nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    open_h: List[Tuple[float, int, int, float]] = []
    heapq.heappush(open_h, (0.0, sx, sy, 0.0))
    gscore = {(sx, sy): 0.0}
    parent: Dict[Tuple[int, int], Tuple[int, int]] = {}
    closed = set()
    best_near = None
    best_near_d = 1e9

    while open_h:
        f, x, y, g = heapq.heappop(open_h)
        if (x, y) in closed:
            continue
        closed.add((x, y))
        wx, wy = ix_to_world(x, y, ox, oy)
        dg = math.hypot(wx - goal[0], wy - goal[1])
        if dg < best_near_d:
            best_near_d = dg
            best_near = (x, y)
        if dg <= success_dist:
            # backtrack
            path = [(wx, wy)]
            cur = (x, y)
            while cur in parent:
                cur = parent[cur]
                path.append(ix_to_world(*cur, ox, oy))
            path.reverse()
            path.append(goal)
            return path
        for dx, dy in nbrs:
            nx_, ny_ = x + dx, y + dy
            if not safe(nx_, ny_):
                continue
            # sample mid for diagonal
            if dx != 0 and dy != 0:
                if not safe(x + dx, y) or not safe(x, y + dy):
                    continue
            step = RES * math.sqrt(dx * dx + dy * dy)
            # average soft factor along edge
            fac = 0.5 * (soft_factor(x, y) + soft_factor(nx_, ny_))
            ng = g + step * fac
            key = (nx_, ny_)
            if ng + 1e-9 < gscore.get(key, 1e18):
                gscore[key] = ng
                parent[key] = (x, y)
                h = math.hypot(ix_to_world(nx_, ny_, ox, oy)[0] - goal[0],
                               ix_to_world(nx_, ny_, ox, oy)[1] - goal[1])
                heapq.heappush(open_h, (ng + h, nx_, ny_, ng))
            if len(closed) > 200000:
                break
    if best_near is not None and best_near_d < 0.5:
        path = [ix_to_world(*best_near, ox, oy)]
        cur = best_near
        while cur in parent:
            cur = parent[cur]
            path.append(ix_to_world(*cur, ox, oy))
        path.reverse()
        return path
    return None


def path_len(path: List[Tuple[float, float]]) -> float:
    if not path or len(path) < 2:
        return 0.0
    return float(sum(math.hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1])
                     for i in range(len(path) - 1)))


def clearance_stats(
    path: List[Tuple[float, float]],
    occ_xy: np.ndarray,
    half_w: float,
) -> Dict:
    if path is None or len(path) == 0 or len(occ_xy) == 0:
        return {"n": 0}
    centers = []
    edges = []
    for x, y in path:
        d = float(np.min(np.hypot(occ_xy[:, 0] - x, occ_xy[:, 1] - y)))
        centers.append(d)
        edges.append(d - half_w)
    centers = np.array(centers)
    edges = np.array(edges)
    return {
        "n": int(len(centers)),
        "center_min": float(centers.min()),
        "center_p10": float(np.percentile(centers, 10)),
        "edge_min": float(edges.min()),
        "edge_p10": float(np.percentile(edges, 10)),
        "worst_i": int(np.argmin(edges)),
        "worst_xy": [float(path[int(np.argmin(edges))][0]), float(path[int(np.argmin(edges))][1])],
    }


def plot_compare(
    out_png: Path,
    raw,
    ox,
    oy,
    inf_p0,
    inf_p1,
    paths: Dict[str, Optional[List]],
    traj: Optional[List],
    title: str,
):
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(8, 8))
    # OCC
    occ = np.argwhere(raw == RAW_OCC)
    if len(occ):
        ax.scatter(ox + occ[:, 0] * RES, oy + occ[:, 1] * RES, s=2, c="#333", label="OCC", zorder=2)
    # P0 inflate boundary ring (inflate XOR ~shrunk)
    b0 = np.argwhere((inf_p0 == 1) & (raw != RAW_OCC))
    if len(b0):
        ax.scatter(
            ox + b0[:, 0] * RES, oy + b0[:, 1] * RES, s=1, c="#aabbcc", alpha=0.35, label="P0 inflate"
        )
    b1 = np.argwhere((inf_p1 == 1) & (raw != RAW_OCC))
    if len(b1):
        ax.scatter(
            ox + b1[:, 0] * RES, oy + b1[:, 1] * RES, s=1, c="#ffcc88", alpha=0.35, label="P1 inflate"
        )
    colors = {"P0": "#d62728", "P1": "#2ca02c", "P2": "#1f77b4"}
    for name, path in paths.items():
        if not path:
            continue
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        ax.plot(xs, ys, "-", color=colors.get(name, "k"), lw=2, label=f"{name} plan", zorder=5)
    if traj:
        ax.plot([p[0] for p in traj], [p[1] for p in traj], "--", color="#9467bd", lw=1.5, label="exec traj")
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    ax.set_xlabel("ros x (m)")
    ax.set_ylabel("ros y (m)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    plt.close(fig)


def freeze_case(run: Path, plan_seq: int, out: Path) -> Dict:
    out.mkdir(parents=True, exist_ok=True)
    lm = load_local_map(run / "native_diag" / f"plan_seq_{plan_seq}_local_map.json")
    plans = [
        json.loads(l)
        for l in (run / "native_diag" / "native_plan_diag.jsonl").read_text().splitlines()
        if l.strip()
    ]
    plan = next((p for p in plans if int(p.get("plan_seq", -1)) == plan_seq), plans[0])
    summary = json.loads((run / "summary.json").read_text())
    cells_path = out / "cells.csv"
    with cells_path.open("w") as f:
        f.write("# x,y,raw_occ,inflate\n")
        for x, y, r, i in lm["cells"]:
            f.write(f"{x},{y},{int(r)},{int(i)}\n")
    cands_path = out / "candidates.csv"
    with cands_path.open("w") as f:
        f.write("# candidate_x,candidate_y\n")
        for c in plan.get("candidates") or []:
            g = c.get("candidate")
            if g and len(g) >= 2:
                f.write(f"{g[0]},{g[1]}\n")
    # exec traj (ros)
    traj = []
    if (run / "steps.jsonl").exists():
        for l in (run / "steps.jsonl").read_text().splitlines():
            if not l.strip():
                continue
            st = json.loads(l)
            pm = st.get("publish_meta") or {}
            br = pm.get("base_ros_chassis") or pm.get("odom_ros")
            if br and len(br) >= 2:
                traj.append([float(br[0]), float(br[1])])
    chassis = lm.get("chassis") or plan.get("chassis_start")
    meta = {
        "source_run": str(run),
        "plan_seq": plan_seq,
        "chassis": chassis,
        "yaw_ros": (summary.get("first_plan_diag") or {}).get("base_yaw_ros"),
        "resolution": lm.get("resolution"),
        "selected_path": plan.get("selected_path"),
        "selected_path_len": plan.get("selected_path_len"),
        "result": plan.get("result"),
        "stop_reason": plan.get("stop_reason"),
        "robot_scale": summary.get("robot_scale"),
        "n_traj": len(traj),
        "note": "dev case from formal/e2e dump; not user video",
    }
    (out / "freeze_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    (out / "exec_traj.json").write_text(json.dumps(traj) + "\n")
    return meta


def run_compare(case_dir: Path, robot_scale: float = 0.7, soft_R: float = 0.40, soft_w: float = 2.0):
    meta = json.loads((case_dir / "freeze_meta.json").read_text())
    cells = []
    with (case_dir / "cells.csv").open() as f:
        for line in f:
            if not line.strip() or line[0] == "#":
                continue
            x, y, r, i = line.strip().split(",")
            cells.append([float(x), float(y), int(r), int(i)])
    cands = []
    with (case_dir / "candidates.csv").open() as f:
        for line in f:
            if not line.strip() or line[0] == "#":
                continue
            x, y = line.strip().split(",")[:2]
            cands.append((float(x), float(y)))
    traj = json.loads((case_dir / "exec_traj.json").read_text()) if (case_dir / "exec_traj.json").exists() else []
    half_w = footprint_half_w(robot_scale)
    half_l = 0.651 * robot_scale
    chassis = tuple(meta["chassis"])
    yaw = float(meta.get("yaw_ros") or 0.0)
    raw, ox, oy = cells_to_grid(cells, pad=half_w + 0.8)
    inf0 = circular_inflate(raw, 0.18)
    inf1 = circular_inflate(raw, half_w)
    dist0 = inflate_only_edt(inf0)
    dist1 = inflate_only_edt(inf1)
    f0 = {
        "cx": chassis[0],
        "cy": chassis[1],
        "yaw": yaw,
        "hl": half_l + 0.3,
        "hw": half_w + 0.3,
    }
    occ_xy = np.array([[c[0], c[1]] for c in cells if c[2] == RAW_OCC], dtype=float)

    def best_path(inf, dist, soft_R_, soft_w_):
        best = None
        best_l = 1e18
        n_ok = 0
        for g in cands:
            p = astar(raw, inf, dist, ox, oy, chassis, g, soft_R_, soft_w_, f0=f0)
            if p is None:
                continue
            n_ok += 1
            L = path_len(p)
            if L < best_l:
                best_l = L
                best = p
        return best, best_l if best is not None else None, n_ok

    p0, l0, n0 = best_path(inf0, dist0, 0.0, 0.0)
    p1, l1, n1 = best_path(inf1, dist1, 0.0, 0.0)
    p2, l2, n2 = best_path(inf1, dist1, soft_R, soft_w)

    report = {
        "case": str(case_dir),
        "source_run": meta.get("source_run"),
        "plan_seq": meta.get("plan_seq"),
        "robot_scale": robot_scale,
        "half_w_m": half_w,
        "soft_R_m": soft_R,
        "soft_w": soft_w,
        "units": {"inflate": "m", "soft_R": "m", "soft_w": "dimensionless", "clearance": "m"},
        "P0": {
            "inflate_m": 0.18,
            "n_reachable": n0,
            "n_candidates": len(cands),
            "best_len": l0,
            "clearance": clearance_stats(p0 or [], occ_xy, half_w),
            "path": p0,
        },
        "P1": {
            "inflate_m": half_w,
            "n_reachable": n1,
            "n_candidates": len(cands),
            "best_len": l1,
            "clearance": clearance_stats(p1 or [], occ_xy, half_w),
            "path": p1,
        },
        "P2": {
            "inflate_m": half_w,
            "soft_R": soft_R,
            "soft_w": soft_w,
            "n_reachable": n2,
            "n_candidates": len(cands),
            "best_len": l2,
            "clearance": clearance_stats(p2 or [], occ_xy, half_w),
            "path": p2,
        },
        "exec_traj_clearance": clearance_stats(traj, occ_xy, half_w) if traj else None,
        "orig_selected_path_clearance": clearance_stats(meta.get("selected_path") or [], occ_xy, half_w),
    }
    (case_dir / "p0p1p2_compare.json").write_text(json.dumps(report, indent=2) + "\n")
    plot_compare(
        case_dir / "p0p1p2_topdown.png",
        raw,
        ox,
        oy,
        inf0,
        inf1,
        {"P0": p0, "P1": p1, "P2": p2},
        traj,
        title=f"{case_dir.name} P0/P1/P2 (half_w={half_w:.4f})",
    )
    # slim stdout
    slim = {
        k: {
            "n_reachable": report[k]["n_reachable"],
            "best_len": report[k]["best_len"],
            "edge_min": (report[k]["clearance"] or {}).get("edge_min"),
            "edge_p10": (report[k]["clearance"] or {}).get("edge_p10"),
            "center_min": (report[k]["clearance"] or {}).get("center_min"),
        }
        for k in ("P0", "P1", "P2")
    }
    slim["exec_edge_min"] = (report.get("exec_traj_clearance") or {}).get("edge_min")
    slim["orig_edge_min"] = (report.get("orig_selected_path_clearance") or {}).get("edge_min")
    print(json.dumps(slim, indent=2))
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze_run", type=Path, default=None)
    ap.add_argument("--plan_seq", type=int, default=20)
    ap.add_argument("--case_dir", type=Path, required=True)
    ap.add_argument("--robot_scale", type=float, default=0.7)
    ap.add_argument("--soft_R", type=float, default=0.40)
    ap.add_argument("--soft_w", type=float, default=2.0)
    ap.add_argument("--compare_only", action="store_true")
    args = ap.parse_args()
    if args.freeze_run and not args.compare_only:
        freeze_case(args.freeze_run, args.plan_seq, args.case_dir)
    run_compare(args.case_dir, args.robot_scale, args.soft_R, args.soft_w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
