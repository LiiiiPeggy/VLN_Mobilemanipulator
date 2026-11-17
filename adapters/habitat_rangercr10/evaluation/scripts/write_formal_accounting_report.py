#!/usr/bin/env python3
# ################################
# VLN adapt: formal independent-eval accounting report (per-cat + ledger)
# ################################
"""Build human-readable accounting from formal JSONL + validity table.

Does not invent success/SPL. near_goal reported separately from SR_proxy.
Invalid spawn / run fail / wrong stop / no SEARCH / stall / budget exhaust
are counted explicitly; timeouts/crashes are not dropped.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from ingest_episode_run import ingest_run  # noqa: E402
from summarize_category_metrics import summarize  # noqa: E402
from wilson_ci import wilson_ci  # noqa: E402

RUN_ROOT = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real")


def _load_jsonl(path: Path):
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _reingest_rows(rows):
    """Prefer fresh ingest from run_dir so empty_run / STOP / SHA stay current."""
    out = []
    for r in rows:
        run_id = r.get("run_id")
        run_dir = Path(r["run_dir"]) if r.get("run_dir") else (RUN_ROOT / run_id if run_id else None)
        if run_dir and run_dir.is_dir():
            fresh = ingest_run(
                run_dir,
                episode_list_id=r.get("episode_list_id"),
                batch_id=r.get("batch_id"),
                recovery_of=r.get("recovery_of"),
            )
            for k in (
                "scene",
                "category",
                "episode_id",
                "shell_rc",
                "archive_role",
                "shell_claimed_max_steps",
                "shell_claimed_max_explore",
                "shell_claimed_code_git_sha",
            ):
                if r.get(k) is not None and fresh.get(k) in (None,):
                    fresh[k] = r.get(k)
                elif k in ("scene", "category", "episode_id") and not fresh.get(k):
                    fresh[k] = r.get(k)
            out.append(fresh)
        else:
            out.append(r)
    return out


def _mean(xs):
    vals = [float(x) for x in xs if x is not None]
    return (sum(vals) / len(vals)) if vals else None


def build(rows, validity_doc=None):
    validity_episodes = (validity_doc or {}).get("episodes") or []
    validity_counts = Counter(e.get("status") for e in validity_episodes)
    invalid_rows = [e for e in validity_episodes if e.get("status") == "invalid"]
    pending_rows = [e for e in validity_episodes if e.get("status") == "pending"]

    # dedupe by episode_list_id keeping first (formal runner is sequential; recovery tagged)
    by_id = {}
    dups = []
    for r in rows:
        eid = r.get("episode_list_id")
        if eid in by_id:
            dups.append(eid)
            # keep first unless this is not a recovery overwrite of success
            continue
        by_id[eid] = r
    uniq = list(by_id.values())

    base = summarize(uniq)
    fail_all = Counter(r.get("fail_bucket") for r in uniq)
    run_all = Counter(r.get("run_status") for r in uniq)
    term_all = Counter(r.get("termination") for r in uniq)

    accounting = {
        "n_list_original": len(validity_episodes) or None,
        "validity_status_counts": dict(validity_counts),
        "n_invalid_spawn": validity_counts.get("invalid", 0),
        "n_pending_validity": validity_counts.get("pending", 0),
        "n_valid_scheduled": validity_counts.get("valid", 0),
        "n_rows_ingested": len(rows),
        "n_unique_episode_ids": len(uniq),
        "duplicate_episode_ids": dups,
        "run_status_counts": dict(run_all),
        "termination_counts": dict(term_all),
        "fail_bucket_counts": dict(fail_all),
        "n_run_fail": sum(
            1
            for r in uniq
            if r.get("run_status") not in (None, "ok")
        ),
        "n_empty_run": sum(1 for r in uniq if r.get("run_status") == "empty_run"),
        "n_wrong_stop": fail_all.get("wrong_stop", 0),
        "n_no_search": sum(
            1
            for r in uniq
            if r.get("entered_search_best") is False
            or r.get("fail_bucket") == "no_search_best"
        ),
        "n_exec_stalled": fail_all.get("exec_stalled", 0),
        "n_budget_exhausted": fail_all.get("budget_exhausted", 0)
        + fail_all.get("explore_budget_exhausted", 0),
        "n_near_goal_true": sum(1 for r in uniq if r.get("near_goal") is True),
        "n_sr_proxy_true": sum(1 for r in uniq if r.get("sr_proxy") is True),
        "mean_sum_moved_m": _mean([r.get("sum_moved_m") for r in uniq]),
        "mean_n_init_lookaround": _mean(
            [r.get("n_init_lookaround_observed") for r in uniq]
        ),
        "mean_n_explore": _mean([r.get("n_explore_observed") for r in uniq]),
        "mean_n_steps": _mean([r.get("n_steps_observed") for r in uniq]),
        "sum_blocked_exec": sum(
            int(r["n_blocked_exec"])
            for r in uniq
            if r.get("n_blocked_exec") is not None
        ),
        "sum_truncated_exec": sum(
            int(r["n_truncated_exec"])
            for r in uniq
            if r.get("n_truncated_exec") is not None
        ),
        "mean_elapsed_sec": _mean([r.get("elapsed_sec") for r in uniq]),
        "sum_elapsed_sec": sum(
            float(r["elapsed_sec"]) for r in uniq if r.get("elapsed_sec") is not None
        ),
        "missing_field_histogram": dict(
            Counter(
                f for r in uniq for f in (r.get("missing_fields") or [])
            )
        ),
        "camera_mode_counts": dict(Counter(r.get("camera_mode") for r in uniq)),
        "simulated_gimbal_counts": dict(
            Counter(r.get("simulated_gimbal") for r in uniq)
        ),
        "executor_version_counts": dict(
            Counter(r.get("executor_version") for r in uniq)
        ),
        "goal_height_bin": "unknown",
        "occlusion_bin": "unknown",
        "multi_instance_ambiguity": "unknown",
        "spl": "N/A",
        "invalid_spawn_ids": [e.get("id") for e in invalid_rows],
        "pending_ids": [e.get("id") for e in pending_rows],
    }

    # per-category near_goal vs SR
    by_cat = defaultdict(list)
    for r in uniq:
        by_cat[str(r.get("category"))].append(r)
    per_cat = []
    for cat in sorted(by_cat):
        xs = by_cat[cat]
        scored = [x for x in xs if x.get("sr_proxy") is not None]
        s = sum(1 for x in scored if x.get("sr_proxy") is True)
        n = len(scored)
        p, lo, hi = wilson_ci(s, n)
        per_cat.append(
            {
                "category": cat,
                "n": len(xs),
                "success": s,
                "n_scored": n,
                "sr_proxy": p,
                "sr_wilson95": [lo, hi],
                "near_goal_true": sum(1 for x in xs if x.get("near_goal") is True),
                "fail_bucket_counts": dict(Counter(x.get("fail_bucket") for x in xs)),
                "mean_sum_moved_m": _mean([x.get("sum_moved_m") for x in xs]),
                "mean_elapsed_sec": _mean([x.get("elapsed_sec") for x in xs]),
            }
        )

    return {
        "summary_metrics": base,
        "accounting": accounting,
        "by_category_detail": per_cat,
        "notes": [
            "SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.",
            "Invalid spawn counted from validity table, not from SR filter.",
            "SPL=N/A without footprint-matched geodesic.",
            "Observation height / occlusion / instance ambiguity = unknown without evidence.",
            "Cup / active-arm strategy not in this freeze.",
        ],
    }


def to_markdown(doc: dict) -> str:
    a = doc["accounting"]
    sm = doc["summary_metrics"]
    lines = [
        "# Formal independent eval — accounting",
        "",
        f"- list original: {a.get('n_list_original')}",
        f"- validity: {a.get('validity_status_counts')}",
        f"- ingested unique: {a.get('n_unique_episode_ids')} / rows {a.get('n_rows_ingested')}",
        f"- micro SR_proxy: {sm.get('micro_sr')} (n_scored={sm.get('n_scored')}, wilson={sm.get('micro_sr_wilson95')})",
        f"- macro SR_proxy: {sm.get('macro_sr')}",
        f"- near_goal true: {a.get('n_near_goal_true')} (reported separately)",
        f"- wrong_stop / no_search / stalled / budget: "
        f"{a.get('n_wrong_stop')} / {a.get('n_no_search')} / {a.get('n_exec_stalled')} / {a.get('n_budget_exhausted')}",
        f"- blocked/truncated exec sum: {a.get('sum_blocked_exec')} / {a.get('sum_truncated_exec')}",
        f"- mean moved_m / steps / elapsed_s: {a.get('mean_sum_moved_m')} / {a.get('mean_n_steps')} / {a.get('mean_elapsed_sec')}",
        f"- camera_mode / simulated_gimbal / executor: "
        f"{a.get('camera_mode_counts')} / {a.get('simulated_gimbal_counts')} / {a.get('executor_version_counts')}",
        f"- missing fields: {a.get('missing_field_histogram')}",
        f"- SPL: {a.get('spl')}; height/occlusion/ambiguity: unknown",
        "",
        "## Per category",
        "",
        "| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |",
        "|---|---:|---:|---|---:|---|",
    ]
    for c in doc["by_category_detail"]:
        lines.append(
            f"| {c['category']} | {c['success']}/{c['n_scored']} | {c['sr_proxy']:.4f} | "
            f"{c['sr_wilson95']} | {c['near_goal_true']} | {c['fail_bucket_counts']} |"
        )
    lines.append("")
    lines.append("## Notes")
    for n in doc["notes"]:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--validity", type=Path, default=None)
    ap.add_argument("--out_json", type=Path, required=True)
    ap.add_argument("--out_md", type=Path, default=None)
    args = ap.parse_args()
    rows = _reingest_rows(_load_jsonl(args.jsonl))
    validity = None
    if args.validity and args.validity.is_file():
        validity = json.loads(args.validity.read_text())
    doc = build(rows, validity)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(doc, indent=2) + "\n")
    md_path = args.out_md or args.out_json.with_suffix(".md")
    md_path.write_text(to_markdown(doc))
    print(f"wrote {args.out_json} and {md_path} n={doc['accounting']['n_unique_episode_ids']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
