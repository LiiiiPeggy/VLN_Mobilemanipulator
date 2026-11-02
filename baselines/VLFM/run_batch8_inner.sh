#!/usr/bin/env bash
# Runs inside vln-vlfm. Writes to D-disk batch dir via absolute mount.
set -eo pipefail
OUT=/media/ubuntu/D/VLN_shared/runs/batch_20261101/VLFM
VLM_LOG="$OUT/vlm_servers"
mkdir -p "$OUT" "$VLM_LOG"
LOG="$OUT/batch8.log"
MEM="$OUT/batch8.mem"
CSV="$OUT/metrics.csv"

cd /workspace/VLFM
pkill -f vlfm.vlm.grounding_dino 2>/dev/null || true
pkill -f vlfm.vlm.blip2itm 2>/dev/null || true
pkill -f vlfm.vlm.sam 2>/dev/null || true
pkill -f vlfm.vlm.yolov7 2>/dev/null || true
sleep 1

GD=$(python -c "import groundingdino,os; print(os.path.join(os.path.dirname(groundingdino.__file__),'config','GroundingDINO_SwinT_OGC.py'))")
export GROUNDING_DINO_CONFIG="$GD"
export GROUNDING_DINO_WEIGHTS=data/groundingdino_swint_ogc.pth
export MOBILE_SAM_CHECKPOINT=data/mobile_sam.pt
export CLASSES_PATH=vlfm/vlm/classes.txt
export HF_HOME=/shared/cache/huggingface
export TRANSFORMERS_CACHE=/shared/cache/huggingface

nohup python -m vlfm.vlm.grounding_dino --port 12181 > "$VLM_LOG/gd_batch.log" 2>&1 &
nohup python -m vlfm.vlm.blip2itm --port 12182 > "$VLM_LOG/blip_batch.log" 2>&1 &
nohup python -m vlfm.vlm.sam --port 12183 > "$VLM_LOG/sam_batch.log" 2>&1 &
nohup python -m vlfm.vlm.yolov7 --port 12184 > "$VLM_LOG/yolo_batch.log" 2>&1 &

ready=0
for i in $(seq 1 120); do
  c=0
  for p in 12181 12182 12183 12184; do
    (echo >/dev/tcp/127.0.0.1/$p) >/dev/null 2>&1 && c=$((c+1)) || true
  done
  if [ "$c" = 4 ]; then echo VLM_READY; ready=1; break; fi
  sleep 2
done
if [ "$ready" != 1 ]; then
  echo VLM_NOT_READY >&2
  tail -n 40 "$VLM_LOG"/*.log || true
  exit 1
fi

test -f data/dummy_policy.pth || python -m vlfm.utils.generate_dummy_policy

( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 20; done ) >"$MEM" &
MPID=$!
START=$(date +%s)
set +e
python -u -m vlfm.run habitat_baselines.test_episode_count=8 >"$LOG" 2>&1
EC=$?
set -e
END=$(date +%s)
kill $MPID 2>/dev/null || true
wait $MPID 2>/dev/null || true
PEAK=$(awk 'BEGIN{m=0}{if($1+0>m)m=$1+0}END{print m}' "$MEM")
WALL=$((END-START))
echo "exit=$EC wall=${WALL}s peak_mem=${PEAK}MiB" | tee "$OUT/summary.txt"
echo "batch,status,exit_code,wall_s,peak_mem_mib,logfile" > "$CSV"
if [ "$EC" = 0 ]; then ST=COMPLETED; else ST=CRASH; fi
echo "0..7,$ST,$EC,$WALL,$PEAK,$LOG" >> "$CSV"

pkill -f vlfm.vlm.grounding_dino 2>/dev/null || true
pkill -f vlfm.vlm.blip2itm 2>/dev/null || true
pkill -f vlfm.vlm.sam 2>/dev/null || true
pkill -f vlfm.vlm.yolov7 2>/dev/null || true
echo DONE
exit $EC
