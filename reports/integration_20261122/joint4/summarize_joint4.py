#!/usr/bin/env python3
# ################################
# VLN adapt: summarize joint4 batch — inflation × blocked_recovery_mode.
# ################################
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

BATCH = "joint4_20261122_164956"
ROOT = Path("/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate")
OUT_ROOT = Path(
    f"/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/{BATCH}"
)
REPORT = ROOT / f"reports/integration_20261122/joint4/results_{BATCH}"
JOBS = ROOT / "reports/integration_20261122/joint4/jobs.tsv"


def _load_json(p: Path) -> Optional[dict]:
    if not p.is_file():
        return None
    return json.loads(p.read_text())


def _effective_params(run: Path) -> Dict[str, Any]:
    p = run / "launch_logs" / "effective_params.txt"
    if not p.is_file():
        return {}
    lines = [ln.strip() for ln in p.read_text().splitlines() if ln.strip() != ""]
    # Order from run_apexnav_real_episode.sh rosparam gets:
    keys = [
        "habitat_radius",
        "obstacles_inflation",
        "lock_obstacles_inflation",
        "soft_cost_range_m",
        "soft_cost_weight",
        "optimistic",
        "depth_filter_mindist",
        "filter_min_height",
        "filter_max_height",
        "startup_prior_mode",
        "startup_prior_half_length",
        "startup_prior_half_width",
        "startup_prior_expand_m",
        "obstacle_denoise",
        "resolution",
        "enable_no_frontier_look",
    ]
    out = {}
    for i, k in enumerate(keys):
        if i < len(lines):
            out[k] = lines[i]
    return out


def _dtg(summary: dict, run: Path) -> Optional[float]:
    for k in (
        "final_distance_to_goal_eval_only",
        "final_distance_to_goal",
        "distance_to_goal",
        "dtg",
        "distance_to_goal_final",
    ):
        if summary.get(k) is not None:
            try:
                return float(summary[k])
            except Exception:
                pass
    m = summary.get("metrics") or {}
    if isinstance(m, dict):
        for k in ("distance_to_goal", "final_distance_to_goal"):
            if m.get(k) is not None:
                return float(m[k])
    steps = run / "steps.jsonl"
    if steps.is_file():
        last = None
        for line in steps.read_text().splitlines():
            if line.strip():
                last = json.loads(line)
        if last:
            for path in (
                ("distance_to_goal",),
                ("dtg",),
                ("metrics", "distance_to_goal"),
                ("exec", "distance_to_goal"),
            ):
                cur: Any = last
                ok = True
                for k in path:
                    if not isinstance(cur, dict) or k not in cur:
                        ok = False
                        break
                    cur = cur[k]
                if ok and cur is not None:
                    try:
                        return float(cur)
                    except Exception:
                        pass
    return None


def _forward_m(run: Path) -> float:
    """Committed forward displacement from steps (moved_m on MOVE_FORWARD)."""
    steps = run / "steps.jsonl"
    if not steps.is_file():
        return 0.0
    tot = 0.0
    for line in steps.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        ex = o.get("exec") or {}
        name = ex.get("action_name") or o.get("planner_action_name") or ""
        if "MOVE_FORWARD" in str(name) or str(ex.get("raw_action")) == "1":
            try:
                tot += float(ex.get("moved_m") or 0.0)
            except Exception:
                pass
    return tot


