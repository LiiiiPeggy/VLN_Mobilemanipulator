#!/usr/bin/env bash
# ################################
# Paired ObjectHold-max-dist fix validation (main session, holds host lock).
# Unique variable: OBJECT_HOLD_MAX_DIST (3.0 OFF vs 8.0 ON).
# Fixed: legacy018 (or per-job), recovery, nf_look=OFF, no PPO, scale0.7 gimbal.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/adapters/habitat_rangercr10/scripts/run_integrate_defaults.env"
# Do not inherit smoke/joint batch ids or short budgets from the parent shell.
if [[ "${BATCH_ID:-}" == joint4_* ]] || [[ "${BATCH_ID:-}" == smoke_* ]]; then
  unset BATCH_ID
fi
BATCH_ID="approach_fix_$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate}"
OUT_ROOT="${OUT_DIR}/$BATCH_ID"
REPORT_DIR="$ROOT/reports/integration_20261122/approach_fix/results_$BATCH_ID"
mkdir -p "$OUT_ROOT" "$REPORT_DIR"
LOCK_SCRIPT="$ROOT/adapters/habitat_rangercr10/scripts/host_sim_lock.sh"
export LOCK_OWNER=integrate_main_approach_fix

"$LOCK_SCRIPT" acquire
cleanup() {
  # stop leftover episode helpers in integrate container only
  docker exec "$CONTAINER" bash -lc \
    'pkill -f "apexnav_real_episode|roslaunch.*exploration_rangercr10|roscore" 2>/dev/null || true' \
    >/dev/null 2>&1 || true
  "$LOCK_SCRIPT" release || true
}
trap cleanup EXIT

# Joint4-matched formal budget (ignore inherited smoke 40/20).
export MAX_STEPS=150
export MAX_EXPLORE_ACTIONS=100
export ENABLE_NO_FRONTIER_LOOK=false
export STARTUP_PRIOR_MODE=initial_footprint
export STARTUP_PRIOR_EXPAND_M=0.3
export ROBOT_SCALE=0.7
export CAMERA_MODE=fixed_base_gimbal
export SKIP_DEMO=1
export PLAN_DIAG_ENABLE=true
export PIPELINE_DIAG_ENABLE=true
# no PPO
unset PPO_RAISE_JSON || true
export PPO_RAISE_JSON=""

JSONL="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: >"$JSONL"
echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
echo "git_head=$(git -C "$ROOT" rev-parse HEAD)" >"$REPORT_DIR/freeze_meta.txt"
echo "exploration_node_mtime=$(docker exec "$CONTAINER" stat -c %Y /workspace/VLN_Mobilemanipulator/.catkin_devel_integrate/lib/exploration_manager/exploration_node)" >>"$REPORT_DIR/freeze_meta.txt"

run_one() {
  local tag="$1" profile="$2" recovery="$3" hold="$4" scene="$5" category="$6" episode="$7" spawn="$8"
  export INFLATION_PROFILE="$profile"
  export BLOCKED_RECOVERY_MODE="$recovery"
  export OBJECT_HOLD_MAX_DIST="$hold"
  export SCENE_FILTER="$scene"
  export CATEGORY_FILTER="$category"
  export EPISODE_ID="$episode"
  export FORCE_SPAWN_JSON="$spawn"
  export RUN_ID="${BATCH_ID}_${tag}"
  export OUT_DIR="$OUT_ROOT"
  echo "[approach_fix] start $tag hold=$hold profile=$profile recovery=$recovery" | tee -a "$REPORT_DIR/host.log"
  set +e
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$REPORT_DIR/${tag}_host.log" 2>&1
  local rc=$?
  set -e
  local SUM="$OUT_ROOT/$RUN_ID/summary.json"
  python3 - <<PY >>"$JSONL"
import json, pathlib, time
tag="$tag"; profile="$profile"; recovery="$recovery"; hold="$hold"; rc=int("$rc")
p=pathlib.Path("$SUM")
row={"tag":tag,"profile":profile,"recovery":recovery,"object_hold_max_dist":float(hold),
     "fix_on": float(hold)>=7.9, "container_rc":rc,"t":time.time()}
if p.exists():
  s=json.loads(p.read_text())
  dtg=s.get("final_distance_to_goal_eval_only")
  term=s.get("termination")
  near=bool(s.get("near_goal"))
  # SR_proxy: planner_stop + near_goal (success_claimed always False by design)
  sr = bool(term=="planner_stop" and near)
  row.update({
    "run_id": s.get("run_id") or "$RUN_ID",
    "status": s.get("status"),
    "termination": term,
    "success_claimed": s.get("success_claimed"),
    "sr_proxy": sr,
    "near_goal": near,
    "n_steps": s.get("n_steps"),
    "sum_moved_m": s.get("sum_moved_m"),
    "dtg": dtg,
    "n_blocked_exec": s.get("n_blocked_exec"),
    "n_truncated_exec": s.get("n_truncated_exec"),
    "n_blocked_recovery": s.get("n_blocked_recovery"),
    "blocked_recovery_mode": s.get("blocked_recovery_mode"),
    "spawn_status": s.get("spawn_status"),
    "out": str(p.parent),
  })
else:
  row.update({"status":"missing_summary","out":"$OUT_ROOT/$RUN_ID","sr_proxy":False})
print(json.dumps(row, ensure_ascii=False))
PY
  echo "[approach_fix] done $tag rc=$rc" | tee -a "$REPORT_DIR/host.log"
}

# --- hy1 ON (OFF reused from joint4) ---
run_one hy1_hold8_on legacy018 v2 8.0 HY1NcmCgn3n plant 0 \
  /workspace/VLN_Mobilemanipulator/reports/ranger_target_discovery_followup/wrong_stop_audit/paired_b/frozen_spawns/hy1_plant_0_start_pose.json

# --- dd4b ON ---
run_one dd4b_hold8_on legacy018 v2 8.0 Dd4bFSTQ8gi toilet 0 \
  /media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/execgimbal_dev24_after_dinofix_20261119_011332_dd4b_toilet_0/start_pose.json

# --- historical success probe OFF (legacy recovery closer to formalgimbal) ---
TEE_SPAWN="/workspace/VLN_Mobilemanipulator/reports/ranger_category_eval_20261116/formal_fixed_gimbal_v1/spawns/TEEsavR23oF_chair_4.json"
run_one tee_chair4_hold3_off legacy018 legacy 3.0 TEEsavR23oF chair 4 "$TEE_SPAWN"

# If OFF shows SR_proxy, run ON; else record gap (no forged positive).
SR=$(python3 - <<PY
import json
from pathlib import Path
rows=[json.loads(l) for l in Path("$JSONL").read_text().splitlines() if l.strip()]
off=[r for r in rows if r.get("tag")=="tee_chair4_hold3_off"]
print("1" if off and off[-1].get("sr_proxy") else "0")
PY
)
if [[ "$SR" == "1" ]]; then
  echo "[approach_fix] tee_chair4 OFF succeeded — running ON" | tee -a "$REPORT_DIR/host.log"
  run_one tee_chair4_hold8_on legacy018 legacy 8.0 TEEsavR23oF chair 4 "$TEE_SPAWN"
else
  echo "[approach_fix] tee_chair4 OFF not SR_proxy — regression gap (no ON)" | tee -a "$REPORT_DIR/host.log"
  echo '{"tag":"tee_chair4_hold8_on","skipped":true,"reason":"off_not_sr_proxy_regression_gap"}' >>"$JSONL"
fi

echo "BATCH_DONE $BATCH_ID -> $REPORT_DIR"
