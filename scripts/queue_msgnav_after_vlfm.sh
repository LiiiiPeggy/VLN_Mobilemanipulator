#!/usr/bin/env bash
# Wait until VLFM full-val host process exits, then run MSGNav 20ep gpt-5.6-luna.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
VLFM_PID_FILE=/media/ubuntu/D/VLN_shared/runs/VLFM_full/FULL_VAL_HOST.pid
QUEUE_LOG=/media/ubuntu/D/VLN_shared/runs/MSGNav_luna_20ep/queue_after_vlfm.log
mkdir -p "$(dirname "$QUEUE_LOG")" /media/ubuntu/D/VLN_shared/runs/MSGNav_luna_20ep

echo "[$(date -Iseconds)] queue start; waiting for VLFM pid file $VLFM_PID_FILE" | tee -a "$QUEUE_LOG"
for i in $(seq 1 120); do
  [ -f "$VLFM_PID_FILE" ] && break
  sleep 5
done
if [ ! -f "$VLFM_PID_FILE" ]; then
  echo "No VLFM pid file; abort" | tee -a "$QUEUE_LOG"
  exit 1
fi
VPID=$(cat "$VLFM_PID_FILE")
echo "[$(date -Iseconds)] waiting for VLFM host pid=$VPID GPT_MODEL=gpt-5.6-luna" | tee -a "$QUEUE_LOG"
while kill -0 "$VPID" 2>/dev/null; do
  sleep 60
done
echo "[$(date -Iseconds)] VLFM finished; starting MSGNav 20ep luna" | tee -a "$QUEUE_LOG"
bash "$ROOT/scripts/run_msgnav_20ep_luna.sh" 2>&1 | tee -a "$QUEUE_LOG"
echo "[$(date -Iseconds)] MSGNav 20ep done exit=$?" | tee -a "$QUEUE_LOG"
