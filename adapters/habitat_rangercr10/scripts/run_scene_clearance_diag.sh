#!/usr/bin/env bash
# Offline GT navmesh clearance screening for Ranger+CR10 (does NOT start ApexNav).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
GPU="${GPU:-0}"
OUT="${OUT_ROOT:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/scene_clearance}"
MAX="${MAX_SCENES:-0}"
IDS="${SCENE_IDS:-}"
bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10
docker exec \
  -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  vln-rangercr10 bash -lc \
  "source /opt/ros/noetic/setup.bash; python -m src.scene_clearance_diag --gpu $GPU --out_root '$OUT' --max_scenes $MAX --scene_ids '$IDS'"
docker exec vln-rangercr10 chown -R 1000:1000 "$OUT" || true
echo "OUT=$OUT"
ls -la "$OUT" | head
