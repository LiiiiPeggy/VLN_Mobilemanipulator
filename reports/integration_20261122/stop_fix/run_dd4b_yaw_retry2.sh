#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$ROOT/adapters/habitat_rangercr10/scripts/run_integrate_defaults.env"
BATCH_ID="stop_fix_dd4b2_$(date +%Y%m%d_%H%M%S)"
OUT_ROOT=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/$BATCH_ID
REPORT_DIR="$ROOT/reports/integration_20261122/stop_fix/results_$BATCH_ID"
mkdir -p "$OUT_ROOT" "$REPORT_DIR"
LOCK="$ROOT/adapters/habitat_rangercr10/scripts/host_sim_lock.sh"
export LOCK_OWNER=integrate_main_dd4b_retry2
"$LOCK" acquire
cleanup(){ docker exec "$CONTAINER" bash -lc 'pkill -f "apexnav_real_episode|roslaunch.*exploration_rangercr10|roscore" 2>/dev/null || true' >/dev/null 2>&1 || true; "$LOCK" release || true; }
trap cleanup EXIT
export MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 ENABLE_NO_FRONTIER_LOOK=false
export INFLATION_PROFILE=legacy018 BLOCKED_RECOVERY_MODE=v2 OBJECT_HOLD_MAX_DIST=8.0
export SOFT_REACH_ON_ANY_STUCK=true STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3
export ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal SKIP_DEMO=1
export PLAN_DIAG_ENABLE=true PIPELINE_DIAG_ENABLE=true PPO_RAISE_JSON=""
export SCENE_FILTER=Dd4bFSTQ8gi CATEGORY_FILTER=toilet EPISODE_ID=0
export FORCE_SPAWN_JSON=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/execgimbal_dev24_after_dinofix_20261119_011332_dd4b_toilet_0/start_pose.json
export RUN_ID="${BATCH_ID}_dd4b_yaw_aware_on" OUT_DIR="$OUT_ROOT"
echo "[dd4b_retry2] start" | tee "$REPORT_DIR/host.log"
set +e
bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" >"$REPORT_DIR/dd4b_host.log" 2>&1
rc=$?
set -e
echo "[dd4b_retry2] done rc=$rc" | tee -a "$REPORT_DIR/host.log"
python3 - <<PY
import json,pathlib,time
p=pathlib.Path("$OUT_ROOT/$RUN_ID/summary.json")
row={"tag":"dd4b_yaw_aware_on","rc":$rc,"t":time.time(),"scene":"Dd4bFSTQ8gi"}
if p.exists():
  s=json.loads(p.read_text()); term=s.get("termination"); near=bool(s.get("near_goal"))
  row.update({k:s.get(k) for k in ["status","termination","near_goal","n_steps","sum_moved_m","final_distance_to_goal_eval_only","n_blocked_exec","spawn_status"]})
  row["sr_proxy"]=bool(term=="planner_stop" and near); row["out"]=str(p.parent)
print(json.dumps(row)); open("$REPORT_DIR/batch.jsonl","w").write(json.dumps(row)+"\n")
PY
echo BATCH_DONE
