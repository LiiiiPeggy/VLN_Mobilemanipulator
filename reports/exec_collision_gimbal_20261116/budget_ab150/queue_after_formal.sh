#!/usr/bin/env bash
# ################################
# Wait for Cursor B formal eval to release shared ROS/GPU, then run:
#   1) wheel-support unit verify (no ROS)
#   2) budget150 diagnostic 4-ep (single-variable vs short50)
#   3) smoke (3) with v1.2 recovery
#   4) full dev24 @150/100
# Does NOT touch evaluation/ or kill foreign pids.
# ################################
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REP=$ROOT/reports/exec_collision_gimbal_20261116
FORMAL_LOCK=$ROOT/reports/ranger_category_eval_20261116/formal_fixed_gimbal_v1/latest_full_pid.txt
LOG=$REP/budget_ab150/queue_outer.log
mkdir -p "$REP/budget_ab150"

exec > >(tee -a "$LOG") 2>&1
echo "[queue] start $(date -Is)"

while true; do
  if [[ -f "$FORMAL_LOCK" ]]; then
    fp=$(cat "$FORMAL_LOCK" 2>/dev/null || true)
    if [[ -n "${fp:-}" ]] && kill -0 "$fp" 2>/dev/null; then
      echo "[queue] waiting formal pid=$fp $(date -Is)"
      sleep 120
      continue
    fi
  fi
  # also wait if formalgimbal episode still inside container
  if docker exec vln-rangercr10 bash -lc 'pgrep -af formalgimbal_formal150 >/dev/null'; then
    echo "[queue] waiting formalgimbal process $(date -Is)"
    sleep 60
    continue
  fi
  break
done
echo "[queue] formal clear $(date -Is)"

# 1) wheel verify (GPU may still be warm; ok)
docker exec vln-rangercr10 bash -lc '
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:${PYTHONPATH}
cd /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10
python scripts/verify_wheel_support_classification.py --gpu 0 \
  --out /media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/wheel_support_verify_v12.json
' || echo "[queue] wheel verify rc=$?"

# 2) budget150 diagnostic (single-variable; current code may include v1.2 — label clearly)
export EPISODE_LIST=$REP/budget_ab_diag_list.json
export REPORT_DIR=$REP
export OUT_DIR=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real
export MAX_STEPS=150
export MAX_EXPLORE_ACTIONS=100
export CAMERA_MODE=fixed_base_gimbal
export GPU=0
export BATCH_ID=budget150_diag_v12_$(date +%Y%m%d_%H%M%S)
export SMOKE_ONLY=0
bash "$ROOT/adapters/habitat_rangercr10/scripts/run_exec_collision_baseline_batch.sh"

# 3) smoke then full 24
export EPISODE_LIST=$ROOT/reports/startup_prior_e2e_20261107/episode_list.json
export BATCH_ID=smoke150_v12_$(date +%Y%m%d_%H%M%S)
export SMOKE_ONLY=1
bash "$ROOT/adapters/habitat_rangercr10/scripts/run_exec_collision_baseline_batch.sh"

export BATCH_ID=dev24_150_v12_$(date +%Y%m%d_%H%M%S)
export SMOKE_ONLY=0
bash "$ROOT/adapters/habitat_rangercr10/scripts/run_exec_collision_baseline_batch.sh"

echo "[queue] all done $(date -Is) last_batch=$BATCH_ID"
echo "$BATCH_ID" > "$REP/budget_ab150/last_dev24_batch_id.txt"
