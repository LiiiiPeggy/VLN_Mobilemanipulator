#!/usr/bin/env bash
# Host: re-run MSGNav known-success episode (batch idx 2) with visualization + stitch mp4.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
OUT=/media/ubuntu/D/VLN_shared/runs/MSGNav_video/video_ep2_20261105
HOST_STATUS="$ROOT/runs/MSGNav/video_ep2_status.md"
mkdir -p "$OUT" "$(dirname "$HOST_STATUS")"

docker exec -w /workspace/MSGNav \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e HF_HOME=/shared/cache/huggingface \
  -e HUGGINGFACE_HUB_CACHE=/shared/cache/huggingface/hub \
  -e PYTHONUNBUFFERED=1 \
  vln-msgnav \
  bash -lc '
set -euo pipefail
OUT=/media/ubuntu/D/VLN_shared/runs/MSGNav_video/video_ep2_20261105
mkdir -p "$OUT"
LOG="$OUT/ep2_video.log"
MEM="$OUT/ep2_video.mem"
( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 20; done ) >"$MEM" &
MPID=$!
START=$(date +%s)
set +e
python -u run_hm3d_evaluation.py -cf cfg/eval_hm3d_video_ep2.yaml --specific 2 >"$LOG" 2>&1
EC=$?
set -e
END=$(date +%s)
kill $MPID 2>/dev/null || true
wait $MPID 2>/dev/null || true
PEAK=$(awk "BEGIN{m=0}{if(\$1+0>m)m=\$1+0}END{print m}" "$MEM")
SR=$(grep -oE "Success rate by distance:[[:space:]]*[0-9.]+" "$LOG" | grep -oE "[0-9.]+$" | tail -1 || true)
SPL=$(grep -oE "SPL by distance:[[:space:]]*[0-9.]+" "$LOG" | grep -oE "[0-9.]+$" | tail -1 || true)
EP_DIR=$(find "$OUT" -maxdepth 1 -type d -name "*_ep_*" | head -1 || true)
echo "exit=$EC sr=${SR:-} spl=${SPL:-} wall=$((END-START))s peak=${PEAK}MiB ep_dir=${EP_DIR:-}" | tee "$OUT/summary.txt"

# Prefer main-view RGB (last view index per step); fallback to top-down visualization.
DEMO_MP4="$OUT/msgnav_ep2_success_demo.mp4"
RGB_DIR=""
if [ -n "${EP_DIR:-}" ] && [ -d "$EP_DIR/rgb_views" ]; then
  RGB_DIR="$EP_DIR/rgb_views"
  # main angle is last view index — pick highest viewN per step
  TMP="$OUT/_demo_frames"
  rm -rf "$TMP" && mkdir -p "$TMP"
  python - <<PY
import glob, os, re, shutil
src = "$RGB_DIR"
dst = "$TMP"
files = sorted(glob.glob(os.path.join(src, "*.png")))
by_step = {}
for f in files:
    m = re.search(r"(\\d+)_view(\\d+)\\.png$", os.path.basename(f))
    if not m:
        continue
    step, view = int(m.group(1)), int(m.group(2))
    by_step.setdefault(step, []).append((view, f))
idx = 0
for step in sorted(by_step):
    view, f = max(by_step[step], key=lambda x: x[0])
    shutil.copy(f, os.path.join(dst, f"{idx:05d}.png"))
    idx += 1
print(f"frames={idx}")
PY
  if ls "$TMP"/*.png >/dev/null 2>&1; then
    ffmpeg -y -framerate 2 -i "$TMP/%05d.png" -c:v libx264 -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "$DEMO_MP4"
  fi
fi
if [ ! -f "$DEMO_MP4" ] && [ -n "${EP_DIR:-}" ] && [ -d "$EP_DIR/visualization" ]; then
  TMP="$OUT/_demo_frames_td"
  rm -rf "$TMP" && mkdir -p "$TMP"
  i=0
  for f in $(ls "$EP_DIR/visualization"/*.png | sort -V); do
    printf -v name "%05d.png" "$i"
    cp "$f" "$TMP/$name"
    i=$((i+1))
  done
  if [ "$i" -gt 0 ]; then
    ffmpeg -y -framerate 2 -i "$TMP/%05d.png" -c:v libx264 -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" "$DEMO_MP4"
  fi
fi
test -f "$DEMO_MP4" && echo "DEMO_OK $DEMO_MP4" || echo "DEMO_MISSING"
exit $EC
'

# Host-side status summary
{
  echo "# MSGNav video ep2 — $(date '+%Y-%m-%d %H:%M %Z')"
  echo
  echo "## Verdict"
  if [ -f "$OUT/msgnav_ep2_success_demo.mp4" ]; then
    echo "**OK** — demo mp4 written"
  else
    echo "**PARTIAL** — run finished but demo mp4 missing (see log)"
  fi
  echo
  echo '```'
  cat "$OUT/summary.txt" 2>/dev/null || true
  echo '```'
  echo
  echo "| Item | Path |"
  echo "|------|------|"
  echo "| Demo | \`$OUT/msgnav_ep2_success_demo.mp4\` |"
  echo "| Log | \`$OUT/ep2_video.log\` |"
  echo "| Summary | \`$OUT/summary.txt\` |"
} > "$HOST_STATUS"
echo "Wrote $HOST_STATUS"
ls -lh "$OUT/msgnav_ep2_success_demo.mp4" 2>/dev/null || true
