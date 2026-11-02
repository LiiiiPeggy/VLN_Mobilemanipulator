#!/usr/bin/env bash
# Runs inside vln-msgnav. Writes to D-disk batch dir via absolute mount.
set -eo pipefail
OUT=/media/ubuntu/D/VLN_shared/runs/batch_20261101/MSGNav
mkdir -p "$OUT"
CSV="$OUT/metrics.csv"
echo "specific_idx,scene_file,status,success_by_distance,spl_by_distance,wall_s,peak_mem_mib,logfile" > "$CSV"

cd /workspace/MSGNav
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=/shared/cache/huggingface
export HUGGINGFACE_HUB_CACHE=/shared/cache/huggingface/hub
export PYTHONUNBUFFERED=1

mapfile -t SCENES < <(ls -1 data/objectnav_hm3d_batch8 | sort)

for i in 0 1 2 3 4 5 6 7; do
  LOG="$OUT/ep_${i}.log"
  MEM="$OUT/ep_${i}.mem"
  SCENE="${SCENES[$i]:-unknown}"
  echo "==== MSGNav ep $i ($SCENE) ====" | tee -a "$OUT/driver.log"
  ( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 20; done ) >"$MEM" &
  MPID=$!
  START=$(date +%s)
  set +e
  python -u run_hm3d_evaluation.py -cf cfg/eval_hm3d_batch8.yaml --specific "$i" >"$LOG" 2>&1
  EC=$?
  set -e
  END=$(date +%s)
  kill $MPID 2>/dev/null || true
  wait $MPID 2>/dev/null || true
  PEAK=$(awk 'BEGIN{m=0}{if($1+0>m)m=$1+0}END{print m}' "$MEM")
  SR=$(grep -oE 'Success rate by distance:[[:space:]]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  SPL=$(grep -oE 'SPL by distance:[[:space:]]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  if [ "$EC" != 0 ]; then ST=CRASH
  elif [ "${SR:-0}" = "100.00" ] || [ "${SR:-0}" = "100" ] || [ "${SR:-0}" = "1.0" ]; then ST=TASK_SUCCESS
  else ST=TASK_FAIL
  fi
  # rewrite header once with SR/SPL columns on first row already written without them — keep simple CSV
  echo "$i,$SCENE,$ST,${SR:-},${SPL:-},$((END-START)),$PEAK,$LOG" | tee -a "$CSV"
done
echo DONE | tee -a "$OUT/driver.log"
