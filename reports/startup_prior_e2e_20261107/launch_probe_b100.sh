#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/startup_prior_e2e_20261107
BATCH_ID=probe_b100_$(date +%Y%m%d_%H%M%S)
echo "$BATCH_ID" >"$REPORT_DIR/probe_batch_id.txt"
echo "START probe $BATCH_ID" | tee "$REPORT_DIR/probe_host.log"
EPISODE_LIST=$REPORT_DIR/probe_budget100_list.json \
  SMOKE_ONLY=1 MODE_FILTER=initial_footprint BATCH_ID=$BATCH_ID \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
  >>"$REPORT_DIR/probe_host.log" 2>&1
echo "PROBE_DONE" | tee -a "$REPORT_DIR/probe_host.log"
