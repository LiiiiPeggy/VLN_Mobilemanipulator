#!/usr/bin/env bash
# ################################
# ObjectNav e2e A/B for startup_prior_mode on Ranger 0.7×.
# Arms: A=none, B=initial_footprint. Same episode_list / spawn / budget.
# Does NOT change camera / ground gate / voxel / 15° / strategy.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LIST="${EPISODE_LIST:-$ROOT/reports/startup_prior_e2e_20261107/episode_list.json}"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/startup_prior_e2e_20261107}"
MODE_FILTER="${MODE_FILTER:-}"          # optional: none|initial_footprint
SMOKE_ONLY="${SMOKE_ONLY:-0}"
MAX_STEPS="${MAX_STEPS:-50}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-20}"
GPU="${GPU:-0}"
PROFILE="${INFLATION_PROFILE:-legacy018}"
RAISE_OUT="${PPO_RAISE_JSON:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json}"
BATCH_ID="${BATCH_ID:-$(date +%Y%m%d_%H%M%S)}"

mkdir -p "$REPORT_DIR" "$OUT_ROOT"
SUMMARY="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: > "$SUMMARY"

python3 - <<'PY' "$LIST" "$SMOKE_ONLY" "$MODE_FILTER" >"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"
import json, sys
from pathlib import Path
doc = json.loads(Path(sys.argv[1]).read_text())
smoke_only = sys.argv[2] == "1"
mode_filter = sys.argv[3].strip()
eps = doc["smoke"] if smoke_only else doc["episodes"]
modes = ["none", "initial_footprint"]
if mode_filter:
    modes = [mode_filter]
for mode in modes:
    for ep in eps:
        print("\t".join([
            mode,
            ep["id"],
            ep["scene_filter"],
            ep["category"],
            str(ep["episode_id"]),
            ep["force_spawn_json"],
        ]))
PY

echo "[e2e] jobs=$(wc -l <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv") summary=$SUMMARY smoke=$SMOKE_ONLY"

