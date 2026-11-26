#!/usr/bin/env python3
# ################################
# VLN adapt: ingest one ApexNav Ranger run dir into a typed episode row
# ################################
"""Read summary.json + steps.jsonl + native_plan_diag; never default missing → false/0.

SR_proxy requires explicit explore-phase STOP (or termination==planner_stop with
STOP action evidence) AND final/at-STOP dtg_viewpoint ≤ success_distance.
near_goal alone is NOT success and is NOT 'approached'.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional


MISSING = None  # explicit null in JSON


def _read_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def _read_jsonl(path: Path) -> List[dict]:
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _get(d: Optional[dict], *keys, default=MISSING):
    if d is None:
        return default
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def ingest_run(
    run_dir: Path,
    *,
    episode_list_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    recovery_of: Optional[str] = None,
    success_distance: float = 1.0,
) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    summary = _read_json(run_dir / "summary.json")
    steps = _read_jsonl(run_dir / "steps.jsonl")
    plans = _read_jsonl(run_dir / "native_diag" / "native_plan_diag.jsonl")
    cam = _read_json(run_dir / "camera_mode.json")
    init_pen = _read_json(run_dir / "initial_penetration.json")
    if init_pen is None and summary:
        init_pen = summary.get("initial_penetration")

    status = _get(summary, "status")
    if summary is None:
        run_status = "missing_summary"
    elif status == "ok":
        run_status = "ok"
    elif status in ("timeout", "crash", "abort"):
        run_status = status
    elif status is MISSING or status is None:
        run_status = "unknown_status"
    else:
        run_status = str(status)
    # ################################
    # VLN adapt: n_steps==0 with status=ok is not a scored success path
    # (e.g. ROS conflict / early cleanup). Keep summary fields; demote run_status.
    # ################################
    n_steps_probe = _get(summary, "n_steps")
    if (
        run_status == "ok"
        and n_steps_probe is not MISSING
        and n_steps_probe is not None
        and int(n_steps_probe) == 0
        and len(steps) == 0
    ):
        run_status = "empty_run"

    # distances from steps (eval-only; primary = camera→VIEW_POINT 3D)
    dtgs = [
        float(st["distance_to_goal_eval_only"])
        for st in steps
        if st.get("distance_to_goal_eval_only") is not None
    ]
    dtg_initial = dtgs[0] if dtgs else MISSING
    dtg_final = dtgs[-1] if dtgs else _get(summary, "final_distance_to_goal_eval_only")
    dtg_min = min(dtgs) if dtgs else MISSING

    # translation: sum exec.moved_m when present; else null (do not coerce to 0)
    moved_vals = []
    for st in steps:
        ex = st.get("exec") or {}
        if "moved_m" in ex and ex["moved_m"] is not None:
            moved_vals.append(float(ex["moved_m"]))
    sum_moved_m = sum(moved_vals) if moved_vals else MISSING

    blocked = trunc = MISSING
    if steps:
        blocked = sum(1 for st in steps if (st.get("exec") or {}).get("blocked") is True)
        trunc = sum(1 for st in steps if (st.get("exec") or {}).get("truncated") is True)

    # STOP evidence: actual action name / raw_action==0, not step-index heuristics
    stop_steps = []
    for st in steps:
        ex = st.get("exec") or {}
        name = ex.get("action_name") or st.get("planner_action_name")
        raw = ex.get("raw_action")
        if name == "STOP" or raw == 0:
            stop_steps.append(
                {
                    "step": st.get("step"),
                    "phase": st.get("phase"),
                    "dtg": st.get("distance_to_goal_eval_only"),
                }
            )
    has_stop_action = True if stop_steps else (False if steps else MISSING)
    term = _get(summary, "termination")

    # SEARCH from native plan diag results
    plan_results = [p.get("result") for p in plans if p.get("result") is not None]
    n_search_best = sum(1 for r in plan_results if r == "SEARCH_BEST_OBJECT")
    n_search_any = sum(1 for r in plan_results if isinstance(r, str) and r.startswith("SEARCH"))
    entered_search_best = True if n_search_best > 0 else (False if plans else MISSING)
    entered_search_any = True if n_search_any > 0 else (False if plans else MISSING)

    # SR_proxy: STOP with dtg≤thr. Prefer dtg at STOP step (camera→VIEW_POINT 3D
    # when run used DIST_CAMERA_VIEW_POINTS_3D).
    sr_proxy = MISSING
    sr_dtg = MISSING
    if has_stop_action is True:
        # use last STOP with known dtg
        for rec in reversed(stop_steps):
            if rec["dtg"] is not None:
                sr_dtg = float(rec["dtg"])
                break
        if sr_dtg is not MISSING:
            sr_proxy = bool(sr_dtg <= success_distance)
        else:
            sr_proxy = MISSING
    elif has_stop_action is False:
        sr_proxy = False
    # near_goal is final_dtg≤thr only (may be spawn-near); keep separate
    near_goal = _get(summary, "near_goal")
    if near_goal is MISSING and dtg_final is not MISSING and dtg_final is not None:
        near_goal = bool(float(dtg_final) <= success_distance)

    init_pen_flag = MISSING
    if isinstance(init_pen, dict):
        if "initial_penetration" in init_pen:
            init_pen_flag = bool(init_pen["initial_penetration"])
        elif "blocking" in (init_pen.get("contacts") or {}):
            init_pen_flag = bool(init_pen["contacts"]["blocking"])

    # Prefer values written by the run itself over outer script constants
    executor_version = _get(summary, "executor_version")
    camera_mode = _get(summary, "camera_mode")
    if camera_mode is MISSING:
        camera_mode = _get(cam, "camera_mode")
    simulated_gimbal = _get(summary, "simulated_gimbal")
    if simulated_gimbal is MISSING:
        simulated_gimbal = _get(cam, "simulated_gimbal")

    # ################################
    # VLN adapt: budget/SHA only from run artifacts (incl. process_meta), never shell-only
    # ################################
    max_steps_cfg = MISSING
    max_explore_cfg = MISSING
    code_git_sha = MISSING
    for cand in (
        run_dir / "process_meta.json",
        run_dir / "run_config.json",
        run_dir / "args.json",
        run_dir / "meta.json",
    ):
        meta = _read_json(cand)
        if not meta:
            continue
        if max_steps_cfg is MISSING and meta.get("max_steps") is not None:
            max_steps_cfg = meta.get("max_steps")
        if max_explore_cfg is MISSING and meta.get("max_explore_actions") is not None:
            max_explore_cfg = meta.get("max_explore_actions")
        if code_git_sha is MISSING:
            sha = meta.get("git_sha_vln") or meta.get("code_git_sha")
            if sha:  # empty/null stays missing — do not coerce
                code_git_sha = sha
    # ################################
    # effective budget from observed steps if file incomplete
    n_steps = _get(summary, "n_steps")
    if n_steps is MISSING and steps:
        n_steps = len(steps)
    n_explore = _get(summary, "n_explore_planner_actions")
    n_init = _get(summary, "n_init_lookaround_actions")

    # ################################
    # VLN adapt: fail bucket from real termination / STOP / SEARCH / stall evidence
    # ################################
    fail_bucket = MISSING
    if run_status == "ok" and sr_proxy is False:
        if term == "step_budget_exhausted":
            fail_bucket = "budget_exhausted"
        elif term == "explore_budget_exhausted":
            fail_bucket = "explore_budget_exhausted"
        elif has_stop_action is True:
            fail_bucket = "wrong_stop"
        elif term in ("completed_without_stop", "no_stop"):
            fail_bucket = "no_stop"
        elif entered_search_best is False:
            fail_bucket = "no_search_best"
        elif sum_moved_m is not MISSING and sum_moved_m == 0.0 and blocked not in (MISSING, 0):
            fail_bucket = "exec_stalled"
        else:
            fail_bucket = "other_fail"
    elif run_status == "ok" and sr_proxy is True:
        fail_bucket = "ok_success_proxy"
    elif run_status == "empty_run":
        fail_bucket = "empty_run"
    elif run_status in ("timeout", "crash", "abort", "missing_summary"):
        fail_bucket = f"run_{run_status}"
    # ################################

    spawn_status = MISSING
    if init_pen_flag is True:
        spawn_status = "invalid_initial_penetration"
    elif init_pen_flag is False:
        spawn_status = "ok"
    # else leave null — do not invent

    row = {
        "episode_list_id": episode_list_id,
        "batch_id": batch_id,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "recovery_of": recovery_of,
        "archive_role": MISSING,  # filled by archiver
        "scene": MISSING,
        "category": MISSING,
        "episode_id": MISSING,
        "robot_scale": _get(summary, "robot_scale"),
        "scale_tag": _get(summary, "scale_tag"),
        "camera_mode": camera_mode,
        "simulated_gimbal": simulated_gimbal,
        "executor_version": executor_version,
        "code_git_sha": code_git_sha,
        "max_steps_config": max_steps_cfg,
        "max_explore_actions_config": max_explore_cfg,
        "n_steps_observed": n_steps,
        "n_init_lookaround_observed": n_init,
        "n_explore_observed": n_explore,
        "spawn_status": spawn_status,
        "run_status": run_status,
        "termination": term,
        "sr_proxy": sr_proxy,
        "sr_dtg_at_stop": sr_dtg,
        "near_goal": near_goal,
        "dtg_initial": dtg_initial,
        "dtg_final": dtg_final,
        "dtg_min": dtg_min,
        "sum_moved_m": sum_moved_m,
        "n_blocked_exec": blocked,
        "n_truncated_exec": trunc,
        "has_stop_action": has_stop_action,
        "n_stop_actions": len(stop_steps) if steps else MISSING,
        "stop_steps": stop_steps if stop_steps else MISSING,
        "entered_search_best": entered_search_best,
        "entered_search_any": entered_search_any,
        "n_search_best": n_search_best if plans else MISSING,
        "n_search_any": n_search_any if plans else MISSING,
        "initial_penetration": init_pen_flag,
        "elapsed_sec": _get(summary, "elapsed_sec"),
        "fail_bucket": fail_bucket,
        "goal_height_bin": "unknown",
        "apparent_scale_bin": "unknown",
        "occlusion_bin": "unknown",
        "multi_instance_ambiguity": "unknown",
        "spl": "N/A",
        "missing_fields": [],
    }

    # annotate missing critical fields
    for k in (
        "executor_version",
        "camera_mode",
        "simulated_gimbal",
        "code_git_sha",
        "max_steps_config",
        "max_explore_actions_config",
        "sum_moved_m",
        "entered_search_best",
        "has_stop_action",
        "dtg_min",
    ):
        if row[k] is MISSING:
            row["missing_fields"].append(k)

    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--episode_list_id")
    ap.add_argument("--batch_id")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    row = ingest_run(
        args.run_dir,
        episode_list_id=args.episode_list_id,
        batch_id=args.batch_id,
    )
    text = json.dumps(row, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
