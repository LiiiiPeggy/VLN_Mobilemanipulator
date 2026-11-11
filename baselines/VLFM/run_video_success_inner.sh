#!/usr/bin/env bash
# Runs inside vln-vlfm. Re-eval first N episodes with video_option=disk.
set -eo pipefail
N_EP="${1:-6}"
OUT=/media/ubuntu/D/VLN_shared/runs/VLFM_video/video_success_20261105
VLM_LOG="$OUT/vlm_servers"
VIDEO_DIR="$OUT/video_dir"
mkdir -p "$OUT" "$VLM_LOG" "$VIDEO_DIR"
LOG="$OUT/eval_video.log"
MEM="$OUT/eval_video.mem"

cd /workspace/VLFM

# Kill only matching python module processes (not this bash script).
pkill -f '[p]ython -m vlfm.vlm.grounding_dino' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.blip2itm' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.sam' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.yolov7' 2>/dev/null || true
sleep 1

GD=$(python -c "import groundingdino,os; print(os.path.join(os.path.dirname(groundingdino.__file__),'config','GroundingDINO_SwinT_OGC.py'))")
export GROUNDING_DINO_CONFIG="$GD"
export GROUNDING_DINO_WEIGHTS=data/groundingdino_swint_ogc.pth
export MOBILE_SAM_CHECKPOINT=data/mobile_sam.pt
export CLASSES_PATH=vlfm/vlm/classes.txt
export HF_HOME=/shared/cache/huggingface
export TRANSFORMERS_CACHE=/shared/cache/huggingface

nohup python -m vlfm.vlm.grounding_dino --port 12181 > "$VLM_LOG/gd.log" 2>&1 &
nohup python -m vlfm.vlm.blip2itm --port 12182 > "$VLM_LOG/blip.log" 2>&1 &
nohup python -m vlfm.vlm.sam --port 12183 > "$VLM_LOG/sam.log" 2>&1 &
nohup python -m vlfm.vlm.yolov7 --port 12184 > "$VLM_LOG/yolo.log" 2>&1 &

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
python -u -m vlfm.run \
  habitat_baselines.test_episode_count="$N_EP" \
  habitat_baselines.video_dir="$VIDEO_DIR" \
  habitat_baselines.eval.video_option='["disk"]' \
  >"$LOG" 2>&1
EC=$?
set -e
END=$(date +%s)
kill $MPID 2>/dev/null || true
wait $MPID 2>/dev/null || true
PEAK=$(awk 'BEGIN{m=0}{if($1+0>m)m=$1+0}END{print m}' "$MEM")
echo "exit=$EC wall=$((END-START))s peak=${PEAK}MiB n_ep=$N_EP" | tee "$OUT/summary.txt"

mkdir -p "$OUT/demo"
shopt -s nullglob
SUCC=0
for f in "$VIDEO_DIR"/*.mp4; do
  bn=$(basename "$f")
  if echo "$bn" | grep -qE 'success=1'; then
    cp -f "$f" "$OUT/demo/"
    SUCC=$((SUCC+1))
  fi
done
ls -lh "$VIDEO_DIR"/*.mp4 2>/dev/null | tee "$OUT/video_list.txt" || true
echo "success_videos=$SUCC" | tee -a "$OUT/summary.txt"

pkill -f '[p]ython -m vlfm.vlm.grounding_dino' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.blip2itm' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.sam' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.yolov7' 2>/dev/null || true
echo DONE
exit $EC
