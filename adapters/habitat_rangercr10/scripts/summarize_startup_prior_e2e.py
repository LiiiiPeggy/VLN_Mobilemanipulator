#!/usr/bin/env python3
# ################################
# Aggregate startup_prior ObjectNav e2e A/B jsonl → tables + markdown.
# ################################
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_rows(path: Path):
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def arm_stats(rows):
    n = len(rows)
    if n == 0:
        return {}
    succ = sum(1 for r in rows if r.get("objectnav_success_proxy"))
    # SPL proxy: success * (straight/path) unavailable without geodesic → report N/A;
    # use success rate + mean forward as exploration proxy.
    entered = sum(1 for r in rows if r.get("entered_explore"))
    start_block = sum(1 for r in rows if r.get("fail_class") == "start_blocked_nopassable")
    mid = sum(1 for r in rows if r.get("fail_class") == "mid_plan_nopassable_or_stuck")
    no_goal = sum(1 for r in rows if r.get("fail_class") == "explore_no_goal")
    stop_far = sum(1 for r in rows if r.get("fail_class") == "stop_not_near_goal")
    runtime = sum(1 for r in rows if r.get("fail_class") == "runtime_or_interface")
    fwd = [float(r.get("forward_m") or 0) for r in rows]
    n_expl = [int(r.get("n_explore") or 0) for r in rows]
    elap = [float(r.get("elapsed_sec") or 0) for r in rows if r.get("elapsed_sec") is not None]
    fail_c = Counter(r.get("fail_class") for r in rows)
    return {
        "n": n,
        "success_proxy": succ,
        "success_rate": succ / n,
        "spl_note": "official SPL not computed (no geodesic path length in adapter summary); report SR proxy only",
        "entered_explore_rate": entered / n,
        "start_blocked_rate": start_block / n,
        "nopassable_or_stuck_rate": mid / n,
        "explore_no_goal_rate": no_goal / n,
        "stop_not_near_goal_rate": stop_far / n,
        "runtime_error_rate": runtime / n,
        "mean_forward_m": sum(fwd) / n,
        "mean_n_explore": sum(n_expl) / n,
        "mean_elapsed_sec": (sum(elap) / len(elap)) if elap else None,
        "fail_class_hist": dict(fail_c),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-id", default="")
    args = ap.parse_args()
    rows = load_rows(args.summary)
    by_mode = defaultdict(list)
    for r in rows:
        by_mode[r.get("startup_prior_mode", "?")].append(r)
    agg = {m: arm_stats(rs) for m, rs in by_mode.items()}
    out = {
        "batch_id": args.batch_id,
        "n_rows": len(rows),
        "by_mode": agg,
        "rows": rows,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"aggregate_{args.batch_id or 'latest'}.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )

    lines = [
        f"# Startup prior ObjectNav e2e aggregate ({args.batch_id})",
        "",
        "Task: **ObjectNav** (HM3D-v2 val) via `apexnav_real_episode` / ApexNav planner.",
        "Success proxy: `termination==planner_stop` AND `near_goal` (dtg ≤ 1.0 m).",
        "Official challenge SPL not available in this adapter path (no geodesic).",
        "",
        "| mode | n | SR_proxy | entered_explore | start_blocked | mid_nopass/stuck | explore_no_goal | mean_fwd_m | mean_n_explore |",
        "|------|---|----------|-----------------|---------------|------------------|-----------------|------------|----------------|",
    ]
    for m, a in sorted(agg.items()):
        lines.append(
            f"| {m} | {a.get('n')} | {a.get('success_rate', 0):.3f} "
            f"({a.get('success_proxy')}/{a.get('n')}) | "
            f"{a.get('entered_explore_rate', 0):.3f} | "
            f"{a.get('start_blocked_rate', 0):.3f} | "
            f"{a.get('nopassable_or_stuck_rate', 0):.3f} | "
            f"{a.get('explore_no_goal_rate', 0):.3f} | "
            f"{a.get('mean_forward_m', 0):.2f} | "
            f"{a.get('mean_n_explore', 0):.1f} |"
        )
    lines.append("")
    lines.append("## Fail class histogram")
    for m, a in sorted(agg.items()):
        lines.append(f"- **{m}**: `{a.get('fail_class_hist')}`")
    lines.append("")
    (args.out / f"aggregate_{args.batch_id or 'latest'}.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in agg.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
