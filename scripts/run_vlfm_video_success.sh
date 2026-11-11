#!/usr/bin/env bash
# Host wrapper: VLFM first N val episodes with disk video; copy success=1 mp4s to demo/.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
OUT=/media/ubuntu/D/VLN_shared/runs/VLFM_video/video_success_20261105
HOST_STATUS="$ROOT/runs/VLFM/video_success_status.md"
N_EP="${1:-6}"
mkdir -p "$OUT" "$(dirname "$HOST_STATUS")"
chmod +x "$ROOT/baselines/VLFM/run_video_success_inner.sh"

docker exec -w /workspace/VLFM vln-vlfm bash /workspace/VLFM/run_video_success_inner.sh "$N_EP"

{
  echo "# VLFM video success — $(date '+%Y-%m-%d %H:%M %Z')"
  echo
  echo "## Verdict"
  n=$(ls "$OUT/demo"/*.mp4 2>/dev/null | wc -l || echo 0)
  if [ "${n:-0}" -gt 0 ]; then
    echo "**OK** — ${n} success demo mp4(s)"
  else
    echo "**CHECK** — see video_dir / log (success filename pattern)"
  fi
  echo
  echo '```'
  cat "$OUT/summary.txt" 2>/dev/null || true
  echo '```'
  echo
  echo "| Item | Path |"
  echo "|------|------|"
  echo "| Video dir | \`$OUT/video_dir\` |"
  echo "| Demo (success) | \`$OUT/demo/\` |"
  echo "| Log | \`$OUT/eval_video.log\` |"
} > "$HOST_STATUS"
echo "Wrote $HOST_STATUS"
ls -lh "$OUT/demo" 2>/dev/null || ls -lh "$OUT/video_dir" 2>/dev/null || true
