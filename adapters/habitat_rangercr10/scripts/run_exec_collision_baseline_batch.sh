#!/usr/bin/env bash
# ################################
# Deployment baseline batch: robot_scale=0.7, camera_mode=fixed_base_gimbal,
# F0+expand0.3, denoise=none, ObjectHold/LabelMap unchanged, NO PPO.
# New execution protocol — not causally comparable to pre-fix trajectories.
#
# Budget labels:
#   MAX_STEPS=50  → short_budget (explore budget rarely binds after 26 init)
#   MAX_STEPS=150 / MAX_EXPLORE_ACTIONS=100 → protocol budget (do not mix)
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LIST="${EPISODE_LIST:-$ROOT/reports/startup_prior_e2e_20261107/episode_list.json}"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/exec_collision_gimbal_20261116}"
SMOKE_ONLY="${SMOKE_ONLY:-0}"
MAX_STEPS="${MAX_STEPS:-50}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
GPU="${GPU:-0}"
PROFILE="${INFLATION_PROFILE:-legacy018}"
BATCH_ID="${BATCH_ID:-$(date +%Y%m%d_%H%M%S)}"
CAMERA_MODE="${CAMERA_MODE:-fixed_base_gimbal}"
# ################################
# VLN adapt: refuse to start if Cursor B formal eval holds the shared ROS/GPU.
# ################################
FORMAL_LOCK="${FORMAL_LOCK:-$ROOT/reports/ranger_category_eval_20261116/formal_fixed_gimbal_v1/latest_full_pid.txt}"
if [[ "${IGNORE_FORMAL_LOCK:-0}" != "1" && -f "$FORMAL_LOCK" ]]; then
  _fp=$(cat "$FORMAL_LOCK" 2>/dev/null || true)
  if [[ -n "${_fp:-}" ]] && kill -0 "$_fp" 2>/dev/null; then
    echo "[baseline] BLOCKED: Cursor B formal eval pid=$_fp still running ($FORMAL_LOCK)."
    echo "[baseline] Queue this batch; do not pkill shared ROS. Set IGNORE_FORMAL_LOCK=1 to override."
    exit 75
  fi
fi
if [[ "$MAX_STEPS" -le 50 ]]; then
  BUDGET_LABEL="short_budget_MAX_STEPS_${MAX_STEPS}"
else
  BUDGET_LABEL="protocol_budget_MAX_STEPS_${MAX_STEPS}_EXPLORE_${MAX_EXPLORE_ACTIONS}"
fi

mkdir -p "$REPORT_DIR" "$OUT_ROOT"
SUMMARY="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: > "$SUMMARY"
echo "$BUDGET_LABEL" > "$REPORT_DIR/budget_label_${BATCH_ID}.txt"

python3 - <<'PY' "$LIST" "$SMOKE_ONLY" >"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"
import json, sys
from pathlib import Path
doc = json.loads(Path(sys.argv[1]).read_text())
smoke_only = sys.argv[2] == "1"
eps = doc["smoke"] if smoke_only else doc["episodes"]
for ep in eps:
    print("\t".join([
        ep["id"],
        ep["scene_filter"],
        ep["category"],
        str(ep["episode_id"]),
        ep["force_spawn_json"],
    ]))
PY

echo "[baseline] jobs=$(wc -l <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv") camera=$CAMERA_MODE budget=$BUDGET_LABEL summary=$SUMMARY"

