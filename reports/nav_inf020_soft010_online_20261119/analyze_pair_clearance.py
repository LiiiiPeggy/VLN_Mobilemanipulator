#!/usr/bin/env python3
# ################################
# Build paired clearance table + top-down overlays for legacy018 vs inf020_soft010.
# ################################
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
except Exception:
    plt = None

HALF_W = 0.4347 * 0.7
HALF_L = 0.651 * 0.7


def load_steps(run: Path) -> List[dict]:
    p = run / "steps.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def traj_ros(steps: List[dict]) -> List[Tuple[float, float, float]]:
    out = []
    for st in steps:
        pm = st.get("publish_meta") or {}
        br = pm.get("base_ros_chassis") or pm.get("odom_ros")
        yaw = float(pm.get("base_yaw_ros") or 0.0)
        if br and len(br) >= 2:
            out.append((float(br[0]), float(br[1]), yaw))
    return out


def path_from_plans(run: Path) -> List[Tuple[float, float]]:
    pl = run / "native_diag" / "native_plan_diag.jsonl"
    if not pl.exists():
        return []
    best = []
    best_len = -1.0
    for line in pl.read_text().splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        path = p.get("selected_path") or []
        L = float(p.get("selected_path_len") or 0)
        if len(path) >= 2 and L > best_len:
            best_len = L
            best = [(float(a), float(b)) for a, b in path]
    return best


