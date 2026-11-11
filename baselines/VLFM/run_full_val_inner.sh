#!/usr/bin/env bash
# Inside vln-vlfm: full HM3D ObjectNav val (2000 ep), no video.
set -eo pipefail
N_EP="${1:-2000}"
STAMP="${2:-$(date +%Y%m%d_%H%M%S)}"
OUT="/media/ubuntu/D/VLN_shared/runs/VLFM_full/full_val_${STAMP}"
VLM_LOG="$OUT/vlm_servers"
mkdir -p "$OUT" "$VLM_LOG"
LOG="$OUT/eval_full.log"
MEM="$OUT/eval_full.mem"
PROGRESS="$OUT/progress.txt"

cd /workspace/VLFM

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
for i in $(seq 1 180); do
  c=0
  for p in 12181 12182 12183 12184; do
    (echo >/dev/tcp/127.0.0.1/$p) >/dev/null 2>&1 && c=$((c+1)) || true
  done
  if [ "$c" = 4 ]; then echo VLM_READY; ready=1; break; fi
  sleep 2
done
if [ "$ready" != 1 ]; then
  echo VLM_NOT_READY >&2
  tail -n 60 "$VLM_LOG"/*.log || true
  exit 1
fi

test -f data/dummy_policy.pth || python -m vlfm.utils.generate_dummy_policy

# Tail progress helper (Success rate lines)
( while true; do
    if [ -f "$LOG" ]; then
      last=$(grep -oE 'Success rate:[[:space:]]*[0-9.]+%[[:space:]]*\([0-9]+ out of [0-9]+\)' "$LOG" | tail -1 || true)
      avg=$(grep -E 'Average episode (success|spl):' "$LOG" | tail -4 || true)
      {
        echo "ts=$(date -Iseconds)"
        echo "last=$last"
        echo "$avg"
      } > "$PROGRESS"
    fi
    sleep 60
  done ) &
PPID_PROG=$!

( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 30; done ) >"$MEM" &
MPID=$!

START=$(date +%s)
echo "START n_ep=$N_EP out=$OUT" | tee "$OUT/summary.txt"
set +e
python -u -m vlfm.run \
  habitat_baselines.test_episode_count="$N_EP" \
  habitat_baselines.eval.video_option='[]' \
  >"$LOG" 2>&1
EC=$?
set -e
END=$(date +%s)
kill $MPID $PPID_PROG 2>/dev/null || true
wait $MPID 2>/dev/null || true
wait $PPID_PROG 2>/dev/null || true
PEAK=$(awk 'BEGIN{m=0}{if($1+0>m)m=$1+0}END{print m}' "$MEM")

SR=$(grep -E 'Average episode success:' "$LOG" | tail -1 | grep -oE '[0-9.]+' | tail -1 || true)
SPL=$(grep -E 'Average episode spl:' "$LOG" | tail -1 | grep -oE '[0-9.]+' | tail -1 || true)
{
  echo "exit=$EC wall=$((END-START))s peak=${PEAK}MiB n_ep=$N_EP"
  echo "avg_success=${SR:-}"
  echo "avg_spl=${SPL:-}"
} | tee "$OUT/summary.txt"

pkill -f '[p]ython -m vlfm.vlm.grounding_dino' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.blip2itm' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.sam' 2>/dev/null || true
pkill -f '[p]ython -m vlfm.vlm.yolov7' 2>/dev/null || true
echo DONE
exit $EC
