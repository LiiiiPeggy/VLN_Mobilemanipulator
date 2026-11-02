#!/usr/bin/env bash
# Run kinematic Ranger+CR10 Habitat demo in dedicated container (does not touch baselines).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/kinematic_demo}"
GPU="${GPU:-0}"
FRAMES="${FRAMES:-40}"

if ! docker ps --format '{{.Names}}' | grep -qx vln-rangercr10; then
  echo "ERROR: container vln-rangercr10 not running. Start it first." >&2
  exit 1
fi

docker exec -e PYTHONPATH="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:${PYTHONPATH:-}" \
  vln-rangercr10 bash -lc "
set -e
python -c 'import habitat_sim; assert habitat_sim.built_with_bullet, \"need bullet build\"'
python -m src.kinematic_demo --out_dir '$OUT' --num_frames $FRAMES --gpu $GPU
"
echo "Wrote $OUT"
