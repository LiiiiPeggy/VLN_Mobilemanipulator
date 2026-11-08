#!/usr/bin/env bash
# Representative never-SEARCH B-class after HM3D→Apex label map fix.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REPORT_DIR=$ROOT/reports/discovery_label_map_20261108
LIST=$REPORT_DIR/episode_list_reps.json
BATCH_ID=reps_labelmap_$(date +%Y%m%d_%H%M%S)
echo "$BATCH_ID" | tee "$REPORT_DIR/reps_batch_id.txt"
echo "START $BATCH_ID" | tee "$REPORT_DIR/reps_host.log"
EPISODE_LIST=$LIST REPORT_DIR=$REPORT_DIR \
  SMOKE_ONLY=0 MODE_FILTER=initial_footprint BATCH_ID=$BATCH_ID \
  MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
  STARTUP_PRIOR_EXPAND_M=0.3 OBSTACLE_DENOISE=none \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh" \
  >>"$REPORT_DIR/reps_host.log" 2>&1
echo "REPS_LABELMAP_DONE" | tee -a "$REPORT_DIR/reps_host.log"