def _recovery_stats(run: Path) -> Dict[str, Any]:
    steps = run / "steps.jsonl"
    stats = {
        "recovery_attempts": 0,
        "by_kind": Counter(),
        "executed_ok": 0,
        "blocked": 0,
        "truncated": 0,
        "forward_progress_n": 0,  # recovery that moved_m > 1e-3
        "forced_forward_attempts": 0,
        "forced_forward_executed": 0,
        "forced_forward_moved": 0,
        "opposite_turn_attempts": 0,
        "gimbal_look_attempts": 0,
        "blocking_links": Counter(),
        "block_reasons": Counter(),
    }
    if not steps.is_file():
        return stats
    for line in steps.read_text().splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        ex = o.get("exec") or {}
        br = ex.get("blocked_recovery")
        if not isinstance(br, dict):
            # also count non-recovery blocks for links
            if ex.get("blocked"):
                reason = ex.get("block_reason") or "unknown"
                stats["block_reasons"][reason] += 1
                links = ex.get("blocking_links") or ex.get("first_blocking_links") or []
                if isinstance(links, str):
                    links = [links]
                for lk in links or []:
                    stats["blocking_links"][str(lk)] += 1
            continue
        stats["recovery_attempts"] += 1
        kind = str(br.get("recovery_kind") or "unknown")
        stats["by_kind"][kind] += 1
        if kind == "forced_forward_after_turn_block":
            stats["forced_forward_attempts"] += 1
        elif kind == "opposite_turn":
            stats["opposite_turn_attempts"] += 1
        elif "gimbal" in kind or "look" in kind:
            stats["gimbal_look_attempts"] += 1
        executed = bool(ex.get("executed"))
        blocked = bool(ex.get("blocked"))
        truncated = bool(ex.get("truncated"))
        moved = float(ex.get("moved_m") or 0.0)
        if executed and not blocked:
            stats["executed_ok"] += 1
        if blocked:
            stats["blocked"] += 1
        if truncated:
            stats["truncated"] += 1
        if moved > 1e-3:
            stats["forward_progress_n"] += 1
        if kind == "forced_forward_after_turn_block":
            if executed and not blocked:
                stats["forced_forward_executed"] += 1
            if moved > 1e-3:
                stats["forced_forward_moved"] += 1
        if blocked:
            reason = ex.get("block_reason") or "unknown"
            stats["block_reasons"][reason] += 1
            links = ex.get("blocking_links") or ex.get("first_blocking_links") or []
            if isinstance(links, str):
                links = [links]
            for lk in links or []:
                stats["blocking_links"][str(lk)] += 1
    return stats


def _success(summary: dict) -> Optional[bool]:
    for k in ("success", "objectnav_success", "success_claimed"):
        if summary.get(k) is not None:
            return bool(summary[k])
    m = summary.get("metrics") or {}
    if isinstance(m, dict) and m.get("success") is not None:
        return bool(m["success"])
    return None


def analyze_run(tag: str, profile: str, recovery: str) -> Dict[str, Any]:
    run_id = f"{BATCH}_{tag}"
    run = OUT_ROOT / run_id
    summary = _load_json(run / "summary.json") or {}
    pm = _load_json(run / "process_meta.json") or {}
    cam = _load_json(run / "camera_mode.json") or {}
    ep = _effective_params(run)
    rec = _recovery_stats(run)
    # PPO usage
    ppo_json = pm.get("ppo_raise_json") or summary.get("ppo_raise_json") or ""
    ppo_used = bool(str(ppo_json).strip()) or bool(summary.get("ppo_raise"))
    row = {
        "tag": tag,
        "profile": profile,
        "recovery": recovery,
        "run_id": run_id,
        "out": str(run),
        "exists": run.is_dir() and (run / "summary.json").is_file(),
        "status": summary.get("status"),
        "termination": summary.get("termination"),
        "success": _success(summary),
        "spawn_status": summary.get("spawn_status") or pm.get("spawn_status"),
        "n_steps": summary.get("n_steps"),
        "sum_moved_m": summary.get("sum_moved_m"),
        "forward_moved_m": _forward_m(run),
        "dtg": _dtg(summary, run),
        "n_blocked_exec": summary.get("n_blocked_exec"),
        "n_truncated_exec": summary.get("n_truncated_exec"),
        "n_blocked_recovery": summary.get("n_blocked_recovery"),
        "blocked_recovery_mode": summary.get("blocked_recovery_mode")
        or pm.get("blocked_recovery_mode"),
        "camera_mode": summary.get("camera_mode")
        or pm.get("camera_mode")
        or cam.get("camera_mode"),
        "robot_scale": summary.get("robot_scale") or pm.get("robot_scale"),
        "code_git_sha": pm.get("code_git_sha") or pm.get("git_sha_vln"),
        "force_spawn_json": pm.get("force_spawn_json") or summary.get("force_spawn_json"),
        "ppo_used": ppo_used,
        "ppo_raise_json": ppo_json or None,
        "arm_pose_source": (
            "ppo_raise_json"
            if ppo_used
            else "fixed_base_gimbal_default_ARM / no PPO (camera_mode fixed_base_gimbal)"
        ),
        "effective_params": ep,
        "recovery_stats": {
            k: (dict(v) if isinstance(v, Counter) else v) for k, v in rec.items()
        },
        "nf_look_expected": False,
        "nf_look_actual": ep.get("enable_no_frontier_look"),
    }
    # config wiring checks
    infl = ep.get("obstacles_inflation")
    soft_r = ep.get("soft_cost_range_m")
    soft_w = ep.get("soft_cost_weight")
    lock = ep.get("lock_obstacles_inflation")
    if profile == "legacy018":
        row["profile_ok"] = (
            str(infl) in ("0.18", "0.180")
            and str(soft_r) in ("0.0", "0", "0.00")
            and str(lock).lower() in ("false", "0")
        )
    elif profile == "inf020_soft010":
        row["profile_ok"] = (
            str(infl) in ("0.2", "0.20", "0.200")
            and str(soft_r) in ("0.1", "0.10", "0.100")
            and str(soft_w) in ("2.0", "2", "2.00")
            and str(lock).lower() in ("true", "1")
        )
    else:
        row["profile_ok"] = None
    row["recovery_mode_ok"] = row["blocked_recovery_mode"] == recovery
    row["valid"] = bool(
        row["exists"]
        and row["spawn_status"] == "ok"
        and row["status"] == "ok"
        and row.get("profile_ok")
        and row.get("recovery_mode_ok")
        and str(row.get("nf_look_actual")).lower() in ("false", "0", "none")
    )
    return row


