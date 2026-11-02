#!/usr/bin/env bash
# Probe Teleop PPO interface against Habitat kinematic env (no false success).
# Keeps stage45j model_5999.pt as pinned baseline; does not swap to 4.8.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOCO="${LOCOMANIP_ROOT:-/home/ubuntu/locomani/LocoManip_Lab}"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_habitat_probe}"
CKPT="${CKPT:-logs/rsl_rl/ranger_cr10_teleop/2026-10-29_19-12-08_stage45j_ppo/model_5999.pt}"
PYBIN="${PYBIN:-/home/ubuntu/miniconda3/envs/env_isaaclab5/bin/python}"
mkdir -p "$OUT"

set +e
"$PYBIN" - <<'PY' >"$OUT/probe.log" 2>&1
import json, sys
from pathlib import Path
import numpy as np

ROOT = Path("/home/ubuntu/locomani/LocoManip_Lab")
CKPT = Path("logs/rsl_rl/ranger_cr10_teleop/2026-10-29_19-12-08_stage45j_ppo/model_5999.pt")
OUT = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_habitat_probe")
sys.path.insert(0, str(ROOT / "mujoco/deploy"))
sys.path.insert(0, str(ROOT / "mujoco/deploy/deploy_mujoco"))
from ranger_cr10.ranger_policy import (  # type: ignore
    NUM_OBS, NUM_ACTIONS, OBS_HISTORY, load_actor, act, ARM_DEFAULT, ACTION_SCALE
)

ckpt = ROOT / CKPT
assert ckpt.exists(), ckpt
actor, kind = load_actor(str(ckpt))
obs = np.zeros((NUM_OBS,), dtype=np.float32)
raw = act(actor, obs)
assert raw.shape == (NUM_ACTIONS,), raw.shape

gaps = [
    "Habitat kinematic env does not expose Isaac/MuJoCo matching 117-D terms (base_ang_vel, joint_vel scales, projected gravity history).",
    "8-D action [vx,wz,j1..j6] needs ChassisAction wheel mapping; Habitat demo currently sets SE(2)+arm joints directly (kinematic_state_set).",
    "10 Hz decimation / base command filter not wired into Habitat step loop yet.",
]
summary = {
    "status": "probe_only_not_integrated",
    "pinned_ckpt": str(ckpt),
    "ckpt_kind": kind,
    "num_obs": NUM_OBS,
    "num_actions": NUM_ACTIONS,
    "obs_history": OBS_HISTORY,
    "zero_obs_action_shape": list(raw.shape),
    "zero_obs_action_sample": raw.astype(float).tolist(),
    "arm_default": list(map(float, ARM_DEFAULT)),
    "action_scale": ACTION_SCALE,
    "habitat_integration": "blocked_by_observation_mismatch",
    "gaps": gaps,
    "note": "Do not treat this as PPO-in-Habitat success. MuJoCo smoke remains the validated PPO path.",
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
sys.exit(2)
PY
rc=$?
set -e
cat "$OUT/probe.log"
if [[ "$rc" -eq 2 && -f "$OUT/summary.json" ]]; then
  echo "PPO probe recorded gaps (expected interpreter rc=2; script exits 0)."
  exit 0
fi
echo "PPO probe failed rc=$rc" >&2
exit "${rc:-1}"
