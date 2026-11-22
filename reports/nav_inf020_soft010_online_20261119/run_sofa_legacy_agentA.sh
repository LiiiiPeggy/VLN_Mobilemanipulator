#!/usr/bin/env bash
set -euo pipefail
A_ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator_agentA_navinf
OUT_ROOT=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentA_navinf
REPORT=$A_ROOT/reports/nav_inf020_soft010_online_20261119
BATCH_ID=${BATCH_ID:-sofa_legacy_A_$(date +%Y%m%d_%H%M%S)}
mkdir -p "$OUT_ROOT" "$REPORT"
echo "$BATCH_ID" > "$REPORT/latest_sofa_legacy_batch.txt"
RUN_ID=${BATCH_ID}_sofa_legacy018
spawn=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/formalgimbal_formal150_full_20261117_190344_TEEsavR23oF_sofa_0/start_pose.json
echo "===== $RUN_ID ====="
INFLATION_PROFILE=legacy018 SCENE_FILTER=TEEsavR23oF CATEGORY_FILTER=sofa EPISODE_ID=0 \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 GPU=0 ROS_PORT=11323 \
  RUN_ID=$RUN_ID OUT_DIR=$OUT_ROOT ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal \
  FORCE_SPAWN_JSON=$spawn PPO_RAISE_JSON= \
  STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3 \
  OBSTACLE_DENOISE=none SKIP_DEMO=1 \
  bash "$A_ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode_agentA.sh"
rc=$?
echo DONE rc=$rc
SUM=$OUT_ROOT/$RUN_ID/summary.json
if [[ -f $SUM ]]; then python3 -c "import json;s=json.load(open('$SUM'));print({k:s.get(k) for k in ('termination','n_steps','status','error','executor_version')})"; fi
grep -E "effective obstacles|soft_cost|lock_obstacles|free\(\)|process has died" $OUT_ROOT/$RUN_ID/launch_logs/exploration.log 2>/dev/null | head -25 || true
exit $rc