def main() -> int:
    jobs: List[tuple] = []
    for line in JOBS.read_text().splitlines()[1:]:
        if not line.strip():
            continue
        tag, profile, recovery, *_ = line.split("\t")
        jobs.append((tag, profile, recovery))
    rows = [analyze_run(t, p, r) for t, p, r in jobs]
    out_json = REPORT / "SUMMARY_ROWS.json"
    out_json.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    # markdown table
    lines = [
        "# Joint4 summary",
        "",
        f"Batch `{BATCH}`",
        "",
        "| tag | profile | recovery | valid | success | termination | steps | sum_moved | fwd_m | dtg | blocked | trunc | recov | FF_try/exec/moved |",
        "|-----|---------|----------|-------|---------|-------------|-------|-----------|-------|-----|---------|-------|-------|-------------------|",
    ]
    for r in rows:
        rs = r.get("recovery_stats") or {}
        ff = f"{rs.get('forced_forward_attempts',0)}/{rs.get('forced_forward_executed',0)}/{rs.get('forced_forward_moved',0)}"
        lines.append(
            "| {tag} | {profile} | {recovery} | {valid} | {success} | {termination} | {n_steps} | {sum_moved_m} | {forward_moved_m} | {dtg} | {n_blocked_exec} | {n_truncated_exec} | {n_blocked_recovery} | {ff} |".format(
                tag=r["tag"],
                profile=r["profile"],
                recovery=r["recovery"],
                valid=r.get("valid"),
                success=r.get("success"),
                termination=r.get("termination"),
                n_steps=r.get("n_steps"),
                sum_moved_m=round(float(r["sum_moved_m"] or 0), 3),
                forward_moved_m=round(float(r["forward_moved_m"] or 0), 3),
                dtg=("" if r.get("dtg") is None else round(float(r["dtg"]), 3)),
                n_blocked_exec=r.get("n_blocked_exec"),
                n_truncated_exec=r.get("n_truncated_exec"),
                n_blocked_recovery=r.get("n_blocked_recovery"),
                ff=ff,
            )
        )
    (REPORT / "SUMMARY_TABLE.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"n": len(rows), "done": sum(1 for r in rows if r["exists"]), "path": str(out_json)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
