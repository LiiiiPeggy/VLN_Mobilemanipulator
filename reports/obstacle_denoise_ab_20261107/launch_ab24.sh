#!/usr/bin/env bash
# ################################
# Full 24-ep A/B: both arms initial_footprint+expand0.3; A=none denoise, B=median3.
# Uses MODE_FILTER via two sequential batches (same list/budget).
# ################################
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/obstacle_denoise_ab_20261107
LIST=$ROOT/reports/startup_prior_e2e_20261107/episode_list.json

run_arm() {
  local TAG="$1" DENOISE="$2"
  local BATCH_ID="${TAG}_$(date +%Y%m%d_%H%M%S)"
  echo "START $BATCH_ID denoise=$DENOISE" | tee -a "$REPORT_DIR/ab24_host.log"
  EPISODE_LIST=$LIST REPORT_DIR=$REPORT_DIR \
    SMOKE_ONLY=0 MODE_FILTER=initial_footprint BATCH_ID=$BATCH_ID \
    MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
    STARTUP_PRIOR_EXPAND_M=0.3 OBSTACLE_DENOISE=$DENOISE \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
    >>"$REPORT_DIR/ab24_host.log" 2>&1
  echo "DONE $BATCH_ID" | tee -a "$REPORT_DIR/ab24_host.log"
  echo "$BATCH_ID" >>"$REPORT_DIR/ab24_batch_ids.txt"
}

: >"$REPORT_DIR/ab24_host.log"
: >"$REPORT_DIR/ab24_batch_ids.txt"
run_arm ab24_A_none none
run_arm ab24_B_med3 median3
echo "AB24_ALL_DONE" | tee -a "$REPORT_DIR/ab24_host.log"
# ################################
