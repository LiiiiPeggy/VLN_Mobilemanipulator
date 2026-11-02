#!/usr/bin/env bash
# Bounded ApexNav-action closed loop on native Habitat Ranger (kinematic).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_loop}"
STEPS="${STEPS:-16}"
GPU="${GPU:-0}"

bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10

set +e
docker exec -e PYTHONPATH="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10" \
  vln-rangercr10 bash -lc "python -m src.apexnav_bridge --out_dir '$OUT' --max_steps $STEPS --gpu $GPU"
rc=$?
set -e

if [[ ! -f "$OUT/summary.json" ]]; then
  echo "ERROR: missing summary (rc=$rc)" >&2
  exit "${rc:-1}"
fi
python3 - <<PY
import json,sys
s=json.load(open("$OUT/summary.json"))
rc=int("$rc")
ok = s.get("status")=="ok" and (rc==0 or rc==134)
print("status=", s.get("status"), "n_steps=", s.get("n_steps"), "container_rc=", rc, "accept=", ok)
sys.exit(0 if ok else 1)
PY