while IFS=$'\t' read -r MODE EP_ID SCENE CAT EP FORCE; do
  TAG="${MODE}_${EP_ID}"
  RUN_ID="e2e_sp_${BATCH_ID}_${TAG}"
  echo "===== $RUN_ID ====="
  docker exec -u root vln-rangercr10 bash -lc \
    'pkill -9 -f "roscore -p 11312" 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true' || true
  set +e
  # ################################
  # SKIP_DEMO / STARTUP_PRIOR_EXPAND_M 透传（initial_footprint 默认 0.3 由下游脚本处理）。
  # ################################
  INFLATION_PROFILE="$PROFILE" \
    SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" GPU="$GPU" \
    RUN_ID="$RUN_ID" ROBOT_SCALE=0.7 \
    FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="$RAISE_OUT" \
    STARTUP_PRIOR_MODE="$MODE" \
    STARTUP_PRIOR_EXPAND_M="${STARTUP_PRIOR_EXPAND_M:-}" \
    OBSTACLE_DENOISE="${OBSTACLE_DENOISE:-none}" \
    SKIP_DEMO="${SKIP_DEMO:-0}" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  # ################################
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
from collections import Counter
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {
    "batch_id": "$BATCH_ID",
    "run_id": "$RUN_ID",
    "startup_prior_mode": "$MODE",
    "startup_prior_expand_m": float("${STARTUP_PRIOR_EXPAND_M:-0.3}"),
    "obstacle_denoise": "${OBSTACLE_DENOISE:-none}",
    "episode_list_id": "$EP_ID",
    "scene": "$SCENE",
    "category": "$CAT",
    "episode_id": "$EP",
    "robot_scale": 0.7,
    "scale_tag": "scaled_robot_proxy_070",
    "rc": int("$rc"),
    "force_spawn_json": "$FORCE",
}
sum_p = run / "summary.json"
if sum_p.is_file():
    s = json.load(open(sum_p))
    steps = []
    sp = run / "steps.jsonl"
    if sp.is_file():
        steps = [json.loads(l) for l in sp.read_text().splitlines() if l.strip()]
    expl = [st for st in steps if st.get("phase") == "explore_planner"]
    mode_c = Counter(str(st.get("expl_result")) for st in expl if st.get("expl_result") is not None)
    fwd = 0.25 * sum(1 for st in expl if st.get("planner_action_name") == "MOVE_FORWARD")
    acts = Counter(st.get("planner_action_name") for st in expl)
    # Native plan NO_PASSABLE count
    n_nopass = 0
    nd = run / "native_diag" / "native_plan_diag.jsonl"
    if nd.is_file():
        for line in nd.read_text().splitlines():
            if not line.strip():
                continue
            p = json.loads(line)
            if "NO_PASSABLE" in str(p.get("result", "")):
                n_nopass += 1
    # ################################
    # Denoise / inflate diagnostics from pipeline_diag.jsonl (if enabled).
    # ################################
    denoise_before = denoise_after = denoise_removed = inflate_sum = denoise_frames = 0
    pd = run / "native_diag" / "map_pipeline_diag.jsonl"
    if pd.is_file():
        for line in pd.read_text().splitlines():
            if not line.strip():
                continue
            try:
                p = json.loads(line)
            except Exception:
                continue
            if p.get("event") == "after_inflate":
                denoise_before = int(p.get("denoise_sum_occ_before") or denoise_before)
                denoise_after = int(p.get("denoise_sum_occ_after") or denoise_after)
                denoise_removed = int(p.get("denoise_sum_removed") or denoise_removed)
                inflate_sum = int(p.get("sum_inflate_cells") or inflate_sum)
                denoise_frames = int(p.get("denoise_frames") or denoise_frames)
            elif "denoise_occ_before" in p:
                # fallback: last frame-only counters if no after_inflate event
                pass
    # ################################
    near = bool(s.get("near_goal"))
    term = s.get("termination")
    # ObjectNav-style proxy (Habitat success_distance); not official challenge eval.
    success_proxy = bool(term == "planner_stop" and near)
    # Fail taxonomy (primary label)
    fail = "ok_success_proxy" if success_proxy else None
    if fail is None:
        if not s.get("entered_callActionPlanner"):
            fail = "init_or_interface"
        elif n_nopass > 0 and int(s.get("n_explore_planner_actions") or 0) <= 1 and fwd < 0.1:
            fail = "start_blocked_nopassable"
        elif n_nopass > 0 or "NO_PASSABLE" in str(mode_c):
            fail = "mid_plan_nopassable_or_stuck"
        elif term in ("explore_budget_exhausted", "step_budget_exhausted") and not near:
            fail = "explore_no_goal"
        elif term == "planner_stop" and not near:
            fail = "stop_not_near_goal"
        elif term in ("planner_action_timeout", "execution_blocked", "exception", "perception_error"):
            fail = "runtime_or_interface"
        else:
            fail = "other"
    row.update({
        "status": s.get("status"),
        "termination": term,
        "elapsed_sec": s.get("elapsed_sec"),
        "n_steps": s.get("n_steps"),
        "entered_explore": s.get("entered_callActionPlanner"),
        "n_explore": s.get("n_explore_planner_actions"),
        "n_init_lookaround": s.get("n_init_lookaround_actions"),
        "explore_actions": dict(acts),
        "expl_result_hist": dict(mode_c),
        "forward_m": fwd,
        "final_dtg": s.get("final_distance_to_goal_eval_only"),
        "near_goal": near,
        "success_distance": 1.0,
        "objectnav_success_proxy": success_proxy,
        "n_native_nopassable": n_nopass,
        "fail_class": fail,
        "denoise_sum_occ_before": denoise_before,
        "denoise_sum_occ_after": denoise_after,
        "denoise_sum_removed": denoise_removed,
        "denoise_frames": denoise_frames,
        "sum_inflate_cells": inflate_sum,
        "demo_mp4": str(run / "demo" / "apexnav_ranger_paper_demo.mp4")
            if (run / "demo" / "apexnav_ranger_paper_demo.mp4").is_file() else None,
    })
else:
    row["fail_class"] = "runtime_or_interface"
    row["status"] = "missing_summary"
print(json.dumps(row))
PY
done <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"

echo "SUMMARY=$SUMMARY"
python3 "$ROOT/adapters/habitat_rangercr10/scripts/summarize_startup_prior_e2e.py" \
  --summary "$SUMMARY" --out "$REPORT_DIR" --batch-id "$BATCH_ID"
