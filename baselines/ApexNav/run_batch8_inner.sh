#!/usr/bin/env bash
# Runs inside vln-apexnav. Writes to D-disk batch dir via absolute mount.
set -eo pipefail
# ROS setup scripts reference unset vars; enable nounset only after sourcing.
OUT=/media/ubuntu/D/VLN_shared/runs/batch_20261101/ApexNav
VLM_LOG="$OUT/vlm_servers"
mkdir -p "$OUT" "$VLM_LOG"
CSV="$OUT/metrics.csv"
echo "global_idx,status,success,spl,soft_spl,dtg,wall_s,peak_mem_mib,logfile" > "$CSV"

cd /workspace/ApexNav
export ROS_DISTRO=noetic
set +u
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
set -u

if ! pgrep -x roscore >/dev/null 2>&1; then
  nohup roscore > "$VLM_LOG/roscore_batch.log" 2>&1 &
  sleep 3
fi
if ! pgrep -f exploration_node >/dev/null 2>&1; then
  nohup bash -lc "source /opt/ros/noetic/setup.bash; source /workspace/ApexNav/devel/setup.bash; roslaunch exploration_manager exploration.launch" \
    > "$VLM_LOG/expl_batch.log" 2>&1 &
  sleep 5
fi

pkill -f vlm.detector.grounding_dino 2>/dev/null || true
pkill -f vlm.itm.blip2itm 2>/dev/null || true
pkill -f vlm.segmentor.sam 2>/dev/null || true
pkill -f vlm.detector.yolov7 2>/dev/null || true
sleep 2

export HF_HOME=/shared/cache/huggingface
export TRANSFORMERS_CACHE=/shared/cache/huggingface
export TORCH_HOME=/shared/cache/torch

nohup python -u -m vlm.detector.grounding_dino --port 12181 > "$VLM_LOG/gdino_12181.log" 2>&1 &
nohup python -u -m vlm.itm.blip2itm --port 12182 > "$VLM_LOG/blip2_12182.log" 2>&1 &
nohup python -u -m vlm.segmentor.sam --port 12183 > "$VLM_LOG/sam_12183.log" 2>&1 &
nohup python -u -m vlm.detector.yolov7 --port 12184 > "$VLM_LOG/yolov7_12184.log" 2>&1 &

echo "waiting for VLM ports..."
ready=0
for i in $(seq 1 120); do
  ok=0
  for p in 12181 12182 12183 12184; do
    if python -c "import socket;s=socket.socket();s.settimeout(0.5);s.connect(('127.0.0.1',$p));s.close()" 2>/dev/null; then
      ok=$((ok+1))
    fi
  done
  if [ "$ok" = "4" ]; then
    echo "VLM ports up after ${i} checks"
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" != "1" ]; then
  echo "ERROR: VLM ports not ready" >&2
  tail -n 50 "$VLM_LOG"/*.log || true
  exit 1
fi

EPISODES=(0 1 2 3 4 5 6 7)
if [ "${APEXNAV_EP0_ONLY:-0}" = "1" ]; then
  EPISODES=(0)
elif [ -n "${APEXNAV_EPISODES:-}" ]; then
  # shellcheck disable=SC2206
  EPISODES=(${APEXNAV_EPISODES})
fi

for i in "${EPISODES[@]}"; do
  LOG="$OUT/ep_${i}.log"
  MEMLOG="$OUT/ep_${i}.mem"
  echo "==== ApexNav ep $i ====" | tee -a "$OUT/driver.log"
  ( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 15; done ) >"$MEMLOG" &
  MPID=$!
  START=$(date +%s)
  set +e
  python -u habitat_evaluation.py --dataset hm3dv2 test_epi_num=$i need_video=false >"$LOG" 2>&1
  EC=$?
  set -e
  END=$(date +%s)
  kill $MPID 2>/dev/null || true
  wait $MPID 2>/dev/null || true
  PEAK=$(awk 'BEGIN{m=0} {if($1+0>m)m=$1+0} END{print m}' "$MEMLOG" 2>/dev/null || echo 0)
  WALL=$((END-START))
  SUCC=$(grep -oE 'Average Success[^0-9]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  SPL=$(grep -oE 'Average SPL[^0-9]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  SSPL=$(grep -oE 'Average Soft SPL[^0-9]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  DTG=$(grep -oE 'Average Distance to Goal[^0-9]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  if [ "$EC" != "0" ]; then ST=CRASH
  elif [ "${SUCC:-0}" = "100.00" ] || [ "${SUCC:-0}" = "100" ] || [ "${SUCC:-0}" = "1.0" ] || [ "${SUCC:-0}" = "1.00" ]; then ST=TASK_SUCCESS
  else ST=TASK_FAIL
  fi
  echo "$i,$ST,${SUCC:-},${SPL:-},${SSPL:-},${DTG:-},$WALL,$PEAK,$LOG" | tee -a "$CSV"
done

pkill -f vlm.detector.grounding_dino 2>/dev/null || true
pkill -f vlm.itm.blip2itm 2>/dev/null || true
pkill -f vlm.segmentor.sam 2>/dev/null || true
pkill -f vlm.detector.yolov7 2>/dev/null || true
pkill -f exploration_node 2>/dev/null || true
pkill -f exploration.launch 2>/dev/null || true
killall roscore 2>/dev/null || true
echo DONE | tee -a "$OUT/driver.log"
