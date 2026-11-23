#!/usr/bin/env bash
# ################################
# Host-side teleop-PPO chassis unit segments (MuJoCo).
# Writes move_forward.json / turn_left.json / turn_right.json under --out_dir.
# Habitat episode replays body-frame ΔSE2 via probe_base_motion (no HM3D in MuJoCo).
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOCO_ROOT="${LOCO_ROOT:-/home/ubuntu/locomani/LocoManip_Lab}"
POLICY="${PPO_CHASSIS_CKPT:-${PPO_LOOK_CKPT:-models/ranger_cr10/model_9999.pt}}"
OUT_DIR="${PPO_CHASSIS_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_chassis_bundle_model9999}"
PY="${PPO_HOST_PYTHON:-/home/ubuntu/miniconda3/envs/env_isaaclab5/bin/python}"
Z_HOLD="${PPO_CHASSIS_Z_HOLD:-${PPO_LOOK_Z_HOLD:-0.40}}"

export PYTHONPATH="${ROOT}/adapters/habitat_rangercr10:${PYTHONPATH:-}"
mkdir -p "$OUT_DIR"
echo "[ppo_chassis] policy=$POLICY out=$OUT_DIR python=$PY z_hold=$Z_HOLD"
"$PY" -m src.ppo_mujoco_raise \
  --mode chassis_bundle \
  --policy "$POLICY" \
  --loco_root "$LOCO_ROOT" \
  --z_hold "$Z_HOLD" \
  --out_dir "$OUT_DIR"
echo "[ppo_chassis] done → $OUT_DIR"
ls -la "$OUT_DIR"
