#!/usr/bin/env python3
"""Per-run answers for NoFrontierLook pairing (4 questions + delayed STOP / budget)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _load_jsonl(path: Path):
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def analyze(run_dir: Path, enable: bool) -> dict:
    summary = {}
    sp = run_dir / "summary.json"
    if sp.is_file():
        summary = json.loads(sp.read_text())
    steps = _load_jsonl(run_dir / "steps.jsonl")
    actions = _load_jsonl(run_dir / "actions.jsonl")
    elog = run_dir / "launch_logs" / "exploration.log"
    elog_text = elog.read_text(errors="replace") if elog.is_file() else ""

    look_hits = re.findall(
        r"\[NoFrontierLook\]\s+(\d+)/(\d+).*action=(\d+)", elog_text
    )
    n_look_steps = len(look_hits)
    finish_transit = "from PLAN_ACTION to FINISH" in elog_text
    no_frontier_warn = "No (passable) frontier" in elog_text

    # New frontier after look: EXPLORATION/SEARCH after first NO_* in plan history
    plan_seq = []
    for s in steps:
        er = s.get("expl_result")
        if er is not None:
            plan_seq.append((s.get("step"), er, s.get("planner_action_name")))

    first_nf_step = None
    recovered_frontier = False
    move_after_look = False
    for step, er, aname in plan_seq:
        # 4=NO_PASSABLE 5=NO_COVERABLE (Habitat-side published expl_result)
        if er in (4, 5) and first_nf_step is None:
            first_nf_step = step
            continue
        if first_nf_step is not None and step > first_nf_step:
            if er in (6, 1) or (isinstance(er, int) and er not in (4, 5, 3)):
                # 1 SEARCH_BEST in some schemas; 6 EXPLORATION — also check action names
                recovered_frontier = True
            if aname == "MOVE_FORWARD":
                move_after_look = True

    # Chassis effective move after first NO_FRONTIER trigger
    moved_after = 0.0
    if first_nf_step is not None:
        pre = None
        for s in steps:
            if s.get("step") == first_nf_step:
                pre = s.get("base") or {}
            if pre and s.get("step") is not None and s["step"] > first_nf_step:
                b = s.get("base") or {}
                if "x" in b and "x" in pre:
                    dx = float(b["x"]) - float(pre["x"])
                    dz = float(b.get("z", 0)) - float(pre.get("z", 0))
                    moved_after = max(moved_after, (dx * dx + dz * dz) ** 0.5)

    dtg = summary.get("final_distance_to_goal_eval_only")
    if dtg is None and steps:
        dtg = steps[-1].get("distance_to_goal_eval_only")
    term = summary.get("termination")
    success = bool(summary.get("success_claimed")) or (
        term == "planner_stop" and dtg is not None and float(dtg) <= 1.0
        and summary.get("spawn_status") == "ok"
        and float(summary.get("sum_moved_m") or 0) > 0.05
    )
    delayed_stop = bool(enable and n_look_steps > 0 and term == "planner_stop" and not success)
    budget_exhausted = term in ("max_steps", "budget", "explore_budget") or (
        str(term).endswith("budget") if term else False
    )
    if not budget_exhausted and summary.get("effective_budget"):
        eb = summary["effective_budget"]
        # heuristic: hit max explore without planner_stop success
        if term and "budget" in str(term).lower():
            budget_exhausted = True
        if (
            int(summary.get("n_explore_planner_actions") or 0)
            >= int(eb.get("max_explore_actions") or 100)
            and term != "planner_stop"
        ):
            budget_exhausted = True

    # OFF path reproduction markers
    off_path_ok = (not enable) and no_frontier_warn and finish_transit and n_look_steps == 0
    on_entered_look = bool(enable and n_look_steps > 0)

    return {
        "run_dir": str(run_dir),
        "enable_no_frontier_look": enable,
        "look_steps": n_look_steps,
        "look_hits_tail": look_hits[-5:],
        "new_usable_frontier": recovered_frontier,
        "chassis_resumed_effective_move": bool(move_after_look or moved_after >= 0.2),
        "moved_m_after_first_nf": round(moved_after, 4),
        "true_objectnav_success": bool(success),
        "delayed_stop": delayed_stop,
        "budget_exhausted": budget_exhausted,
        "termination": term,
        "final_dtg": dtg,
        "sum_moved_m": summary.get("sum_moved_m"),
        "spawn_status": summary.get("spawn_status"),
        "off_reproduced_nf_finish_stop": off_path_ok,
        "on_entered_lookaround": on_entered_look,
        "first_nf_step": first_nf_step,
        "n_actions": len(actions),
        "answers": {
            "补视步数": n_look_steps,
            "新可用frontier": recovered_frontier,
            "底盘恢复有效移动": bool(move_after_look or moved_after >= 0.2),
            "真正寻物成功": bool(success),
            "延迟STOP": delayed_stop,
            "预算耗尽": budget_exhausted,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--enable", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    enable = str(args.enable).lower() in ("1", "true", "yes", "on")
    rep = analyze(Path(args.run_dir), enable)
    Path(args.out).write_text(json.dumps(rep, indent=2, ensure_ascii=False))
    print(json.dumps(rep["answers"], ensure_ascii=False))


if __name__ == "__main__":
    main()