def occ_from_map(run: Path, prefer_seq: Optional[int] = None) -> np.ndarray:
    maps = sorted(
        (run / "native_diag").glob("plan_seq_*_local_map.json"),
        key=lambda p: int(p.stem.split("_")[2]),
    )
    if not maps:
        return np.zeros((0, 2))
    if prefer_seq is not None:
        for m in maps:
            if int(m.stem.split("_")[2]) == prefer_seq:
                maps = [m]
                break
    else:
        maps = [maps[min(len(maps) // 3, len(maps) - 1)]]
    cells = json.loads(maps[0].read_text())["cells"]
    return np.array([[c[0], c[1]] for c in cells if int(c[2]) == 2], dtype=float)


def clearance_stats(xy: List[Tuple[float, float]], occ: np.ndarray) -> Dict:
    if not xy or len(occ) == 0:
        return {"n": 0}
    centers, edges = [], []
    worst_i = 0
    for i, (x, y) in enumerate(xy):
        d = float(np.min(np.hypot(occ[:, 0] - x, occ[:, 1] - y)))
        centers.append(d)
        edges.append(d - HALF_W)
        if edges[-1] < edges[worst_i]:
            worst_i = i
    c = np.array(centers)
    e = np.array(edges)
    return {
        "n": int(len(c)),
        "center_min": float(c.min()),
        "center_p10": float(np.percentile(c, 10)),
        "edge_min": float(e.min()),
        "edge_p10": float(np.percentile(e, 10)),
        "worst_xy": [float(xy[worst_i][0]), float(xy[worst_i][1])],
        "worst_i": int(worst_i),
    }


def path_length(xy: List[Tuple[float, float]]) -> float:
    if len(xy) < 2:
        return 0.0
    return float(
        sum(math.hypot(xy[i + 1][0] - xy[i][0], xy[i + 1][1] - xy[i][1]) for i in range(len(xy) - 1))
    )


def count_rejects(steps: List[dict]) -> Dict:
    blocked = 0
    contact_submit = 0
    for st in steps:
        ex = st.get("exec") or {}
        if ex.get("blocked") or ex.get("rejected") or ex.get("collision_rejected"):
            blocked += 1
        if ex.get("contact_after_commit") or ex.get("penetration_after_commit"):
            contact_submit += 1
        # v1.2 fields
        if (ex.get("reject_reason") or "").startswith("collision"):
            blocked += 1
    return {"action_rejects": blocked, "commit_penetration_flags": contact_submit}


def footprint_poly(x: float, y: float, yaw: float):
    c, s = math.cos(yaw), math.sin(yaw)
    corners = []
    for sl, sw in ((1, 1), (1, -1), (-1, -1), (-1, 1)):
        lx, ly = sl * HALF_L, sw * HALF_W
        corners.append((x + c * lx - s * ly, y + s * lx + c * ly))
    return corners


def plot_pair(out_png: Path, title: str, occ, plan, traj, yaw_samples):
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(8, 8))
    if len(occ):
        ax.scatter(occ[:, 0], occ[:, 1], s=2, c="#222", label="OCC", zorder=2)
    if plan:
        ax.plot([p[0] for p in plan], [p[1] for p in plan], "-", color="#1f77b4", lw=2, label="plan")
    if traj:
        ax.plot([p[0] for p in traj], [p[1] for p in traj], "--", color="#d62728", lw=1.5, label="exec")
        # sample footprints
        for i in np.linspace(0, len(traj) - 1, min(8, len(traj))).astype(int):
            x, y, yaw = traj[i] if len(traj[i]) == 3 else (traj[i][0], traj[i][1], 0.0)
            if yaw_samples and i < len(yaw_samples):
                yaw = yaw_samples[i]
            poly = footprint_poly(x, y, yaw)
            ax.add_patch(
                Polygon(poly, closed=True, fill=False, edgecolor="#ff7f0e", lw=0.8, alpha=0.7)
            )
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.legend(loc="best", fontsize=8)
    ax.set_xlabel("ros x")
    ax.set_ylabel("ros y")
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    plt.close(fig)


def analyze_run(run: Path, label: str, out_dir: Path) -> Dict:
    steps = load_steps(run)
    traj3 = traj_ros(steps)
    traj = [(x, y) for x, y, _ in traj3]
    yaws = [yaw for _, _, yaw in traj3]
    plan = path_from_plans(run)
    occ = occ_from_map(run)
    summary = json.loads((run / "summary.json").read_text()) if (run / "summary.json").exists() else {}
    rec = {
        "label": label,
        "run": str(run),
        "termination": summary.get("termination"),
        "n_steps": summary.get("n_steps"),
        "success_claimed": summary.get("success_claimed"),
        "near_goal": summary.get("near_goal"),
        "plan_len": path_length(plan),
        "exec_len": path_length(traj),
        "plan_clearance": clearance_stats(plan, occ),
        "exec_clearance": clearance_stats(traj, occ),
        "rejects": count_rejects(steps),
    }
    # first plan/exec divergence
    if plan and traj:
        diverge = None
        for i, (x, y) in enumerate(traj):
            # nearest plan point
            d = min(math.hypot(x - px, y - py) for px, py in plan)
            if d > 0.35:
                diverge = {"traj_i": i, "xy": [x, y], "dist_to_plan": d, "yaw": yaws[i] if i < len(yaws) else None}
                break
        rec["first_plan_exec_diverge"] = diverge
    png = out_dir / f"{label}_topdown.png"
    plot_pair(png, label, occ, plan, traj3, yaws)
    rec["topdown"] = str(png)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch_jsonl", type=Path, required=True)
    ap.add_argument("--out_dir", type=Path, required=True)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in args.batch_jsonl.read_text().splitlines() if l.strip()]
    analyses = []
    for r in rows:
        run = Path(r["run_dir"])
        if not run.exists():
            continue
        analyses.append(analyze_run(run, r["tag"], args.out_dir))
    # pair table by scene prefix
    table = {"pairs": [], "runs": analyses}
    (args.out_dir / "pair_analysis.json").write_text(json.dumps(table, indent=2) + "\n")
    # markdown
    lines = ["# Online pair clearance", "", "| tag | term | n | plan_edge_min | exec_edge_min | plan_len | exec_len | rejects |",
             "|-----|------|---|---------------|---------------|----------|----------|---------|"]
    for a in analyses:
        pc = a.get("plan_clearance") or {}
        ec = a.get("exec_clearance") or {}
        lines.append(
            f"| {a['label']} | {a.get('termination')} | {a.get('n_steps')} | "
            f"{pc.get('edge_min')} | {ec.get('edge_min')} | {a.get('plan_len'):.2f} | "
            f"{a.get('exec_len'):.2f} | {a.get('rejects')} |"
        )
    (args.out_dir / "PAIR_TABLE.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
