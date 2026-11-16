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


def _success(row: dict) -> bool:
    if "sr_proxy" in row:
        return bool(row["sr_proxy"])
    if "sr_proxy_viewpoint" in row:
        return bool(row["sr_proxy_viewpoint"])
    if "objectnav_success_proxy" in row:
        return bool(row["objectnav_success_proxy"])
    return bool(row.get("success"))


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
        s = sum(1 for x in xs if _success(x))
        n = len(xs)
        p, lo, hi = wilson_ci(s, n)
        wrong_stop = sum(
            1
            for x in xs
            if (x.get("fail_bucket") == "wrong_stop")
            or (
                x.get("termination") == "planner_stop"
                and not _success(x)
            )
        )
        cat_stats.append(
            {
                "category": cat,
                "group": GROUP_OF.get(cat, "other"),
                "n": n,
                "success": s,
                "sr": p,
                "sr_wilson95": [lo, hi],
                "wrong_stop": wrong_stop,
                "wrong_stop_rate": (wrong_stop / n) if n else float("nan"),
                "mean_n_steps": _mean([x.get("n_steps") for x in xs]),
                "mean_elapsed_sec": _mean([x.get("elapsed_sec") for x in xs]),
                "mean_forward_m": _mean([x.get("forward_m") for x in xs]),
                "mean_arm_motions": _mean([x.get("n_arm_motions") for x in xs]),
                "mean_effective_observations": _mean(
                    [x.get("n_effective_observations") for x in xs]
                ),
            }
        )

    # micro over concrete rows only (exclude unknown cats from micro if desired)
    concrete_rows = [r for r in rows if r.get("category") in CONCRETE] or list(rows)
    s = sum(1 for r in concrete_rows if _success(r))
    n = len(concrete_rows)
    p, lo, hi = wilson_ci(s, n)

    # macro: unweighted mean of per-category SR for cats with n>0 in CONCRETE
    concrete_stats = [c for c in cat_stats if c["category"] in CONCRETE]
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
        # micro within group
        gn = sum(c["n"] for c in cs)
        gs = sum(c["success"] for c in cs)
        gp, glo, ghi = wilson_ci(gs, gn)
        group_stats.append(
            {
                "group": g,
                "n": gn,
                "success": gs,
                "sr_micro_in_group": gp,
                "sr_wilson95": [glo, ghi],
                "note": "grouping_only_do_not_add_to_overall_with_subcats",
            }
        )

    strata = None
    if strata_key:
        strata = defaultdict(lambda: {"n": 0, "success": 0})
        for r in rows:
            k = str(r.get(strata_key, "unknown"))
            strata[k]["n"] += 1
            strata[k]["success"] += int(_success(r))
        strata = {
            k: {
                **v,
                "sr": v["success"] / v["n"] if v["n"] else float("nan"),
                "sr_wilson95": list(wilson_ci(v["success"], v["n"])[1:]),
            }
            for k, v in strata.items()
        }

    return {
        "n": n,
        "success": s,
        "micro_sr": p,
        "micro_sr_wilson95": [lo, hi],
        "macro_sr": macro,
        "by_category": cat_stats,
        "by_group_report_only": group_stats,
        "by_strata": strata,
        "metrics_notes": [
            "SR_proxy uses VIEW_POINTS horizontal distance when logged as such.",
            "Do not call detection precision 'accuracy' interchangeably with SR.",
            "SPL is N/A unless a footprint-matched geodesic exists.",
            "Repeat seeds must be flagged; not independent scenes for CI interpretation.",
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
    both = sum(1 for i in ids if a[i] and b[i])
    a_only = sum(1 for i in ids if a[i] and not b[i])
    b_only = sum(1 for i in ids if b[i] and not a[i])
    neither = sum(1 for i in ids if (not a[i]) and (not b[i]))
    return {
        "n_paired": len(ids),
        "both_success": both,
        "a_only": a_only,
        "b_only": b_only,
        "neither": neither,
        "delta_sr": ((both + b_only) - (both + a_only)) / len(ids) if ids else float("nan"),
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
    print(f"wrote {args.out} micro_sr={out['micro_sr']:.4f} n={out['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
