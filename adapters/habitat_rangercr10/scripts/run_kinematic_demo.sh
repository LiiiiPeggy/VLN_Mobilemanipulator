#!/usr/bin/env bash
# Native Habitat URDF kinematic demo in vln-rangercr10 (Bullet + fixed EGL ICD).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/kinematic_demo}"
GPU="${GPU:-0}"
FRAMES="${FRAMES:-24}"

bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10

if ! docker ps --format '{{.Names}}' | grep -qx vln-rangercr10; then
  echo "ERROR: container vln-rangercr10 not running." >&2
  exit 1
fi

set +e
docker exec -e PYTHONPATH="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10" \
  vln-rangercr10 bash -lc "
set -e
python -c 'import habitat_sim; assert habitat_sim.built_with_bullet, \"need bullet build\"'
python -m src.kinematic_demo --out_dir '$OUT' --num_frames $FRAMES --gpu $GPU
"
rc=$?
set -e

if [[ ! -f "$OUT/summary.json" ]]; then
  echo "ERROR: missing $OUT/summary.json (rc=$rc)" >&2
  exit "${rc:-1}"
fi
python3 - <<PY
import json,sys
s=json.load(open("$OUT/summary.json"))
rc=int("$rc")
# habitat-sim 0.3.1 often aborts (134) on Simulator.close after success
ok = s.get("status")=="ok" and (rc==0 or rc==134)
print("summary.status=", s.get("status"), "container_rc=", rc, "accept=", ok)
print("frames=", s.get("num_frames"), "contacts_final=", s.get("final_contacts"),
      "limits_ok=", s.get("arm_within_limits_final"))
sys.exit(0 if ok else 1)
PY
echo "Wrote $OUT"