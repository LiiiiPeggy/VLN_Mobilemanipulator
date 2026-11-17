#!/usr/bin/env python3
# ################################
# VLN adapt: reusable category metrics (micro/macro SR, Wilson CI, paired stub)
# ################################
"""Summarize episode result rows by concrete category and optional observation strata.

Input JSONL/JSON rows must include at least: category, success (bool) or sr_proxy.
Does not invent SPL. Distinguishes navigation SR_proxy from detection precision.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from wilson_ci import wilson_ci  # noqa: E402

CONCRETE = ["chair", "bed", "sofa", "plant", "toilet", "tv_monitor"]
# Report groupings — never double-count into micro
GROUP_OF = {
    "chair": "large_furniture",
    "bed": "large_furniture",
    "sofa": "large_furniture",
    "toilet": "large_furniture",
    "tv_monitor": "large_furniture",
    "plant": "large_furniture",
    "cup": "small_object",
    "mug": "small_object",
}


def _success(row: dict):
    """Return True/False, or None if success field is missing (do NOT coerce to False)."""
    for key in ("sr_proxy", "sr_proxy_viewpoint", "objectnav_success_proxy", "success"):
        if key in row:
            val = row[key]
            if val is None:
                return None
            return bool(val)
    return None


def _load_rows(path: Path):
    text = path.read_text().strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    for key in ("episodes", "rows", "results"):
        if key in data and isinstance(data[key], list):
            return data[key]
    raise SystemExit(f"Unrecognized JSON structure in {path}")


def summarize(rows, strata_key: str | None = None):
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[str(r.get("category"))].append(r)

    cat_stats = []
    for cat in sorted(by_cat):
        xs = by_cat[cat]
        known = [x for x in xs if _success(x) is not None]
        unknown = len(xs) - len(known)
        s = sum(1 for x in known if _success(x) is True)
        n = len(known)
        p, lo, hi = wilson_ci(s, n)
        wrong_stop = sum(1 for x in xs if x.get("fail_bucket") == "wrong_stop")
        cat_stats.append(
            {
                "category": cat,
                "group": GROUP_OF.get(cat, "other"),
                "n_rows": len(xs),
                "n_scored": n,
                "n_success_unknown": unknown,
                "success": s,
                "sr": p,
                "sr_wilson95": [lo, hi],
                "wrong_stop": wrong_stop,
                "wrong_stop_rate": (wrong_stop / len(xs)) if xs else float("nan"),
                "fail_bucket_counts": dict(
                    __import__("collections").Counter(x.get("fail_bucket") for x in xs)
                ),
                "run_status_counts": dict(
                    __import__("collections").Counter(x.get("run_status") for x in xs)
                ),
                "mean_n_steps": _mean(
                    [x.get("n_steps_observed", x.get("n_steps")) for x in xs]
                ),
                "mean_elapsed_sec": _mean([x.get("elapsed_sec") for x in xs]),
                "mean_forward_m": _mean(
                    [x.get("sum_moved_m", x.get("forward_m")) for x in xs]
                ),
                "mean_arm_motions": _mean([x.get("n_arm_motions") for x in xs]),
                "mean_effective_observations": _mean(
                    [x.get("n_effective_observations") for x in xs]
                ),
                "n_blocked_exec_sum": sum(
                    int(x["n_blocked_exec"])
                    for x in xs
                    if x.get("n_blocked_exec") is not None
                ),
                "n_truncated_exec_sum": sum(
                    int(x["n_truncated_exec"])
                    for x in xs
                    if x.get("n_truncated_exec") is not None
                ),
            }
        )

    # micro over concrete rows with known success only
    concrete_rows = [r for r in rows if r.get("category") in CONCRETE] or list(rows)
    known = [r for r in concrete_rows if _success(r) is not None]
    s = sum(1 for r in known if _success(r) is True)
    n = len(known)
    p, lo, hi = wilson_ci(s, n)

    concrete_stats = [c for c in cat_stats if c["category"] in CONCRETE and c["n_scored"] > 0]
    macro = (
        sum(c["sr"] for c in concrete_stats) / len(concrete_stats)
        if concrete_stats
        else float("nan")
    )

    # group rollups (for reporting only)
    groups = defaultdict(list)
    for c in cat_stats:
        groups[c["group"]].append(c)
    group_stats = []
    for g, cs in sorted(groups.items()):
        gn = sum(c["n_scored"] for c in cs)
        gs = sum(c["success"] for c in cs)
        gp, glo, ghi = wilson_ci(gs, gn)
        group_stats.append(
            {
                "group": g,
                "n_scored": gn,
                "success": gs,
                "sr_micro_in_group": gp,
                "sr_wilson95": [glo, ghi],
                "note": "grouping_only_do_not_add_to_overall_with_subcats",
            }
        )

    strata = None
    # strata: skip rows with unknown success for SR; still count unknowns
    if strata_key:
        strata = defaultdict(lambda: {"n_rows": 0, "n_scored": 0, "success": 0, "n_unknown": 0})
        for r in rows:
            k = str(r.get(strata_key, "unknown"))
            strata[k]["n_rows"] += 1
            suc = _success(r)
            if suc is None:
                strata[k]["n_unknown"] += 1
            else:
                strata[k]["n_scored"] += 1
                strata[k]["success"] += int(suc)
        strata = {
            k: {
                **v,
                "sr": (v["success"] / v["n_scored"]) if v["n_scored"] else None,
                "sr_wilson95": (
                    list(wilson_ci(v["success"], v["n_scored"])[1:])
                    if v["n_scored"]
                    else None
                ),
            }
            for k, v in strata.items()
        }

    return {
        "n_rows": len(concrete_rows),
        "n_scored": n,
        "n_success_unknown": len(concrete_rows) - n,
        "success": s,
        "micro_sr": p,
        "micro_sr_wilson95": [lo, hi],
        "macro_sr": macro,
        "by_category": cat_stats,
        "by_group_report_only": group_stats,
        "by_strata": strata,
        "metrics_notes": [
            "SR_proxy uses VIEW_POINTS; missing success fields stay unknown (not false).",
            "near_goal is reported separately and is not SR_proxy.",
            "Do not call detection precision 'accuracy' interchangeably with SR.",
            "SPL is N/A unless a footprint-matched geodesic exists.",
            "Repeat seeds must be flagged; not independent scenes for CI interpretation.",
            "camera_mode for ApexNav baseline A must be fixed_base_gimbal (+ simulated_gimbal).",
        ],
    }


def _mean(xs):
    vals = [float(x) for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return (sum(vals) / len(vals)) if vals else None


def paired_compare(rows_a, rows_b, id_key="episode_list_id"):
    """McNemar-style paired success counts for same episode ids."""
    a = {r[id_key]: _success(r) for r in rows_a if id_key in r}
    b = {r[id_key]: _success(r) for r in rows_b if id_key in r}
    ids = sorted(set(a) & set(b))
    scored_ids = [i for i in ids if a[i] is not None and b[i] is not None]
    unknown_pair = [i for i in ids if i not in scored_ids]
    both = sum(1 for i in scored_ids if a[i] and b[i])
    a_only = sum(1 for i in scored_ids if a[i] and not b[i])
    b_only = sum(1 for i in scored_ids if b[i] and not a[i])
    neither = sum(1 for i in scored_ids if (not a[i]) and (not b[i]))
    dup_a = [i for i, c in __import__("collections").Counter(r.get(id_key) for r in rows_a).items() if c > 1]
    dup_b = [i for i, c in __import__("collections").Counter(r.get(id_key) for r in rows_b).items() if c > 1]
    return {
        "n_id_overlap": len(ids),
        "n_paired_scored": len(scored_ids),
        "unknown_or_missing_success_ids": unknown_pair,
        "duplicate_ids_a": dup_a,
        "duplicate_ids_b": dup_b,
        "missing_in_b": sorted(set(a) - set(b)),
        "missing_in_a": sorted(set(b) - set(a)),
        "both_success": both,
        "a_only": a_only,
        "b_only": b_only,
        "neither": neither,
        "delta_sr": (
            ((both + b_only) - (both + a_only)) / len(scored_ids) if scored_ids else None
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", type=Path, help="JSON/JSONL episode results")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--strata", default=None, help="optional observation-condition field")
    ap.add_argument("--paired_with", type=Path, default=None)
    ap.add_argument("--id_key", default="episode_list_id")
    args = ap.parse_args()

    rows = _load_rows(args.results)
    out = summarize(rows, strata_key=args.strata)
    if args.paired_with:
        out["paired"] = paired_compare(rows, _load_rows(args.paired_with), id_key=args.id_key)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")
    n = out.get("n_scored", out.get("n"))
    ms = out.get("micro_sr")
    print(f"wrote {args.out} micro_sr={ms} n_scored={n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
