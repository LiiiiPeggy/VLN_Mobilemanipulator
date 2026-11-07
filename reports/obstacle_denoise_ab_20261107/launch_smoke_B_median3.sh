#!/usr/bin/env bash
# ################################
# Smoke B: initial_footprint + expand 0.3 + obstacle_denoise=median3
# ################################
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/obstacle_denoise_ab_20261107
BATCH_ID=smoke_B_med3_$(date +%Y%m%d_%H%M%S)
echo "$BATCH_ID" >"$REPORT_DIR/smoke_B_batch_id.txt"
echo "START $BATCH_ID" | tee "$REPORT_DIR/smoke_B_host.log"
EPISODE_LIST=$ROOT/reports/startup_prior_e2e_20261107/episode_list.json \
  REPORT_DIR=$REPORT_DIR \
  SMOKE_ONLY=1 MODE_FILTER=initial_footprint BATCH_ID=$BATCH_ID \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
  STARTUP_PRIOR_EXPAND_M=0.3 OBSTACLE_DENOISE=median3 \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
  >>"$REPORT_DIR/smoke_B_host.log" 2>&1
echo "SMOKE_B_DONE" | tee -a "$REPORT_DIR/smoke_B_host.log"
# ################################
