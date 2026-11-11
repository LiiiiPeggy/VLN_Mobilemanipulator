#!/usr/bin/env bash
# Host: VLFM full HM3D ObjectNav val (default 2000 ep), no video.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
N_EP="${1:-2000}"
STAMP="${2:-$(date +%Y%m%d_%H%M%S)}"
OUT="/media/ubuntu/D/VLN_shared/runs/VLFM_full/full_val_${STAMP}"
HOST_STATUS="$ROOT/runs/VLFM/full_val_status.md"
mkdir -p "$OUT" "$(dirname "$HOST_STATUS")" /media/ubuntu/D/VLN_shared/runs/VLFM_full
chmod +x "$ROOT/baselines/VLFM/run_full_val_inner.sh"
echo "$OUT" > /media/ubuntu/D/VLN_shared/runs/VLFM_full/LATEST_OUT.txt
echo "$STAMP" > /media/ubuntu/D/VLN_shared/runs/VLFM_full/LATEST_STAMP.txt

# Pointer for live progress
{
  echo "# VLFM full val — started $(date '+%Y-%m-%d %H:%M %Z')"
  echo
  echo "| Item | Value |"
  echo "|------|-------|"
  echo "| Episodes | $N_EP |"
  echo "| Output | \`$OUT\` |"
  echo "| Progress | \`$OUT/progress.txt\` |"
  echo "| Log | \`$OUT/eval_full.log\` |"
  echo
  echo "Status: **RUNNING**"
} > "$HOST_STATUS"

docker exec -w /workspace/VLFM vln-vlfm bash /workspace/VLFM/run_full_val_inner.sh "$N_EP" "$STAMP"
EC=$?

{
  echo "# VLFM full val — finished $(date '+%Y-%m-%d %H:%M %Z')"
  echo
  echo "## Verdict"
  if [ "$EC" = 0 ]; then echo "**OK** — EXIT 0"; else echo "**FAIL** — EXIT $EC"; fi
  echo
  echo '```'
  cat "$OUT/summary.txt" 2>/dev/null || true
  echo '```'
  echo
  echo "| Item | Path |"
  echo "|------|------|"
  echo "| Output | \`$OUT\` |"
  echo "| Log | \`$OUT/eval_full.log\` |"
  echo
  echo "Paper HM3D reference: SR 52.5% / SPL 30.4%"
} > "$HOST_STATUS"
exit $EC
