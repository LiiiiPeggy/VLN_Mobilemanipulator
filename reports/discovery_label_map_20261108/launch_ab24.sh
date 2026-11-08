#!/usr/bin/env bash
# Same 24-ep list as Hold baseline; freeze F0/expand/denoise/ObjectHold.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/discovery_label_map_20261108
LIST=$ROOT/reports/startup_prior_e2e_20261107/episode_list.json
BATCH_ID=ab24_labelmap_$(date +%Y%m%d_%H%M%S)
echo "$BATCH_ID" | tee "$REPORT_DIR/ab24_batch_id.txt"
echo "START $BATCH_ID" | tee "$REPORT_DIR/ab24_host.log"
EPISODE_LIST=$LIST REPORT_DIR=$REPORT_DIR \
  SMOKE_ONLY=0 MODE_FILTER=initial_footprint BATCH_ID=$BATCH_ID \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
  STARTUP_PRIOR_EXPAND_M=0.3 OBSTACLE_DENOISE=none \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
  >>"$REPORT_DIR/ab24_host.log" 2>&1
echo "AB24_LABELMAP_DONE" | tee -a "$REPORT_DIR/ab24_host.log"
