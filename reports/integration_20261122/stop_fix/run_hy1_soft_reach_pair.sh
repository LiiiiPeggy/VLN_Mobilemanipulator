#!/usr/bin/env bash
# ################################
# hy1 soft_reach_on_any_stuck pair. Unique var: SOFT_REACH_ON_ANY_STUCK.
# Fixed: legacy018, v2, ObjectHold=8.0, nf_look=OFF, no PPO, joint4 spawn/budget.
# OFF reused from approach_fix hy1_hold8_on when comparable.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/adapters/habitat_rangercr10/scripts/run_integrate_defaults.env"

BATCH_ID="stop_fix_$(date +%Y%m%d_%H%M%S)"
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

export MAX_STEPS=150
export MAX_EXPLORE_ACTIONS=100
export ENABLE_NO_FRONTIER_LOOK=false
export INFLATION_PROFILE=legacy018
export BLOCKED_RECOVERY_MODE=v2
export OBJECT_HOLD_MAX_DIST=8.0
export STARTUP_PRIOR_MODE=initial_footprint
export STARTUP_PRIOR_EXPAND_M=0.3
export ROBOT_SCALE=0.7
export CAMERA_MODE=fixed_base_gimbal
export SKIP_DEMO=1
export PLAN_DIAG_ENABLE=true
export PIPELINE_DIAG_ENABLE=true
export PPO_RAISE_JSON=""
export SCENE_FILTER=HY1NcmCgn3n
export CATEGORY_FILTER=plant
export EPISODE_ID=0
export FORCE_SPAWN_JSON=/workspace/VLN_Mobilemanipulator/reports/ranger_target_discovery_followup/wrong_stop_audit/paired_b/frozen_spawns/hy1_plant_0_start_pose.json

JSONL="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: >"$JSONL"
echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
echo "baseline_sha=$(git -C "$ROOT" rev-parse HEAD)" >"$REPORT_DIR/freeze_meta.txt"
echo "soft_reach_pair: OFF=reuse approach_fix hy1_hold8_on; ON=this batch" >>"$REPORT_DIR/freeze_meta.txt"

# Record OFF reuse pointer
python3 - <<PY >>"$JSONL"
import json, time
print(json.dumps({
  "tag":"hy1_soft_reach_off",
  "soft_reach_on_any_stuck": False,
  "reused": True,
  "out":"/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/approach_fix_20261122_215609/approach_fix_20261122_215609_hy1_hold8_on",
  "profile":"legacy018","recovery":"v2","object_hold_max_dist":8.0,
  "note":"comparable OFF: soft_reach default false",
  "t": time.time(),
}, ensure_ascii=False))
PY

export SOFT_REACH_ON_ANY_STUCK=true
export RUN_ID="${BATCH_ID}_hy1_soft_reach_on"
export OUT_DIR="$OUT_ROOT"
echo "[stop_fix] start hy1_soft_reach_on" | tee -a "$REPORT_DIR/host.log"
set +e
bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
  >"$REPORT_DIR/hy1_soft_reach_on_host.log" 2>&1
rc=$?
set -e
SUM="$OUT_ROOT/$RUN_ID/summary.json"
python3 - <<PY >>"$JSONL"
import json, pathlib, time
rc=int("$rc")
p=pathlib.Path("$SUM")
row={"tag":"hy1_soft_reach_on","soft_reach_on_any_stuck":True,"reused":False,
     "profile":"legacy018","recovery":"v2","object_hold_max_dist":8.0,
     "container_rc":rc,"t":time.time()}
if p.exists():
  s=json.loads(p.read_text())
  term=s.get("termination"); near=bool(s.get("near_goal")); dtg=s.get("final_distance_to_goal_eval_only")
  row.update({
    "run_id":s.get("run_id") or "$RUN_ID","status":s.get("status"),
    "termination":term,"success_claimed":s.get("success_claimed"),
    "sr_proxy": bool(term=="planner_stop" and near),
    "near_goal":near,"n_steps":s.get("n_steps"),"sum_moved_m":s.get("sum_moved_m"),
    "dtg":dtg,"dtg_point":s.get("final_distance_to_goal_point_eval_only"),
    "n_blocked_exec":s.get("n_blocked_exec"),"n_truncated_exec":s.get("n_truncated_exec"),
    "spawn_status":s.get("spawn_status"),"out":str(p.parent),
  })
else:
  row.update({"status":"missing_summary","out":"$OUT_ROOT/$RUN_ID","sr_proxy":False})
print(json.dumps(row, ensure_ascii=False))
PY
echo "[stop_fix] done hy1_soft_reach_on rc=$rc" | tee -a "$REPORT_DIR/host.log"
echo "BATCH_DONE $BATCH_ID -> $REPORT_DIR"
