#!/usr/bin/env bash
# ################################
# Validate teleop-PPO model_9999 can execute real reverse (negative vx).
# Writes calibrated segments under D-disk runs; no Habitat / no fake ΔSE2.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOCO_ROOT="${LOCO_ROOT:-/home/ubuntu/locomani/LocoManip_Lab}"
POLICY="${PPO_CHASSIS_CKPT:-${PPO_LOOK_CKPT:-models/ranger_cr10/model_9999.pt}}"
OUT_DIR="${PPO_REVERSE_OUT:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_reverse_validation_model9999}"
PY="${PPO_HOST_PYTHON:-/home/ubuntu/miniconda3/envs/env_isaaclab5/bin/python}"
Z_HOLD="${PPO_CHASSIS_Z_HOLD:-${PPO_LOOK_Z_HOLD:-0.40}}"
VX="${PPO_REVERSE_VX:--0.25}"

export PYTHONPATH="${ROOT}/adapters/habitat_rangercr10:${PYTHONPATH:-}"
mkdir -p "$OUT_DIR"
echo "[ppo_reverse] policy=$POLICY out=$OUT_DIR vx=$VX z_hold=$Z_HOLD"

"$PY" - <<PY
import json, hashlib, time
from pathlib import Path
from src.ppo_mujoco_raise import run_mujoco_chassis_segment, write_orient_report

out = Path("${OUT_DIR}")
policy = "${POLICY}"
loco = "${LOCO_ROOT}"
z_hold = float("${Z_HOLD}")
vx = float("${VX}")
targets = [0.15, 0.25, 0.40]
# ################################
# Extra long max_steps for 0.40 m capability probe.
# ################################
max_steps_by_t = {0.15: 40, 0.25: 50, 0.40: 80}
summary = {
    "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "policy": policy,
    "loco_root": loco,
    "z_hold": z_hold,
    "vel_cmd_vx": vx,
    "vel_cmd_wz": 0.0,
    "targets_m": targets,
    "note": "Real MuJoCo teleop-PPO reverse; not negated forward segment.",
    "trials": [],
}

ckpt = Path(policy)
if not ckpt.is_file():
    ckpt = Path(loco) / policy
raw = ckpt.read_bytes()
summary["policy_sha256"] = hashlib.sha256(raw).hexdigest()
summary["policy_resolved"] = str(ckpt)

for t in targets:
    tag = f"move_backward_{str(t).replace('.', 'p')}"
    # ################################
    # target_forward_m uses abs(path_m) stop in run_mujoco_chassis_segment.
    # ################################
    rep = run_mujoco_chassis_segment(
        policy=str(ckpt),
        loco_root=loco,
        vx=vx,
        wz=0.0,
        z_hold=z_hold,
        target_forward_m=float(t),
        target_yaw_rad=None,
        raise_ramp_steps=20,
        raise_hold_steps=25,
        max_steps=int(max_steps_by_t[t]),
        settle_steps=5,
        tag=tag,
    )
    path = write_orient_report(rep, out / f"{tag}.json")
    df = float(rep["delta_final"]["d_forward"])
    dl = float(rep["delta_final"]["d_left"])
    dy = float(rep["delta_final"]["d_yaw"])
    trial = {
        "tag": tag,
        "target_m": t,
        "file": str(path),
        "stop_reason": rep["control"]["stop_reason"],
        "n_policy_steps": rep["n_policy_steps"],
        "d_forward": df,
        "d_left": dl,
        "d_yaw": dy,
        "path_m": float(rep["path_m"]),
        "reverse_distance_m": float(-df) if df < 0 else float(df),
        "yaw_drift_rad": dy,
        "lateral_offset_m": dl,
        "arm_q_final": rep.get("arm_q_final"),
        "steer_q_final": rep.get("steer_q_final"),
        "wheel_q_final": rep.get("wheel_q_final"),
        "elapsed_wall_s": rep.get("elapsed_wall_s"),
        "ok_reverse": bool(df < -0.05),
    }
    summary["trials"].append(trial)
    print(json.dumps(trial, indent=2))

# ################################
# Unit segment for nav: prefer ~0.25 m reverse if ok; else best available.
# ################################
ok_trials = [t for t in summary["trials"] if t["ok_reverse"]]
pick = None
for t in ok_trials:
    if abs(t["target_m"] - 0.25) < 1e-6:
        pick = t
        break
if pick is None and ok_trials:
    pick = min(ok_trials, key=lambda r: abs(r["path_m"] - 0.25))

if pick is not None:
    src = Path(pick["file"])
    unit = json.loads(src.read_text())
    unit["tag"] = "move_backward"
    unit["control"] = dict(unit.get("control") or {})
    unit["control"]["nav_unit_from"] = pick["tag"]
    unit_path = out / "move_backward.json"
    unit_path.write_text(json.dumps(unit, indent=2) + "\n")
    # copy jsonl samples if present
    jl = src.with_suffix(".jsonl")
    if jl.is_file():
        (out / "move_backward.jsonl").write_text(jl.read_text())
    summary["nav_unit_segment"] = str(unit_path)
    summary["nav_unit_from"] = pick["tag"]
else:
    summary["nav_unit_segment"] = None
    summary["error"] = "no_reliable_reverse_segment"

summary["n_ok"] = sum(1 for t in summary["trials"] if t["ok_reverse"])
(out / "reverse_validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
# also mirror short index into repo reports
rep_idx = Path("${ROOT}/reports/hy1_reverse_planning/ppo_reverse_validation/summary.json")
rep_idx.parent.mkdir(parents=True, exist_ok=True)
rep_idx.write_text(json.dumps(summary, indent=2) + "\n")
print("SUMMARY", json.dumps({k: summary[k] for k in summary if k != "trials"}, indent=2))
print("n_ok", summary["n_ok"], "/", len(summary["trials"]))
PY

echo "[ppo_reverse] done → $OUT_DIR"
ls -la "$OUT_DIR"
