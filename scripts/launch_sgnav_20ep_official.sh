#!/usr/bin/env bash
# SG-Nav 20ep on MP3D with official habitat navmesh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export STAMP="${STAMP:-$(date +%Y%m%d_%H%M%S)}"
export SGNAV_NUM_EPISODES="${SGNAV_NUM_EPISODES:-20}"
export SPLIT_L="${SPLIT_L:-0}"
export SPLIT_R="${SPLIT_R:-1}"
# Prefer D disk; fall back to repo runs if not writable
if mkdir -p "/media/ubuntu/D/VLN_shared/runs/SG-Nav/smoke_${STAMP}" 2>/dev/null; then
  export OUT_HOST="/media/ubuntu/D/VLN_shared/runs/SG-Nav"
else
  export OUT_HOST="${ROOT}/runs/SG-Nav"
  mkdir -p "${OUT_HOST}/smoke_${STAMP}"
fi
echo "$STAMP" > "${ROOT}/runs/SG-Nav/latest_stamp_sg20.txt"
LOG="${ROOT}/runs/SG-Nav/smoke_launch_${STAMP}_sg20.log"
echo "STAMP=${STAMP} OUT_HOST=${OUT_HOST} N=${SGNAV_NUM_EPISODES}" | tee "$LOG"
bash "${ROOT}/scripts/run_sgnav_smoke.sh" >>"$LOG" 2>&1
echo "DONE see $LOG"
