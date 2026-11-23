#!/usr/bin/env bash
# ################################
# After hy1 soft-reach success: Dd4b ON + one regression probe (soft_reach ON).
# Fixed: legacy018, v2, ObjectHold=8.0, nf_look=OFF. Unique: soft_reach true.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/adapters/habitat_rangercr10/scripts/run_integrate_defaults.env"

BATCH_ID="stop_fix_ext_$(date +%Y%m%d_%H%M%S)"
OUT_DIR=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate
OUT_ROOT="${OUT_DIR}/$BATCH_ID"
REPORT_DIR="$ROOT/reports/integration_20261122/stop_fix/results_$BATCH_ID"
mkdir -p "$OUT_ROOT" "$REPORT_DIR"
LOCK_SCRIPT="$ROOT/adapters/habitat_rangercr10/scripts/host_sim_lock.sh"
export LOCK_OWNER=integrate_main_stop_fix

"$LOCK_SCRIPT" acquire
cleanup() {
  docker exec "$CONTAINER" bash -lc \
    'pkill -f "apexnav_real_episode|roslaunch.*exploration_rangercr10|roscore" 2>/dev/null || true' \
    >/dev/null 2>&1 || true
  "$LOCK_SCRIPT" release || true
}
trap cleanup EXIT

export MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100
export ENABLE_NO_FRONTIER_LOOK=false
export INFLATION_PROFILE=legacy018
export BLOCKED_RECOVERY_MODE=v2
export OBJECT_HOLD_MAX_DIST=8.0
export SOFT_REACH_ON_ANY_STUCK=true
export STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3
export ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal
export SKIP_DEMO=1 PLAN_DIAG_ENABLE=true PIPELINE_DIAG_ENABLE=true
export PPO_RAISE_JSON=""

JSONL="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: >"$JSONL"
echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"

run_one() {
  local tag="$1" scene="$2" cat="$3" ep="$4" spawn="$5"
  export SCENE_FILTER="$scene" CATEGORY_FILTER="$cat" EPISODE_ID="$ep"
  export FORCE_SPAWN_JSON="$spawn"
  export RUN_ID="${BATCH_ID}_${tag}"
  export OUT_DIR="$OUT_ROOT"
  echo "[stop_fix_ext] start $tag" | tee -a "$REPORT_DIR/host.log"
  set +e
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$REPORT_DIR/${tag}_host.log" 2>&1
  local rc=$?
  set -e
  python3 - "$tag" "$rc" "$OUT_ROOT/$RUN_ID/summary.json" "$OUT_ROOT/$RUN_ID" <<'PY' >>"$JSONL"
import json, pathlib, sys, time
tag, rc, sum_path, out = sys.argv[1:5]
rc=int(rc)
p=pathlib.Path(sum_path)
row={"tag":tag,"soft_reach_on_any_stuck":True,"object_hold_max_dist":8.0,
     "profile":"legacy018","recovery":"v2","container_rc":rc,"t":time.time()}
if p.exists():
  s=json.loads(p.read_text())
  term=s.get("termination"); near=bool(s.get("near_goal"))
  row.update({
    "run_id":s.get("run_id") or pathlib.Path(out).name,"status":s.get("status"),
    "termination":term,"success_claimed":s.get("success_claimed"),
    "sr_proxy": bool(term=="planner_stop" and near),"near_goal":near,
    "n_steps":s.get("n_steps"),"sum_moved_m":s.get("sum_moved_m"),
    "dtg":s.get("final_distance_to_goal_eval_only"),
    "dtg_point":s.get("final_distance_to_goal_point_eval_only"),
    "n_blocked_exec":s.get("n_blocked_exec"),"spawn_status":s.get("spawn_status"),
    "out":str(p.parent),
  })
else:
  row.update({"status":"missing_summary","out":out,"sr_proxy":False})
print(json.dumps(row, ensure_ascii=False))
PY
  echo "[stop_fix_ext] done $tag rc=$rc" | tee -a "$REPORT_DIR/host.log"
}

# Dd4b ON (OFF = approach_fix dd4b_hold8_on reused in report)
run_one dd4b_soft_reach_on Dd4bFSTQ8gi toilet 0 \
  /media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/execgimbal_dev24_after_dinofix_20261119_011332_dd4b_toilet_0/start_pose.json

# Regression: historical plant success spawn (formal gimbal)
run_one ziup_plant3_soft_reach_on ziup5kvtCCR plant 3 \
  /workspace/VLN_Mobilemanipulator/reports/ranger_category_eval_20261116/formal_fixed_gimbal_v1/spawns/ziup5kvtCCR_plant_3.json

echo "BATCH_DONE $BATCH_ID -> $REPORT_DIR"
