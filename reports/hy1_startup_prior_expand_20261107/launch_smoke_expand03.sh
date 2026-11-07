#!/usr/bin/env bash
# ################################
# Smoke: initial_footprint + expand_m=0.3 on HY1/eF36/yr17 (same smoke list).
# ################################
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/hy1_startup_prior_expand_20261107
BATCH_ID=smoke_exp03_$(date +%Y%m%d_%H%M%S)
echo "$BATCH_ID" >"$REPORT_DIR/smoke_batch_id.txt"
echo "START smoke expand0.3 $BATCH_ID" | tee "$REPORT_DIR/smoke_expand_host.log"
EPISODE_LIST=$ROOT/reports/startup_prior_e2e_20261107/episode_list.json \
  SMOKE_ONLY=1 MODE_FILTER=initial_footprint BATCH_ID=$BATCH_ID \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
  STARTUP_PRIOR_EXPAND_M=0.3 \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
  >>"$REPORT_DIR/smoke_expand_host.log" 2>&1
echo "SMOKE_EXPAND_DONE" | tee -a "$REPORT_DIR/smoke_expand_host.log"
# ################################
