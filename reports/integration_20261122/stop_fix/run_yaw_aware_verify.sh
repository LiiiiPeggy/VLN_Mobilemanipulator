#!/usr/bin/env bash
# ################################
# Verify yaw-aware soft_reach candidate: hy1 ON + Dd4b ON.
# Reuse: hy1 OFF (approach_fix hold8), published any_stuck ON (stop_fix_002141).
# Fixed: legacy018, v2, ObjectHold=8.0, nf_look=OFF, budget 150/100.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/adapters/habitat_rangercr10/scripts/run_integrate_defaults.env"

BATCH_ID="stop_fix_yaw_$(date +%Y%m%d_%H%M%S)"
OUT_DIR=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate
OUT_ROOT="${OUT_DIR}/$BATCH_ID"
REPORT_DIR="$ROOT/reports/integration_20261122/stop_fix/results_$BATCH_ID"
mkdir -p "$OUT_ROOT" "$REPORT_DIR"
LOCK_SCRIPT="$ROOT/adapters/habitat_rangercr10/scripts/host_sim_lock.sh"
export LOCK_OWNER=integrate_main_stop_fix_yaw

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
export SKIP_DEMO=0
export PLAN_DIAG_ENABLE=true PIPELINE_DIAG_ENABLE=true
export PPO_RAISE_JSON=""

JSONL="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: >"$JSONL"
echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
{
  echo "baseline_sha=$(git -C "$ROOT" rev-parse HEAD)"
  echo "soft_reach=yaw_aware_candidate"
  echo "exploration_node_mtime=$(docker exec "$CONTAINER" stat -c %Y /workspace/VLN_Mobilemanipulator/.catkin_devel_integrate/lib/exploration_manager/exploration_node)"
} >"$REPORT_DIR/freeze_meta.txt"

# Pointers to reused baselines
python3 - <<PY >>"$JSONL"
import json, time
print(json.dumps({
  "tag":"hy1_soft_reach_off","soft_reach":"legacy_off","reused":True,
  "out":"/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/approach_fix_20261122_215609/approach_fix_20261122_215609_hy1_hold8_on",
  "t":time.time(),
}, ensure_ascii=False))
print(json.dumps({
  "tag":"hy1_published_any_stuck_on","soft_reach":"published_xy_any","reused":True,
  "out":"/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/stop_fix_20261123_002141/stop_fix_20261123_002141_hy1_soft_reach_on",
  "note":"false-positive STOP after successful TURN",
  "t":time.time(),
}, ensure_ascii=False))
PY

run_one() {
  local tag="$1" scene="$2" cat="$3" ep="$4" spawn="$5"
  export SCENE_FILTER="$scene" CATEGORY_FILTER="$cat" EPISODE_ID="$ep"
  export FORCE_SPAWN_JSON="$spawn"
  export RUN_ID="${BATCH_ID}_${tag}"
  export OUT_DIR="$OUT_ROOT"
  echo "[yaw_verify] start $tag" | tee -a "$REPORT_DIR/host.log"
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
row={"tag":tag,"soft_reach":"yaw_aware","soft_reach_on_any_stuck":True,
     "object_hold_max_dist":8.0,"profile":"legacy018","recovery":"v2",
     "container_rc":rc,"t":time.time()}
if p.exists():
  s=json.loads(p.read_text())
  term=s.get("termination"); near=bool(s.get("near_goal"))
  row.update({
    "run_id":s.get("run_id") or pathlib.Path(out).name,"status":s.get("status"),
    "termination":term,"success_claimed":s.get("success_claimed"),
    "sr_proxy": bool(term=="planner_stop" and near),"near_goal":near,
    "n_steps":s.get("n_steps"),"sum_moved_m":s.get("sum_moved_m"),
    "dtg":s.get("final_distance_to_goal_eval_only"),
    "n_blocked_exec":s.get("n_blocked_exec"),"spawn_status":s.get("spawn_status"),
    "out":str(p.parent),
  })
else:
  row.update({"status":"missing_summary","out":out,"sr_proxy":False})
print(json.dumps(row, ensure_ascii=False))
PY
  echo "[yaw_verify] done $tag rc=$rc" | tee -a "$REPORT_DIR/host.log"
}

SPAWN_ROOT=/workspace/VLN_Mobilemanipulator/reports/ranger_target_discovery_followup/wrong_stop_audit/paired_b/frozen_spawns
run_one hy1_yaw_aware_on HY1NcmCgn3n plant 0 "$SPAWN_ROOT/hy1_plant_0_start_pose.json"
run_one dd4b_yaw_aware_on Dd4b8kjZ6Fs toilet 0 "$SPAWN_ROOT/dd4b_toilet_0_start_pose.json"

echo "BATCH_DONE $BATCH_ID -> $REPORT_DIR" | tee -a "$REPORT_DIR/host.log"
