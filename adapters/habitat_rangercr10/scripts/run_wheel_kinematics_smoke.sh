#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/wheel_kinematics_smoke}"
GPU="${GPU:-0}"
mkdir -p "$OUT"
bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10
docker exec \
  -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  vln-rangercr10 bash -lc \
  "source /opt/ros/noetic/setup.bash; python -m src.wheel_kinematics_smoke --out_dir '$OUT' --gpu $GPU"
docker exec vln-rangercr10 chown -R 1000:1000 "$OUT" || true
python3 - <<PY
import json
from pathlib import Path
s=json.load(open("$OUT/summary.json"))
print("PASS" if s.get("pass") else "FAIL")
print({k:s[k] for k in s if k!="frames"})
PY
