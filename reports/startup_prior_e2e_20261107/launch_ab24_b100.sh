#!/usr/bin/env bash
# ################################
# 同一 24-ep 清单，预算 150/100，A=none vs B=initial_footprint；SKIP_DEMO=1。
# ################################
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/startup_prior_e2e_20261107
BATCH_ID=ab24_b100_$(date +%Y%m%d_%H%M%S)
echo "$BATCH_ID" >"$REPORT_DIR/ab24_b100_batch_id.txt"
echo "START ab24_b100 $BATCH_ID" | tee "$REPORT_DIR/ab_b100_host.log"
EPISODE_LIST=$REPORT_DIR/episode_list.json \
  SMOKE_ONLY=0 MODE_FILTER= BATCH_ID=$BATCH_ID \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
  >>"$REPORT_DIR/ab_b100_host.log" 2>&1
echo "AB24_B100_DONE" | tee -a "$REPORT_DIR/ab_b100_host.log"
# ################################
