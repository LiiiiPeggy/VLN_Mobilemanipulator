#!/usr/bin/env bash
# ################################
# Host-side teleop-PPO LOOK bundle (MuJoCo). Habitat container only syncs joints.
# Writes look_up.json / look_down.json / look_level.json under --out_dir.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOCO_ROOT="${LOCO_ROOT:-/home/ubuntu/locomani/LocoManip_Lab}"
POLICY="${PPO_LOOK_CKPT:-models/ranger_cr10/model_9999.pt}"
OUT_DIR="${PPO_LOOK_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_look_bundle_model9999}"
PY="${PPO_HOST_PYTHON:-/home/ubuntu/miniconda3/envs/env_isaaclab5/bin/python}"
Z_HOLD="${PPO_LOOK_Z_HOLD:-0.40}"

export PYTHONPATH="${ROOT}/adapters/habitat_rangercr10:${PYTHONPATH:-}"
mkdir -p "$OUT_DIR"
echo "[ppo_look] policy=$POLICY out=$OUT_DIR python=$PY"
"$PY" -m src.ppo_mujoco_raise \
  --mode look_bundle \
  --policy "$POLICY" \
  --loco_root "$LOCO_ROOT" \
  --z_hold "$Z_HOLD" \
  --out_dir "$OUT_DIR"
echo "[ppo_look] done → $OUT_DIR"
ls -la "$OUT_DIR"
