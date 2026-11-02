#!/usr/bin/env bash
# Hybrid kinematic demo: host MuJoCo FK/robot viz + vln-apexnav Habitat EE RGB-D.
# Does not modify baseline images/tags. Control mode = kinematic_state_set.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/hybrid_kinematic_demo}"
PYBIN="${PYBIN:-/home/ubuntu/miniconda3/envs/env_isaaclab5/bin/python}"
FRAMES="${FRAMES:-24}"
GPU="${GPU:-0}"
mkdir -p "$OUT"

export PYTHONPATH="$ROOT/adapters/habitat_rangercr10:${PYTHONPATH:-}"

echo "[1/3] MuJoCo FK + robot render → $OUT"
"$PYBIN" -m src.hybrid_kinematic_demo --mujoco_only --out_dir "$OUT" --num_frames "$FRAMES"

echo "[2/3] Habitat EE RGB-D via running vln-apexnav (working EGL; script on D mount)"
SCENE=/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb
RENDER_PY=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/habitat_ee_render.py
# habitat-sim 0.3.1 often SIGABRT on Simulator.close(); accept if summary written
set +e
docker exec vln-apexnav python "$RENDER_PY" "$OUT" "$OUT/fk_poses.json" "$SCENE" "$GPU"
hab_rc=$?
set -e
if [[ ! -f "$OUT/summary_habitat.json" ]]; then
  echo "Habitat pass failed (rc=$hab_rc)" >&2
  exit "$hab_rc"
fi
echo "Habitat pass summary ok (container rc=$hab_rc)"

echo "[3/3] Collage on host"
"$PYBIN" - <<PY
from pathlib import Path
from src.hybrid_kinematic_demo import make_collage
import json
out = Path("$OUT")
n = len(json.loads((out/"fk_poses.json").read_text()))
make_collage(out, n)
summary = {
  "status": "ok",
  "control_mode": "kinematic_state_set",
  "robot_mesh_in_habitat": False,
  "note": "Hybrid: MuJoCo robot mesh + Habitat EE RGB-D via FK. Not whole-body dynamics.",
  "out_dir": str(out),
  "num_frames": n,
  "mujoco": json.loads((out/"summary_mujoco.json").read_text()) if (out/"summary_mujoco.json").exists() else None,
  "habitat": json.loads((out/"summary_habitat.json").read_text()) if (out/"summary_habitat.json").exists() else None,
}
(out/"summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
PY

echo "Done → $OUT"
