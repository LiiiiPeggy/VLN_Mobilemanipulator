#!/usr/bin/env bash
# Stage 4.10d MuJoCo PPO short eval (does NOT modify LocoManip training code).
set -euo pipefail
unset OUT_DIR || true
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate env_isaaclab5
cd /home/ubuntu/locomani/LocoManip_Lab
OUT="${1:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_stage410d_mujoco_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
export PYTHONPATH=/home/ubuntu/locomani/LocoManip_Lab:${PYTHONPATH:-}
POLICY="${POLICY:-logs/rsl_rl/ranger_cr10_teleop/2026-11-03_16-30-44_stage410d_ppo/model_5999.pt}"
echo "OUT=$OUT"
echo "POLICY=$POLICY"
python -c 'import torch,mujoco; print("cuda", torch.cuda.is_available(), "dev", torch.cuda.device_count(), "mujoco", mujoco.__version__)'
# P0 suites: drift (zero-cmd / hold) + modes (base/arm/joint) + coverage on 4.10 safe box
python mujoco/deploy/deploy_mujoco/ranger_cr10/teleop_eval.py \
  --policy "$POLICY" --suite drift --out "$OUT" --tag stage410d \
  2>&1 | tee "$OUT/drift.log"
python mujoco/deploy/deploy_mujoco/ranger_cr10/teleop_eval.py \
  --policy "$POLICY" --suite modes --out "$OUT" --tag stage410d \
  2>&1 | tee "$OUT/modes.log"
python mujoco/deploy/deploy_mujoco/ranger_cr10/teleop_eval.py \
  --policy "$POLICY" --suite coverage --coverage_box 4.10 --out "$OUT" --tag stage410d \
  2>&1 | tee "$OUT/coverage.log"
# Optional self-collision if script exists
if [[ -f scripts/ranger_cr10/check_self_collision.py ]]; then
  python scripts/ranger_cr10/check_self_collision.py --help 2>&1 | tee "$OUT/self_collision_help.txt" || true
  python scripts/ranger_cr10/check_self_collision.py --box 4.10 --out "$OUT/self_collision.json" \
    2>&1 | tee "$OUT/self_collision.log" || true
elif [[ -f scripts/ranger_cr10/check_workspace_collision.py ]]; then
  python scripts/ranger_cr10/check_workspace_collision.py --box 4.10 --out "$OUT/self_collision.json" \
    2>&1 | tee "$OUT/self_collision.log" || true
fi
echo "$OUT" > "$OUT/OUT_PATH.txt"
ls -la "$OUT" | tee "$OUT/listing.txt"
echo "DONE OUT=$OUT"
