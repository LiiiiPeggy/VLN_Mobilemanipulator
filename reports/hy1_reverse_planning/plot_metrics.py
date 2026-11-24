#!/usr/bin/env python3
"""Rebuild CSV + figures for HY1 reverse-planning ablation from run dirs.

################################
Usage:
  python3 reports/hy1_reverse_planning/plot_metrics.py \\
    --index reports/hy1_reverse_planning/runs_index.jsonl \\
    --out_dir reports/hy1_reverse_planning
################################
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def load_jsonl(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def summarize_run(out_dir: Path) -> Dict[str, Any]:
    s = json.loads((out_dir / "summary.json").read_text())
    steps = load_jsonl(out_dir / "steps.jsonl")
    actions = load_jsonl(out_dir / "actions.jsonl")
    rev = s.get("reverse_planning") or {}
    n_fwd = n_turn = n_rev = n_blk = n_trunc = n_noprog = 0
    executed_len = 0.0
    xs, zs = [], []
    rev_xs, rev_zs = [], []
    coll_xz = []
    for st in steps:
        base = st.get("base") or {}
        if "x" in base and "z" in base:
            xs.append(float(base["x"]))
            zs.append(float(base["z"]))
        ex = st.get("exec") or {}
        name = str(ex.get("actual_action") or st.get("planner_action_name") or "")
        if "BACKWARD" in name:
            n_rev += 1
            if "x" in base:
                rev_xs.append(float(base["x"]))
                rev_zs.append(float(base["z"]))
        elif name.startswith("MOVE_FORWARD"):
            n_fwd += 1
        elif "TURN" in name:
            n_turn += 1
        if ex.get("blocked"):
            n_blk += 1
            if "x" in base:
                coll_xz.append((float(base["x"]), float(base["z"])))
        if ex.get("truncated"):
            n_trunc += 1
        moved = float(ex.get("moved_m") or 0.0)
        executed_len += abs(moved)
        if moved < 0.02 and abs(float(ex.get("yaw_delta") or 0.0)) < math.radians(5):
            if (st.get("phase") or "").startswith("explore"):
                n_noprog += 1
    # progress proxy: distance from spawn along explore
    progress = []
    if xs:
        x0, z0 = xs[0], zs[0]
        for x, z in zip(xs, zs):
            progress.append(math.hypot(x - x0, z - z0))
    return {
        "run_id": s.get("run_id") or out_dir.name,
        "out_dir": str(out_dir),
        "mode": rev.get("mode") or "A",
        "termination": s.get("termination"),
        "n_steps": s.get("n_steps"),
        "sum_moved_m": s.get("sum_moved_m"),
        "executed_path_length_m": executed_len,
        "n_blocked_exec": s.get("n_blocked_exec"),
        "n_truncated_exec": s.get("n_truncated_exec"),
        "n_forward": n_fwd,
        "n_turn": n_turn,
        "n_reverse": n_rev,
        "n_no_progress_explore": n_noprog,
        "sum_reverse_m": rev.get("sum_reverse_m"),
        "n_gear_switches": rev.get("n_gear_switches"),
        "n_hybrid_calls": rev.get("n_hybrid_calls"),
        "n_hybrid_fail": rev.get("n_hybrid_fail"),
        "elapsed_sec": s.get("elapsed_sec"),
        "near_goal": s.get("near_goal"),
        "final_dtg": s.get("final_distance_to_goal_eval_only"),
        "traj_x": xs,
        "traj_z": zs,
        "rev_x": rev_xs,
        "rev_z": rev_zs,
        "coll_xz": coll_xz,
        "progress": progress,
        "escape_success": bool(n_rev > 0 and (s.get("sum_moved_m") or 0) > 1.2),
        "nav_resumption": bool((s.get("sum_moved_m") or 0) > 1.5 and n_noprog < 10),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--out_dir", type=Path, required=True)
    ap.add_argument(
        "--baseline_a",
        type=Path,
        default=Path(
            "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/"
            "ppo_chassis_hy1_20261123_220210_hy1_plant_0"
        ),
    )
    args = ap.parse_args()
    out = args.out_dir
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    if args.baseline_a.is_dir() and (args.baseline_a / "summary.json").is_file():
        r = summarize_run(args.baseline_a)
        r["mode"] = "A"
        r["budget"] = "orig"
        r["source"] = "immutable_original"
        rows.append(r)

    for ent in load_jsonl(args.index):
        od = Path(ent.get("out_dir") or "")
        if not od.is_dir() or not (od / "summary.json").is_file():
            continue
        r = summarize_run(od)
        r["budget"] = ent.get("budget")
        r["rep"] = ent.get("rep")
        r["source"] = "ablation"
        rows.append(r)

    # CSV (no traj arrays)
    csv_path = out / "metrics.csv"
    keys = [
        "mode",
        "budget",
        "rep",
        "run_id",
        "termination",
        "n_steps",
        "sum_moved_m",
        "executed_path_length_m",
        "n_forward",
        "n_turn",
        "n_reverse",
        "n_blocked_exec",
        "n_truncated_exec",
        "n_no_progress_explore",
        "sum_reverse_m",
        "n_gear_switches",
        "n_hybrid_calls",
        "elapsed_sec",
        "escape_success",
        "nav_resumption",
        "near_goal",
        "final_dtg",
        "source",
    ]
    with csv_path.open("w") as f:
        f.write(",".join(keys) + "\n")
        for r in rows:
            f.write(
                ",".join(
                    str(r.get(k, "")).replace(",", ";") for k in keys
                )
                + "\n"
            )

    agg = {
        "n_rows": len(rows),
        "by_mode": {},
        "csv": str(csv_path),
    }
    for r in rows:
        m = r["mode"]
        agg["by_mode"].setdefault(m, []).append(
            {k: r.get(k) for k in keys if k not in ("run_id",)}
        )
    (out / "aggregate.json").write_text(json.dumps(agg, indent=2) + "\n")

    # Fig1: traj overlay
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    colors = {"A": "#444444", "B": "#1f77b4", "C": "#d62728"}
    for r in rows:
        if not r.get("traj_x"):
            continue
        ax.plot(
            r["traj_x"],
            r["traj_z"],
            "-",
            color=colors.get(r["mode"], "k"),
            lw=1.6,
            label=f"{r['mode']} ({r.get('budget')})",
            alpha=0.85,
        )
        if r.get("rev_x"):
            ax.scatter(r["rev_x"], r["rev_z"], c=colors.get(r["mode"], "k"), s=18, marker="s")
        if r.get("coll_xz"):
            cx, cz = zip(*r["coll_xz"])
            ax.scatter(cx, cz, c="orange", s=12, marker="x", alpha=0.5)
        ax.scatter(r["traj_x"][0], r["traj_z"][0], c="green", s=40, zorder=5)
        ax.scatter(r["traj_x"][-1], r["traj_z"][-1], c="purple", s=40, zorder=5)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("Habitat x (m)")
    ax.set_ylabel("Habitat z (m)")
    ax.set_title("HY1 plant: base trajectory (A/B/C)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig1_traj_xyz.png", dpi=160)
    plt.close(fig)

    # Fig2: progress vs step
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for r in rows:
        prog = r.get("progress") or []
        if not prog:
            continue
        ax.plot(
            range(len(prog)),
            prog,
            color=colors.get(r["mode"], "k"),
            label=f"{r['mode']}",
            lw=1.5,
        )
    ax.set_xlabel("step")
    ax.set_ylabel("displacement from first pose (m)")
    ax.set_title("Navigation progress vs action steps")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "fig2_progress.png", dpi=160)
    plt.close(fig)

    # Fig3: action/collision bars
    # Prefer successful completed runs for bar charts (skip handshake failures).
    good = [
        r
        for r in rows
        if int(r.get("n_steps") or 0) > 0 and r.get("termination") != "exception"
    ]
    modes = sorted({r["mode"] for r in good} or {r["mode"] for r in rows})
    metrics = ["n_forward", "n_turn", "n_reverse", "n_blocked_exec", "n_truncated_exec", "n_no_progress_explore"]
    # pick one row per mode (latest good)
    pick = {}
    for r in good or rows:
        pick[r["mode"]] = r
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    x = np.arange(len(metrics))
    width = 0.25
    for i, m in enumerate(modes):
        vals = [float(pick[m].get(k) or 0) for k in metrics]
        ax.bar(x + i * width, vals, width, label=m, color=colors.get(m, "k"))
    ax.set_xticks(x + width)
    ax.set_xticklabels(metrics, rotation=25, ha="right")
    ax.set_ylabel("count")
    ax.set_title("Action / collision statistics")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "fig3_action_collision.png", dpi=160)
    plt.close(fig)

    # Fig4: efficiency
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    labels = ["executed_path_length_m", "n_steps", "sum_reverse_m", "elapsed_sec"]
    for i, m in enumerate(modes):
        vals = [float(pick[m].get(k) or 0) for k in labels]
        # normalize elapsed for display
        vals[3] = vals[3] / 60.0  # minutes
        ax.bar(np.arange(len(labels)) + i * width, vals, width, label=m, color=colors.get(m, "k"))
    ax.set_xticks(np.arange(len(labels)) + width)
    ax.set_xticklabels(["path_m", "n_steps", "rev_m", "elapsed_min"], rotation=15)
    ax.set_title("Efficiency comparison")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "fig4_efficiency.png", dpi=160)
    plt.close(fig)

    print(json.dumps({"csv": str(csv_path), "figures": str(fig_dir), "n": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
