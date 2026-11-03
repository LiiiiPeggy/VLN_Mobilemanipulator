#!/usr/bin/env bash
# Habitat kinematic camera / LOOK diagnostics (no PPO, no LocoManip edits).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/camera_view_diag_$(date +%Y%m%d_%H%M%S)}"
GPU="${GPU:-0}"
bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10
docker exec \
  -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  vln-rangercr10 bash -lc \
  "source /opt/ros/noetic/setup.bash; python -m src.camera_view_diag --out_dir '$OUT' --gpu $GPU"
docker exec vln-rangercr10 chown -R 1000:1000 "$OUT" || true
echo "OUT=$OUT"
ls -la "$OUT" | head
