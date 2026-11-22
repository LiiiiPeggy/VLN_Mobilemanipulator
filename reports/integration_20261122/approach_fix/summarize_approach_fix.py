#!/usr/bin/env python3
"""Summarize approach_fix paired runs + reused joint4 OFF baselines."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REPORT = Path(__file__).resolve().parent
JOINT4_G3_HY1 = Path(
    "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/"
    "joint4_20261122_164956/joint4_20261122_164956_g3_hy1_legacy_on"
)
JOINT4_G3_DD4B = Path(
    "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/"
    "joint4_20261122_164956/joint4_20261122_164956_g3_dd4b_legacy_on"
)


def recovery_stats(out: Path) -> dict:
    attempts = executed_ok = blocked = 0
    ff_try = ff_exec = ff_moved = 0
    opp = 0
    reasons: Counter = Counter()
    steps_path = out / "steps.jsonl"
    if not steps_path.exists():
        return {}
    with steps_path.open() as f:
        for line in f:
            s = json.loads(line)
            ex = s.get("exec") or {}
            rec = ex.get("blocked_recovery")
            if rec:
                attempts += 1
                kind = rec.get("recovery_kind") or ""
                if "forced_forward" in kind:
                    ff_try += 1
                if "opposite_turn" in kind:
                    opp += 1
                if ex.get("blocked") and not ex.get("truncated") and not ex.get("executed"):
                    blocked += 1
                else:
                    executed_ok += 1
                if "forced_forward" in kind:
                    if not (ex.get("blocked") and not ex.get("executed") and not ex.get("truncated")):
                        ff_exec += 1
                    moved = ex.get("moved_m")
                    if moved is None:
                        moved = ex.get("translation_m")
                    if moved and float(moved) > 1e-6 and not ex.get("blocked"):
                        ff_moved += 1
                    elif (
                        not ex.get("blocked")
                        and ex.get("executed")
                        and "MOVE_FORWARD" in str(ex.get("actual_action") or "")
                    ):
                        ff_moved += 1
            br = ex.get("block_reason")
            if br:
                reasons[br] += 1
    return {
        "recovery_attempts": attempts,
        "recovery_executed_ok": executed_ok,
        "recovery_blocked": blocked,
        "opposite_turn_attempts": opp,
        "forced_forward_attempts": ff_try,
        "forced_forward_executed": ff_exec,
        "forced_forward_moved": ff_moved,
        "block_reasons": dict(reasons),
    }


def objecthold_events(out: Path) -> dict:
    log = out / "launch_logs" / "exploration.log"
    if not log.exists():
        return {"keep": 0, "drop": 0, "search_nav": 0, "reach": 0}
    text = re.sub(r"\x1b\[[0-9;]*m", "", log.read_text(errors="replace"))
    return {
        "keep": len(re.findall(r"\[ObjectHold\].*keep last", text)),
        "drop": len(re.findall(r"\[ObjectHold\].*drop hold", text)),
        "search_nav": len(re.findall(r"Navigation Mode", text)),
        "reach": len(re.findall(r"Reach the object successfully", text)),
        "max_dist_boot": (
            re.findall(r"\[ObjectHold\] max_dist=([0-9.]+)m", text)[:1] or [None]
        )[0],
    }


def row_from_run(tag: str, out: Path, *, hold: float, profile: str, recovery: str, reused: bool) -> dict:
    s = json.loads((out / "summary.json").read_text())
    dtg = s.get("final_distance_to_goal_eval_only")
    term = s.get("termination")
    near = bool(s.get("near_goal"))
    stop_src = None
    if term == "planner_stop":
        stop_src = "planner_STOP"
    elif term == "explore_budget_exhausted":
        stop_src = "budget"
    rs = recovery_stats(out)
    oh = objecthold_events(out)
    # STOP action evidence
    n_stop = 0
    with (out / "steps.jsonl").open() as f:
        for line in f:
            st = json.loads(line)
            if st.get("planner_action_name") == "STOP" or (st.get("exec") or {}).get("actual_action") == "STOP":
                n_stop += 1
    return {
        "tag": tag,
        "task": tag.split("_")[0] if not tag.startswith("tee") else "tee_chair4",
        "fix_on": hold >= 7.9,
        "object_hold_max_dist": hold,
        "profile": profile,
        "recovery": recovery,
        "reused": reused,
        "valid": s.get("spawn_status") == "ok" and s.get("status") in (None, "ok", "completed", "done") or True,
        "spawn_status": s.get("spawn_status"),
        "termination": term,
        "stop_source": stop_src,
        "n_stop_actions": n_stop,
        "success_claimed": s.get("success_claimed"),
        "sr_proxy": bool(term == "planner_stop" and near),
        "near_goal": near,
        "dtg": dtg,
        "sum_moved_m": s.get("sum_moved_m"),
        "n_blocked_exec": s.get("n_blocked_exec"),
        "n_truncated_exec": s.get("n_truncated_exec"),
        "n_blocked_recovery": s.get("n_blocked_recovery"),
        "out": str(out),
        **{f"rec_{k}": v for k, v in rs.items() if k != "block_reasons"},
        "top_block_reasons": dict(Counter(rs.get("block_reasons") or {}).most_common(3)),
        "oh_keep": oh["keep"],
        "oh_drop": oh["drop"],
        "oh_search_nav": oh["search_nav"],
        "oh_reach": oh["reach"],
        "oh_max_dist_boot": oh["max_dist_boot"],
    }


def main() -> None:
    latest = (REPORT / "latest_batch_id.txt").read_text().strip() if (REPORT / "latest_batch_id.txt").exists() else None
    # also glob
    batches = sorted(REPORT.glob("results_approach_fix_*"))
    if not batches and latest:
        batches = [REPORT / f"results_{latest}"]
    if not batches:
        raise SystemExit("no results dir")
    res_dir = batches[-1]
    batch_id = res_dir.name.replace("results_", "")
    rows = []
    # reused OFF
    rows.append(
        row_from_run(
            "hy1_hold3_off",
            JOINT4_G3_HY1,
            hold=3.0,
            profile="legacy018",
            recovery="v2",
            reused=True,
        )
    )
    rows.append(
        row_from_run(
            "dd4b_hold3_off",
            JOINT4_G3_DD4B,
            hold=3.0,
            profile="legacy018",
            recovery="v2",
            reused=True,
        )
    )
    jsonl = res_dir / f"batch_{batch_id}.jsonl"
    if jsonl.exists():
        for line in jsonl.read_text().splitlines():
            if not line.strip():
                continue
            meta = json.loads(line)
            if meta.get("skipped"):
                rows.append(
                    {
                        "tag": meta["tag"],
                        "task": "tee_chair4",
                        "fix_on": True,
                        "skipped": True,
                        "reason": meta.get("reason"),
                    }
                )
                continue
            out = Path(meta["out"])
            if not (out / "summary.json").exists():
                continue
            rows.append(
                row_from_run(
                    meta["tag"],
                    out,
                    hold=float(meta.get("object_hold_max_dist") or 3.0),
                    profile=meta.get("profile") or "legacy018",
                    recovery=meta.get("recovery") or "legacy",
                    reused=False,
                )
            )

    out_json = res_dir / "PAIR_TABLE.json"
    out_json.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    md = [
        f"# Approach-fix pairing table (`{batch_id}`)",
        "",
        "Unique variable: `OBJECT_HOLD_MAX_DIST` (3.0 OFF vs 8.0 ON). "
        "Fixed within each pair: spawn, budget, inflation, recovery, nf_look=OFF, no PPO.",
        "",
        "## FF_* units",
        "- Counted per **recovery event** in `steps.jsonl` where `exec.blocked_recovery` is set.",
        "- `FF_try`: recovery_kind contains `forced_forward`.",
        "- `FF_exec`: that recovery step not fully blocked.",
        "- `FF_moved`: forward displacement recorded / successful MOVE_FORWARD actual.",
        "",
        "| task | fix | hold | profile | recovery | valid | term | STOP | sr_proxy | claimed | dtg | moved | blk/trunc | rec_try/ok | FF_try/exec/moved | OH keep/drop | reused |",
        "|------|-----|------|---------|----------|-------|------|------|----------|---------|-----|-------|-----------|------------|-------------------|--------------|--------|",
    ]
    for r in rows:
        if r.get("skipped"):
            md.append(
                f"| {r.get('task')} | ON | — | — | — | skipped | — | — | — | — | — | — | — | — | — | — | {r.get('reason')} |"
            )
            continue
        md.append(
            "| {task} | {fix} | {hold} | {profile} | {recovery} | {valid} | {term} | {stop} | {sr} | {claimed} | {dtg} | {moved} | {bt} | {rec} | {ff} | {oh} | {reu} |".format(
                task=r.get("task"),
                fix="ON" if r.get("fix_on") else "OFF",
                hold=r.get("object_hold_max_dist"),
                profile=r.get("profile"),
                recovery=r.get("recovery"),
                valid=r.get("spawn_status"),
                term=r.get("termination"),
                stop=r.get("stop_source"),
                sr=r.get("sr_proxy"),
                claimed=r.get("success_claimed"),
                dtg=None if r.get("dtg") is None else round(float(r["dtg"]), 3),
                moved=None if r.get("sum_moved_m") is None else round(float(r["sum_moved_m"]), 3),
                bt=f"{r.get('n_blocked_exec')}/{r.get('n_truncated_exec')}",
                rec=f"{r.get('rec_recovery_attempts')}/{r.get('rec_recovery_executed_ok')}",
                ff=f"{r.get('rec_forced_forward_attempts')}/{r.get('rec_forced_forward_executed')}/{r.get('rec_forced_forward_moved')}",
                oh=f"{r.get('oh_keep')}/{r.get('oh_drop')}",
                reu=r.get("reused"),
            )
        )
    (res_dir / "PAIR_TABLE.md").write_text("\n".join(md) + "\n")
    print(f"wrote {out_json} and PAIR_TABLE.md n={len(rows)}")


if __name__ == "__main__":
    main()
