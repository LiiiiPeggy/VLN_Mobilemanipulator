#!/usr/bin/env bash
# Offline 7 FPS paper Demo from a finished apexnav_real run (white map + pose interp).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
RUN_DIR="${RUN_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/20261104_114652}"
GPU="${GPU:-0}"
bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10
docker exec \
  -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  vln-rangercr10 bash -lc \
  "source /opt/ros/noetic/setup.bash; python -m src.demo_7fps_from_run --run_dir '$RUN_DIR' --gpu $GPU"
docker exec vln-rangercr10 chown -R 1000:1000 "$RUN_DIR/demo" || true
MP4="$RUN_DIR/demo/apexnav_ranger_paper_demo_7fps.mp4"
echo "MP4=$MP4"
ffprobe -v error -select_streams v:0 \
  -show_entries stream=r_frame_rate,avg_frame_rate,nb_frames,width,height,duration \
  -of json "$MP4"
python3 - <<PY
import json
from pathlib import Path
p=Path("$RUN_DIR")/"demo"/"demo_7fps_rates.json"
print(p.read_text())
PY
