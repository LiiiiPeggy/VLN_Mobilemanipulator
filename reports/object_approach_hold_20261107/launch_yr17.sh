#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/object_approach_hold_20261107
BATCH_ID=yr17_hold_$(date +%Y%m%d_%H%M%S)
echo "$BATCH_ID" >"$REPORT_DIR/yr17_batch_id.txt"
echo "START $BATCH_ID" | tee "$REPORT_DIR/yr17_host.log"
EPISODE_LIST=$REPORT_DIR/yr17_only.json REPORT_DIR=$REPORT_DIR \
  SMOKE_ONLY=0 MODE_FILTER=initial_footprint BATCH_ID=$BATCH_ID \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=0 \
  STARTUP_PRIOR_EXPAND_M=0.3 OBSTACLE_DENOISE=none \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
  >>"$REPORT_DIR/yr17_host.log" 2>&1
echo "YR17_DONE" | tee -a "$REPORT_DIR/yr17_host.log"