while IFS=$'\t' read -r EP_ID SCENE CAT EP FORCE; do
  TAG="$EP_ID"
  RUN_ID="execgimbal_${BATCH_ID}_${TAG}"
  echo "===== $RUN_ID ====="
  # ################################
  # Only clear OUR ros master port leftovers; never touch foreign compose stacks.
  # Re-check formal lock each episode so we do not clobber a newly started B run.
  # ################################
  if [[ "${IGNORE_FORMAL_LOCK:-0}" != "1" && -f "$FORMAL_LOCK" ]]; then
    _fp=$(cat "$FORMAL_LOCK" 2>/dev/null || true)
    if [[ -n "${_fp:-}" ]] && kill -0 "$_fp" 2>/dev/null; then
      echo "[baseline] STOP mid-batch: formal eval pid=$_fp acquired lock"
      exit 75
    fi
  fi
  docker exec -u root vln-rangercr10 bash -lc \
    'pkill -9 -f "roscore -p 11312" 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true' || true
  set +e
  INFLATION_PROFILE="$PROFILE" \
    SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" GPU="$GPU" \
    RUN_ID="$RUN_ID" ROBOT_SCALE=0.7 CAMERA_MODE="$CAMERA_MODE" \
    FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="" \
    STARTUP_PRIOR_MODE=initial_footprint \
    STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none \
    SKIP_DEMO="${SKIP_DEMO:-1}" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {
    "batch_id": "$BATCH_ID",
    "run_id": "$RUN_ID",
    "episode_list_id": "$EP_ID",
    "scene": "$SCENE",
    "category": "$CAT",
    "episode_id": "$EP",
    "robot_scale": 0.7,
    "scale_tag": "scaled_robot_proxy_070",
    "camera_mode": "$CAMERA_MODE",
    "budget_label": "$BUDGET_LABEL",
    "max_steps": int("$MAX_STEPS"),
    "max_explore_actions": int("$MAX_EXPLORE_ACTIONS"),
    "executor_version": "kinematic_collision_v1.2",
    "startup_prior_mode": "initial_footprint",
    "startup_prior_expand_m": 0.3,
    "obstacle_denoise": "none",
    "ppo_raise": False,
    "rc": int("$rc"),
}
sum_p = run / "summary.json"
if sum_p.is_file():
    s = json.load(open(sum_p))
    steps = []
    sp = run / "steps.jsonl"
    if sp.is_file():
        steps = [json.loads(l) for l in sp.read_text().splitlines() if l.strip()]
    blocked = sum(1 for st in steps if (st.get("exec") or {}).get("blocked"))
    truncated = sum(1 for st in steps if (st.get("exec") or {}).get("truncated"))
    moved = [float((st.get("exec") or {}).get("moved_m") or 0) for st in steps]
    yaw = [abs(float((st.get("exec") or {}).get("yaw_delta") or 0)) for st in steps]
    # ################################
    # STOP by real action evidence — ANY phase. Do not require explore_planner.
    # near_goal alone is never success.
    # ################################
    stop_steps = []
    for st in steps:
        ex = st.get("exec") or {}
        name = ex.get("action_name") or st.get("planner_action_name")
        raw = ex.get("raw_action") if ex.get("raw_action") is not None else st.get("planner_action")
        if name == "STOP" or raw == 0:
            stop_steps.append({
                "step": st.get("step"),
                "phase": st.get("phase"),
                "dtg": st.get("distance_to_goal_eval_only"),
            })
    sr = False
    for rec in reversed(stop_steps):
        if rec["dtg"] is not None and float(rec["dtg"]) <= 1.0:
            sr = True
            break
    dtgs = [float(st["distance_to_goal_eval_only"]) for st in steps if st.get("distance_to_goal_eval_only") is not None]
    row.update({
        "status": s.get("status"),
        "termination": s.get("termination"),
        "n_steps": s.get("n_steps"),
        "n_init": s.get("n_init_lookaround_actions"),
        "n_explore": s.get("n_explore_planner_actions"),
        "near_goal": s.get("near_goal"),
        "final_dtg": s.get("final_distance_to_goal_eval_only"),
        "dtg_initial": dtgs[0] if dtgs else None,
        "dtg_min": min(dtgs) if dtgs else None,
        "camera_mode_summary": s.get("camera_mode"),
        "simulated_gimbal": s.get("simulated_gimbal"),
        "executor_version_run": s.get("executor_version"),
        "initial_penetration": (s.get("initial_penetration") or {}).get("initial_penetration"),
        "spawn_status": s.get("spawn_status"),
        "n_blocked_exec": blocked,
        "n_truncated_exec": truncated,
        "n_blocked_recovery": s.get("n_blocked_recovery"),
        "sum_moved_m": sum(moved) if moved else s.get("sum_moved_m"),
        "sum_abs_yaw_delta": sum(yaw) if yaw else s.get("sum_abs_yaw_delta"),
        "has_stop_action": bool(stop_steps),
        "stop_steps": stop_steps or None,
        "planner_stop": bool(stop_steps) or s.get("termination") == "planner_stop",
        "sr_proxy": sr,
        "max_steps_summary": s.get("max_steps"),
        "max_explore_summary": s.get("max_explore_actions"),
        "effective_budget": s.get("effective_budget"),
    })
else:
    row["status"] = "missing_summary"
print(json.dumps(row), flush=True)
PY
done <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"

echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
echo "[baseline] done batch=$BATCH_ID budget=$BUDGET_LABEL summary=$SUMMARY"
