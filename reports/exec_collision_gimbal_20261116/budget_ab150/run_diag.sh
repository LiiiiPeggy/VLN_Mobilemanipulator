#!/usr/bin/env bash
# ################################
# Budget single-variable retest: MAX_STEPS=150 / MAX_EXPLORE_ACTIONS=100
# on diagnostic subset (lt9 / k1cup / ef36 / hy1). No recognition/recovery changes.
# ################################
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REP=$ROOT/reports/exec_collision_gimbal_20261116
export EPISODE_LIST=$REP/budget_ab_diag_list.json
export REPORT_DIR=$REP
export OUT_DIR=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real
export MAX_STEPS=150
export MAX_EXPLORE_ACTIONS=100
export BATCH_ID="${BATCH_ID:-budget150_diag_$(date +%Y%m%d_%H%M%S)}"
export SMOKE_ONLY=0
export CAMERA_MODE=fixed_base_gimbal
export GPU="${GPU:-0}"
echo "$BATCH_ID" > "$REP/budget_ab150/diag_batch_id.txt"
echo "START $BATCH_ID MAX_STEPS=$MAX_STEPS MAX_EXPLORE=$MAX_EXPLORE_ACTIONS date=$(date -Is)"
bash "$ROOT/adapters/habitat_rangercr10/scripts/run_exec_collision_baseline_batch.sh"
echo "DONE $BATCH_ID date=$(date -Is)"
