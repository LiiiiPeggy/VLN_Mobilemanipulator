#!/usr/bin/env python3
# ################################
# VLN adapt: archive distinct protocol batches; merge recovery without double-count
# ################################
"""Separate:
  - hist_labelmap_vp_8of24 (pre-fix diagnostic)
  - short50_exec_v1_0of24 (MAX_STEPS≈50 fixed_base_gimbal)
  - recovery / fix batches linked by episode_list_id

Does not treat historical tv/plant failure mix as causal for the new executor.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from ingest_episode_run import ingest_run  # noqa: E402
from summarize_category_metrics import summarize  # noqa: E402
from wilson_ci import wilson_ci  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
REP = ROOT / "reports/ranger_category_eval_20261116"
ARCH = REP / "archives"
EXEC_REP = ROOT / "reports/exec_collision_gimbal_20261116"
RUN_ROOT = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real")
DEV24 = ROOT / "reports/startup_prior_e2e_20261107/episode_list.json"
HIST_DIAG = REP / "tables/dev24_category_diag.json"


def _load_jsonl(path: Path):
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _ingest_batch(batch_jsonl: Path, archive_role: str, recovery: bool = False):
    rows = []
    for rec in _load_jsonl(batch_jsonl):
        eid = rec.get("episode_list_id")
        run_id = rec.get("run_id")
        run_dir = RUN_ROOT / run_id if run_id else None
        if run_dir and run_dir.is_dir():
            row = ingest_run(
                run_dir,
                episode_list_id=eid,
                batch_id=rec.get("batch_id"),
                recovery_of=rec.get("batch_id") if recovery else None,
            )
        else:
            # keep shell-level status; do not invent metrics
            row = {
                "episode_list_id": eid,
                "batch_id": rec.get("batch_id"),
                "run_id": run_id,
                "run_dir": str(run_dir) if run_dir else None,
                "run_status": rec.get("status") or "missing_run_dir",
                "sr_proxy": None,
                "near_goal": rec.get("near_goal"),
                "missing_fields": ["summary.json"],
                "camera_mode": rec.get("camera_mode"),
                "executor_version": rec.get("executor_version_run") or rec.get("executor_version"),
                "robot_scale": rec.get("robot_scale"),
                "category": rec.get("category"),
                "scene": rec.get("scene"),
                "episode_id": rec.get("episode_id"),
                "termination": rec.get("termination"),
                "sum_moved_m": rec.get("sum_moved_m"),
                "initial_penetration": rec.get("initial_penetration"),
                "n_steps_observed": rec.get("n_steps"),
                "n_explore_observed": rec.get("n_explore"),
                "n_blocked_exec": rec.get("n_blocked_exec"),
                "n_truncated_exec": rec.get("n_truncated_exec"),
                "spl": "N/A",
            }
        row["archive_role"] = archive_role
        row["scene"] = row.get("scene") or rec.get("scene")
        row["category"] = row.get("category") or rec.get("category")
        row["episode_id"] = row.get("episode_id") or rec.get("episode_id")
        row["shell_rc"] = rec.get("rc")
        row["recovery_flag"] = bool(recovery or rec.get("recovery"))
        # outer script constants are informational only
        row["shell_claimed_executor_version"] = rec.get("executor_version")
        row["shell_claimed_camera_mode"] = rec.get("camera_mode")
        rows.append(row)
    return rows


def _merge_primary_and_recovery(primary, recovery):
    """One row per episode_list_id: prefer latest recovery ok over missing_summary."""
    by_id = {}
    lineage = defaultdict(list)
    for r in primary:
        eid = r["episode_list_id"]
        by_id[eid] = r
        lineage[eid].append({"batch_id": r.get("batch_id"), "run_id": r.get("run_id"), "role": "primary"})
    for r in recovery:
        eid = r["episode_list_id"]
        lineage[eid].append(
            {"batch_id": r.get("batch_id"), "run_id": r.get("run_id"), "role": "recovery"}
        )
        cur = by_id.get(eid)
        if cur is None:
            by_id[eid] = r
            continue
        # replace only if primary missing/failed and recovery has summary
        cur_bad = cur.get("run_status") in (
            "missing_summary",
            "missing_run_dir",
            "crash",
            "timeout",
            "unknown_status",
        )
        rec_ok = r.get("run_status") == "ok"
        if cur_bad and rec_ok:
            r = dict(r)
            r["supersedes_run_id"] = cur.get("run_id")
            r["recovery_of"] = cur.get("batch_id")
            by_id[eid] = r
        elif (not cur_bad) and rec_ok:
            # keep primary; record unused recovery
            cur.setdefault("unused_recovery_run_ids", []).append(r.get("run_id"))
    merged = [by_id[k] for k in sorted(by_id)]
    return merged, dict(lineage)


def _pair_check(rows_a, rows_b, id_key="episode_list_id"):
    a_ids = [r[id_key] for r in rows_a]
    b_ids = [r[id_key] for r in rows_b]
    dup_a = [i for i, c in Counter(a_ids).items() if c > 1]
    dup_b = [i for i, c in Counter(b_ids).items() if c > 1]
    sa, sb = set(a_ids), set(b_ids)
    return {
        "duplicate_ids_a": dup_a,
        "duplicate_ids_b": dup_b,
        "missing_in_b": sorted(sa - sb),
        "missing_in_a": sorted(sb - sa),
        "n_paired": len(sa & sb),
        "config_mismatches": _config_mismatches(rows_a, rows_b, sa & sb, id_key),
    }


def _config_mismatches(rows_a, rows_b, ids, id_key):
    ma = {r[id_key]: r for r in rows_a}
    mb = {r[id_key]: r for r in rows_b}
    bad = []
    keys = ("camera_mode", "robot_scale", "executor_version")
    for i in sorted(ids):
        diffs = {}
        for k in keys:
            va, vb = ma[i].get(k), mb[i].get(k)
            if va is not None and vb is not None and va != vb:
                diffs[k] = {"a": va, "b": vb}
        if diffs:
            bad.append({"episode_list_id": i, "diffs": diffs})
    return bad


def _near_goal_table(rows):
    """Only rows with near_goal is True; do not call zero-move 'successful approach'."""
    out = []
    for r in rows:
        if r.get("near_goal") is not True:
            continue
        moved = r.get("sum_moved_m")
        interpretation = None
        if moved is None:
            interpretation = "moved_unknown"
        elif float(moved) == 0.0:
            interpretation = "spawn_or_static_near_goal_not_an_approach"
        else:
            interpretation = "translated_while_ending_near_goal"
        out.append(
            {
                "episode_list_id": r.get("episode_list_id"),
                "run_id": r.get("run_id"),
                "category": r.get("category"),
                "dtg_initial": r.get("dtg_initial"),
                "dtg_final": r.get("dtg_final"),
                "dtg_min": r.get("dtg_min"),
                "sum_moved_m": moved,
                "entered_search_best": r.get("entered_search_best"),
                "entered_search_any": r.get("entered_search_any"),
                "has_stop_action": r.get("has_stop_action"),
                "termination": r.get("termination"),
                "initial_penetration": r.get("initial_penetration"),
                "sr_proxy": r.get("sr_proxy"),
                "interpretation": interpretation,
            }
        )
    return out


def main() -> int:
    ARCH.mkdir(parents=True, exist_ok=True)
    tables = REP / "tables"
    tables.mkdir(parents=True, exist_ok=True)

    # --- Archive A: historical LabelMap VIEW_POINTS diagnostic ---
    hist = json.loads(HIST_DIAG.read_text()) if HIST_DIAG.is_file() else {}
    hist_doc = {
        "archive_id": "hist_labelmap_vp_recompute_20261109",
        "role": "development_diagnosis_only",
        "not_for_new_protocol_failure_attribution": True,
        "note": (
            "Pre-fix 8/24 VIEW_POINTS recompute. May include penetration. "
            "tv/plant failure mix MUST NOT be used as primary causal attribution "
            "for kinematic_collision_v1.1 / fixed_base_gimbal."
        ),
        "micro_sr_proxy": hist.get("sr_proxy_viewpoint_micro"),
        "n": hist.get("n"),
        "success": hist.get("success"),
        "source": str(HIST_DIAG),
    }
    (ARCH / "00_hist_labelmap_vp_8of24.json").write_text(json.dumps(hist_doc, indent=2) + "\n")

    # --- Archive B: short-budget 50-step primary + recovery merge ---
    primary = _ingest_batch(
        EXEC_REP / "batch_ab24b_20261116_224229.jsonl",
        archive_role="short50_primary",
        recovery=False,
    )
    # Prefer latest completed recovery jsonl
    rec_files = sorted(EXEC_REP.glob("batch_ab24b_rec_*.jsonl"))
    recovery = (
        _ingest_batch(rec_files[-1], archive_role="short50_recovery", recovery=True)
        if rec_files
        else []
    )
    merged, lineage = _merge_primary_and_recovery(primary, recovery)

    # Also ingest earlier incomplete ab24 for reference only
    early = _ingest_batch(
        EXEC_REP / "batch_ab24_20261116_221752.jsonl",
        archive_role="short50_early_incomplete",
        recovery=False,
    )

    short_doc = {
        "archive_id": "short50_fixed_base_gimbal_20261116",
        "role": "new_executor_short_budget",
        "camera_mode_required": "fixed_base_gimbal",
        "budget_note": "Shell used MAX_STEPS=50; max_steps_config often missing in summary — see missing_fields.",
        "primary_batch": "ab24b_20261116_224229",
        "recovery_batch": rec_files[-1].name if rec_files else None,
        "n_primary": len(primary),
        "n_recovery_rows": len(recovery),
        "n_merged": len(merged),
        "lineage": lineage,
        "pair_check_primary_vs_recovery": _pair_check(primary, recovery) if recovery else None,
        "episodes": merged,
        "early_incomplete_not_in_merge": early,
    }
    (ARCH / "01_short50_exec_gimbal.json").write_text(json.dumps(short_doc, indent=2) + "\n")
    (tables / "short50_merged_episodes.json").write_text(
        json.dumps({"episodes": merged, "lineage": lineage}, indent=2) + "\n"
    )

    # metrics with null-safe success
    scored = [r for r in merged if r.get("run_status") == "ok" and r.get("sr_proxy") is not None]
    metrics = summarize(scored) if scored else {"n": 0, "success": 0, "micro_sr": None}
    accounting = {
        "n_list": 24,
        "n_merged": len(merged),
        "run_status": dict(Counter(r.get("run_status") for r in merged)),
        "spawn_status": dict(Counter(r.get("spawn_status") for r in merged)),
        "fail_bucket": dict(Counter(r.get("fail_bucket") for r in merged)),
        "n_sr_true": sum(1 for r in merged if r.get("sr_proxy") is True),
        "n_sr_false": sum(1 for r in merged if r.get("sr_proxy") is False),
        "n_sr_unknown": sum(1 for r in merged if r.get("sr_proxy") is None),
        "n_near_goal": sum(1 for r in merged if r.get("near_goal") is True),
        "n_initial_penetration": sum(1 for r in merged if r.get("initial_penetration") is True),
        "n_missing_summary_unrecovered": sum(
            1 for r in merged if r.get("run_status") == "missing_summary"
        ),
        "sum_moved_m_known": sum(
            float(r["sum_moved_m"]) for r in merged if r.get("sum_moved_m") is not None
        ),
        "sum_blocked_known": sum(
            int(r["n_blocked_exec"]) for r in merged if r.get("n_blocked_exec") is not None
        ),
        "sum_truncated_known": sum(
            int(r["n_truncated_exec"]) for r in merged if r.get("n_truncated_exec") is not None
        ),
        "metrics_on_scored_ok_rows": metrics,
        "note": "Do not equate near_goal with approach success; zero moved_m near_goal ≠ successful approach.",
    }
    (tables / "short50_accounting.json").write_text(json.dumps(accounting, indent=2) + "\n")

    ng = _near_goal_table(merged)
    (tables / "near_goal_5_detail.json").write_text(json.dumps({"n": len(ng), "rows": ng}, indent=2) + "\n")
    # markdown
    lines = [
        "# near_goal 明细（短预算 fixed_base_gimbal 合并集）",
        "",
        "定义：`near_goal` = 最终 VIEW_POINTS 距 ≤ 1.0 m。**不等于** SR_proxy，**不等于**成功接近。",
        "",
        "| ep | dtg_init | dtg_final | dtg_min | moved_m | SEARCH_BEST | STOP | init_pen | term | 解释 |",
        "|----|---------:|----------:|--------:|--------:|:-----------:|:----:|:--------:|------|------|",
    ]
    for r in ng:
        lines.append(
            f"| {r['episode_list_id']} | {r['dtg_initial']} | {r['dtg_final']} | {r['dtg_min']} | "
            f"{r['sum_moved_m']} | {r['entered_search_best']} | {r['has_stop_action']} | "
            f"{r['initial_penetration']} | {r['termination']} | {r['interpretation']} |"
        )
    zero_move = sum(1 for r in ng if r.get("sum_moved_m") == 0.0)
    lines += [
        "",
        f"其中 `moved_m==0`：**{zero_move}** / {len(ng)} — **禁止**表述为「成功接近但未停止」。",
        "",
    ]
    (tables / "near_goal_5_detail.md").write_text("\n".join(lines) + "\n")

    # short category table (scored only)
    by_cat = defaultdict(list)
    for r in scored:
        by_cat[str(r.get("category"))].append(r)
    cat_lines = [
        "# 短预算批逐类（仅 run_status=ok 且 sr_proxy 已知）",
        "",
        "与历史 8/24 **不可因果对比**。观测分层均为 unknown。",
        "",
        "| category | n | success | SR_proxy | Wilson95 | wrong_stop | no_SEARCH_BEST | budget_exh | stalled |",
        "|----------|--:|--------:|---------:|----------|-----------:|---------------:|-----------:|--------:|",
    ]
    for cat in sorted(by_cat):
        xs = by_cat[cat]
        s = sum(1 for x in xs if x.get("sr_proxy") is True)
        n = len(xs)
        p, lo, hi = wilson_ci(s, n)
        fb = Counter(x.get("fail_bucket") for x in xs)
        cat_lines.append(
            f"| {cat} | {n} | {s} | {p:.3f} | [{lo:.3f},{hi:.3f}] | "
            f"{fb.get('wrong_stop',0)} | {fb.get('no_search_best',0)} | "
            f"{fb.get('budget_exhausted',0)} | {fb.get('exec_stalled',0)} |"
        )
    if scored:
        s = sum(1 for x in scored if x.get("sr_proxy") is True)
        n = len(scored)
        p, lo, hi = wilson_ci(s, n)
        cat_lines.append(f"| __micro__ | {n} | {s} | {p:.3f} | [{lo:.3f},{hi:.3f}] |  |  |  |  |")
    (tables / "short50_by_category.md").write_text("\n".join(cat_lines) + "\n")

    print(f"merged={len(merged)} near_goal={len(ng)} scored={len(scored)} sr_true={accounting['n_sr_true']}")
    print("wrote", ARCH, tables / "near_goal_5_detail.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
