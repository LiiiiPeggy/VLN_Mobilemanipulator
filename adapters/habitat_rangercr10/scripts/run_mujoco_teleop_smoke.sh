#!/usr/bin/env bash
# Short MuJoCo teleop PPO smoke (LocoManip_Lab), independent of Habitat.
# Pins: rangercr10-teleop @ 1973cb4, default ckpt model_5999.pt (stage45j).
set -euo pipefail
LOCO="${LOCOMANIP_ROOT:-/home/ubuntu/locomani/LocoManip_Lab}"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/mujoco_teleop_smoke}"
CKPT="${CKPT:-logs/rsl_rl/ranger_cr10_teleop/2026-10-29_19-12-08_stage45j_ppo/model_5999.pt}"
PYBIN="${PYBIN:-/home/ubuntu/miniconda3/envs/env_isaaclab5/bin/python}"
mkdir -p "$OUT"

cd "$LOCO"
COMMIT=$(git rev-parse HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "LocoManip $BRANCH @$COMMIT" | tee "$OUT/versions.txt"
echo "ckpt=$CKPT" | tee -a "$OUT/versions.txt"
echo "pybin=$PYBIN" | tee -a "$OUT/versions.txt"

"$PYBIN" - <<PY | tee "$OUT/smoke.log"
import json, sys, time
from pathlib import Path
import numpy as np

ROOT = Path("$LOCO")
sys.path.insert(0, str(ROOT / "mujoco/deploy"))
sys.path.insert(0, str(ROOT / "mujoco/deploy/deploy_mujoco"))

from ranger_cr10.teleop_eval import Sim, BaseCommandFilter, ee_command_from_offset  # type: ignore
from ranger_cr10.ranger_policy import NUM_OBS, NUM_ACTIONS, OBS_HISTORY, ARM_DEFAULT  # type: ignore

ckpt = ROOT / "$CKPT"
assert ckpt.exists(), ckpt
filt = BaseCommandFilter(0.02, 0.02, False, 0.0)
sim = Sim(str(ckpt), filt)
sim.reset()
obs0 = sim.obs.push(sim.last_action, (0.0, 0.0), sim.ee_cmd)
assert obs0.shape == (NUM_OBS,), (obs0.shape, NUM_OBS)
assert NUM_ACTIONS == 8 and OBS_HISTORY == 3

# base-only: vx command
sim.set_commands(0.2, 0.0, ee_command_from_offset((0, 0, 0), (0, 0, 0)))
base_stats = []
t0 = time.time()
for _ in range(30):  # 3 s @ 10 Hz
    s = sim.step()
    base_stats.append({"act_vx": s["act_vx"], "act_wz": s["act_wz"], "ee_pos": s["ee_pos"], "ee_ori": s["ee_ori"]})

# arm-ish: EE offset command, base zero
sim.reset()
sim.set_commands(0.0, 0.0, ee_command_from_offset((0.05, 0.0, 0.05), (0, 0, 0)))
arm_stats = []
for _ in range(30):
    s = sim.step()
    arm_stats.append({"act_vx": s["act_vx"], "act_wz": s["act_wz"], "ee_pos": s["ee_pos"], "ee_ori": s["ee_ori"]})

# combined
sim.reset()
sim.set_commands(0.15, 0.2, ee_command_from_offset((0.0, 0.05, 0.0), (0, 0, 0)))
combo = []
for _ in range(30):
    s = sim.step()
    combo.append({"act_vx": s["act_vx"], "act_wz": s["act_wz"], "ee_pos": s["ee_pos"], "ee_ori": s["ee_ori"]})

elapsed = time.time() - t0
summary = {
    "status": "ok",
    "num_obs": NUM_OBS,
    "num_actions": NUM_ACTIONS,
    "obs_history": OBS_HISTORY,
    "policy_hz": 10,
    "ckpt": str(ckpt),
    "arm_default": list(map(float, ARM_DEFAULT)),
    "elapsed_sec": elapsed,
    "base_tail": base_stats[-1],
    "arm_tail": arm_stats[-1],
    "combo_tail": combo[-1],
}
Path("$OUT/summary.json").write_text(json.dumps(summary, indent=2, default=float))
print(json.dumps(summary, indent=2, default=float))
PY
