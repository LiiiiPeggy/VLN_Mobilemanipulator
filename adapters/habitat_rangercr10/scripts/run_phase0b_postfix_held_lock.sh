#!/usr/bin/env bash
# ################################
# Run phase0b ON-only while caller already holds _sim_host_run.lock.
# Releases lock and cleans B ros leftovers on EXIT.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SAFE="${B_SAFE_DIR:-/home/ubuntu/locomani/B_followup_safe}"
PAIR_DIR="$ROOT/reports/ranger_target_discovery_followup/wrong_stop_audit/paired_b"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentB_nofrontier}"
REPORT_DIR="${REPORT_DIR:-$PAIR_DIR/results}"
CONTAINER="${CONTAINER:-vln-rangercr10-agentB-nofrontier}"
ROS_PORT="${ROS_PORT:-11314}"
BATCH_ID="${BATCH_ID:-phase0b_fix_$(date +%Y%m%d_%H%M%S)}"
PHASE="${PHASE:-phase0b_post_recovery_fix_on}"
MAX_STEPS="${MAX_STEPS:-150}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
export SIM_HOST_LOCK="${SIM_HOST_LOCK:-/home/ubuntu/locomani/_sim_host_run.lock}"
export LOCK_OWNER="${LOCK_OWNER:-agentB_nofrontier}"
HOST_LOCK_SH="$ROOT/adapters/habitat_rangercr10/scripts/host_sim_lock.sh"
BEFORE_ON="${BEFORE_ON:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentB_nofrontier/agentB_phase0_hy1_20261121_235918_hy1_plant_0_ON}"

mkdir -p "$REPORT_DIR" "$OUT_ROOT" "$SAFE/host_lock"
bash "$HOST_LOCK_SH" status | tee -a "$SAFE/host_lock/b_host_lock_meta.txt"
echo "$(date -Is) batch=$BATCH_ID phase=$PHASE held_lock_start" | tee -a "$SAFE/host_lock/b_host_lock_meta.txt"

bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_apex_symlink_safe.sh" "$CONTAINER"

SUMMARY="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: >"$SUMMARY"
echo "protocol_budget_MAX_STEPS_${MAX_STEPS}_EXPLORE_${MAX_EXPLORE_ACTIONS}" >"$REPORT_DIR/budget_label_${BATCH_ID}.txt"
python3 - <<PY >"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"
import json
from pathlib import Path
doc=json.loads(Path("$PAIR_DIR/lists/paired_manifest.json").read_text())
phase=doc["phases"]["$PHASE"]
by={e["id"]:e for e in doc["episodes"]}
for eid in phase["episodes"]:
    e=by[eid]
    for arm in phase["arms"]:
        tag="ON" if arm else "OFF"
        print("\t".join([
            e["id"], tag, "true" if arm else "false",
            e["scene_filter"], e["category"], str(e["episode_id"]),
            e["force_spawn_json"], e.get("bucket",""),
        ]))
PY
echo "[B] phase=$PHASE jobs=$(wc -l <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv") batch=$BATCH_ID"

cleanup() {
  docker exec -u root "$CONTAINER" bash -lc \
    "pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; pkill -9 -f apexnav_real_episode 2>/dev/null; sleep 1; true" || true
  LOCK_OWNER="$LOCK_OWNER" SIM_HOST_LOCK="$SIM_HOST_LOCK" bash "$HOST_LOCK_SH" release || true
  echo "$(date -Is) released owner=$LOCK_OWNER batch=$BATCH_ID" >>"$SAFE/host_lock/b_host_lock_meta.txt"
}
trap cleanup EXIT

while IFS=$'\t' read -r EP_ID ARM_TAG ENABLE SCENE CAT EP FORCE BUCKET; do
  RUN_ID="agentB_${BATCH_ID}_${EP_ID}_${ARM_TAG}"
  echo "===== $RUN_ID enable=$ENABLE ====="
  docker exec -u root "$CONTAINER" bash -lc \
    "pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true" || true
  set +e
  CONTAINER="$CONTAINER" ROS_PORT="$ROS_PORT" \
    ENABLE_NO_FRONTIER_LOOK="$ENABLE" \
    SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" \
    RUN_ID="$RUN_ID" OUT_DIR="$OUT_ROOT" \
    ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal \
    FORCE_SPAWN_JSON="$FORCE" \
    STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none SKIP_DEMO=1 \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode_agentB.sh" \
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
    "arm": "$ARM_TAG",
    "enable_no_frontier_look": "$ENABLE" == "true",
    "scene": "$SCENE",
    "category": "$CAT",
    "episode_id": "$EP",
    "force_spawn_json": "$FORCE",
    "bucket_prior": "$BUCKET",
    "max_steps": int("$MAX_STEPS"),
    "max_explore_actions": int("$MAX_EXPLORE_ACTIONS"),
    "rc": int("$rc"),
    "run_dir": str(run),
    "baseline_before_run": "$BEFORE_ON",
    "fix": "post_look_no_forward_recovery",
}
sum_p = run / "summary.json"
if sum_p.is_file():
    s=json.loads(sum_p.read_text())
    row["termination"]=s.get("termination")
    row["n_steps"]=s.get("n_steps")
    row["sum_moved_m"]=s.get("sum_moved_m")
    row["final_dtg"]=s.get("final_distance_to_goal_eval_only")
    row["success_claimed"]=s.get("success_claimed")
    row["spawn_status"]=s.get("spawn_status")
print(json.dumps(row))
PY
  python3 "$ROOT/adapters/habitat_rangercr10/scripts/analyze_nofrontier_pair_run.py" \
    --run_dir "$OUT_ROOT/$RUN_ID" \
    --enable "$ENABLE" \
    --out "$REPORT_DIR/analyze_${RUN_ID}.json" || true
done <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"

echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
echo "[B] done batch=$BATCH_ID"
cat "$SUMMARY"
