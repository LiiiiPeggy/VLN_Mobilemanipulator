#!/usr/bin/env python3
# ################################
# VLN adapt: historical 24-ep per-category diagnostic (read-only)
# ################################
"""Build per-category diagnostic tables from LabelMap 24-ep + VIEW_POINTS recompute.

Caveat: historical execution chain may have penetration / footprint issues;
results are for development diagnosis only — not a frozen independent baseline.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
AGG = ROOT / "reports/discovery_label_map_20261108/aggregate_ab24_labelmap_20261108_220204.json"
RECOMPUTE = ROOT / "reports/stop_near_viewpoint_20261109/recompute_viewpoint_sr.json"
EP_LIST = ROOT / "reports/startup_prior_e2e_20261107/episode_list.json"
OUT_DIR = ROOT / "reports/ranger_category_eval_20261116/tables"

# Fail taxonomy used for diagnosis (mutually exclusive priority)
FAIL_BUCKETS = (
    "ok_success_proxy",
    "wrong_stop",  # planner_stop but not near VIEW_POINTS (false target / wrong instance / extreme)
    "no_search_best",  # never entered SEARCH_BEST (includes synonym-only / explore_no_goal w/o BEST)
    "explore_no_goal_after_search",  # had SEARCH_BEST but ended explore_no_goal (rare)
    "other_fail",
)


def _bucket(ep: dict) -> str:
    if ep.get("sr_proxy_viewpoint"):
        return "ok_success_proxy"
    has_best = bool(ep.get("has_search_best"))
    term = ep.get("termination") or ""
    fail = ep.get("fail_class_viewpoint") or ep.get("fail_class_recorded") or ""
    if term == "planner_stop" and not ep.get("sr_proxy_viewpoint"):
        return "wrong_stop"
    if not has_best:
        return "no_search_best"
    if fail == "explore_no_goal":
        return "explore_no_goal_after_search"
    return "other_fail"


def main() -> int:
    agg = json.loads(AGG.read_text())
    rec = json.loads(RECOMPUTE.read_text())["labelmap"]
    ep_list = {e["id"]: e for e in json.loads(EP_LIST.read_text())["episodes"]}
    by_id = {e["episode_list_id"]: e for e in rec["episodes"]}
    rows_out = []
    for r in agg["rows"]:
        eid = r["episode_list_id"]
        ep = by_id[eid]
        meta = ep_list.get(eid, {})
        bucket = _bucket(ep)
        rows_out.append(
            {
                "episode_list_id": eid,
                "scene": r.get("scene") or meta.get("scene_filter"),
                "category": r.get("category") or meta.get("category"),
                "episode_id": str(r.get("episode_id") or meta.get("episode_id")),
                "robot_scale": r.get("robot_scale", 0.7),
                "scale_tag": r.get("scale_tag", "scaled_robot_proxy_070"),
                "termination": ep.get("termination"),
                "sr_proxy_point": bool(ep.get("sr_proxy_point")),
                "sr_proxy_viewpoint": bool(ep.get("sr_proxy_viewpoint")),
                "fail_class_recorded": ep.get("fail_class_recorded"),
                "fail_class_viewpoint": ep.get("fail_class_viewpoint"),
                "fail_bucket": bucket,
                "has_label0": bool(ep.get("has_label0")),
                "has_search_best": bool(ep.get("has_search_best")),
                "n_search_best": ep.get("n_search_best"),
                "n_search_extreme": ep.get("n_search_extreme"),
                "sum_ndet": ep.get("sum_ndet"),
                "dtg_point": ep.get("dtg_point"),
                "dtg_viewpoint": ep.get("dtg_viewpoint"),
                "n_steps": ep.get("n_steps"),
                "elapsed_sec": ep.get("elapsed_sec"),
                "forward_m": r.get("forward_m"),
                "force_spawn_json": r.get("force_spawn_json") or meta.get("force_spawn_json"),
                "caveat": "historical_chain_may_penetrate; diagnostic_only",
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_path = OUT_DIR / "dev24_per_episode.csv"
    with per_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    by_cat = defaultdict(list)
    for row in rows_out:
        by_cat[row["category"]].append(row)

    summary = []
    for cat in sorted(by_cat):
        xs = by_cat[cat]
        n = len(xs)
        succ = sum(1 for x in xs if x["sr_proxy_viewpoint"])
        bc = Counter(x["fail_bucket"] for x in xs)
        summary.append(
            {
                "category": cat,
                "n": n,
                "success": succ,
                "sr_proxy": round(succ / n, 4) if n else None,
                "wrong_stop": bc.get("wrong_stop", 0),
                "no_search_best": bc.get("no_search_best", 0),
                "explore_no_goal_after_search": bc.get("explore_no_goal_after_search", 0),
                "other_fail": bc.get("other_fail", 0),
                "has_label0": sum(1 for x in xs if x["has_label0"]),
                "has_search_best": sum(1 for x in xs if x["has_search_best"]),
            }
        )

    overall_n = len(rows_out)
    overall_s = sum(1 for x in rows_out if x["sr_proxy_viewpoint"])
    summary.append(
        {
            "category": "__ALL_micro__",
            "n": overall_n,
            "success": overall_s,
            "sr_proxy": round(overall_s / overall_n, 4),
            "wrong_stop": sum(1 for x in rows_out if x["fail_bucket"] == "wrong_stop"),
            "no_search_best": sum(1 for x in rows_out if x["fail_bucket"] == "no_search_best"),
            "explore_no_goal_after_search": sum(
                1 for x in rows_out if x["fail_bucket"] == "explore_no_goal_after_search"
            ),
            "other_fail": sum(1 for x in rows_out if x["fail_bucket"] == "other_fail"),
            "has_label0": sum(1 for x in rows_out if x["has_label0"]),
            "has_search_best": sum(1 for x in rows_out if x["has_search_best"]),
        }
    )

    sum_path = OUT_DIR / "dev24_by_category.csv"
    with sum_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    md = OUT_DIR / "dev24_by_category.md"
    lines = [
        "# 历史 24 例逐类诊断（LabelMap + VIEW_POINTS 重算）",
        "",
        f"来源：`{AGG.relative_to(ROOT)}` + `{RECOMPUTE.relative_to(ROOT)}`。",
        "",
        "**免责声明**：历史执行链可能存在穿模 / 足迹与规划不一致；**仅供开发诊断**，"
        "不得作为独立测试集基线，也不得称为真实尺寸实机结果（`robot_scale=0.7`）。",
        "",
        "成功定义：`SR_proxy` = `planner_stop ∧ dtg(VIEW_POINTS) ≤ 1.0 m`；**不报 SPL**。",
        "",
        "| category | n | success | SR_proxy | wrong_stop | no_SEARCH_BEST | other | label0 | SEARCH_BEST |",
        "|----------|---|--------:|---------:|-----------:|---------------:|------:|-------:|------------:|",
    ]
    for s in summary:
        lines.append(
            f"| {s['category']} | {s['n']} | {s['success']} | {s['sr_proxy']} | "
            f"{s['wrong_stop']} | {s['no_search_best']} | "
            f"{s['explore_no_goal_after_search'] + s['other_fail']} | "
            f"{s['has_label0']} | {s['has_search_best']} |"
        )
    lines += [
        "",
        "## 失败桶说明",
        "",
        "- `wrong_stop`：已 `planner_stop` 但未到 VIEW_POINTS（含错误物体/实例、近义 EXTREME）。",
        "- `no_search_best`：从未进入 `SEARCH_BEST_OBJECT`（含仅辅助簇 / 探索未确认目标）。",
        "- 分组 `大型家具` / `小物体` 仅用于报告汇总，**不**与子类重复计入总体 micro。",
        "",
        f"逐例 CSV：`{per_path.relative_to(ROOT)}`",
        "",
    ]
    md.write_text("\n".join(lines) + "\n")

    payload = {
        "source_aggregate": str(AGG),
        "source_recompute": str(RECOMPUTE),
        "batch_id": agg.get("batch_id"),
        "sr_proxy_viewpoint_micro": overall_s / overall_n,
        "n": overall_n,
        "success": overall_s,
        "by_category": summary,
        "episodes": rows_out,
        "caveat": "historical_chain_may_penetrate; scale_0.7_proxy; diagnostic_only",
    }
    (OUT_DIR / "dev24_category_diag.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {per_path}")
    print(f"wrote {sum_path}")
    print(f"wrote {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
