#!/usr/bin/env bash
# MuJoCo teleop-PPO raise (host) → Habitat 0.7× ApexNav episodes (docker).
# Tag: scaled_robot_proxy_070. Does not retrain PPO or edit baselines.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOCO="${LOCOMANIP_ROOT:-/home/ubuntu/locomani/LocoManip_Lab}"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
RAISE_OUT="${RAISE_OUT:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json}"
POLICY="${POLICY:-logs/rsl_rl/ranger_cr10_teleop/2026-11-03_16-30-44_stage410d_ppo/model_5999.pt}"
PYBIN="${PYBIN:-/home/ubuntu/miniconda3/envs/env_isaaclab5/bin/python}"
MAX_STEPS="${MAX_STEPS:-50}"
GPU="${GPU:-0}"
PROFILE="${INFLATION_PROFILE:-legacy018}"

mkdir -p "$(dirname "$RAISE_OUT")" "$OUT_ROOT"

echo "[1/2] MuJoCo teleop-PPO raise → $RAISE_OUT"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
export PYTHONPATH="$ROOT/adapters/habitat_rangercr10:${PYTHONPATH:-}"
"$PYBIN" -m src.ppo_mujoco_raise \
  --policy "$POLICY" \
  --loco_root "$LOCO" \
  --z_offset 0.40 \
  --hold_steps 40 \
  --ramp_steps 20 \
  --settle_steps 30 \
  --out "$RAISE_OUT"

# scene|category|episode_id|tag|force_spawn
CASES=(
  "yr17PDCnDDW|chair|0|yr17|/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_yr17_openband_20261105_012302/start_pose.json"
  "eF36g7L6Z9M|chair|4|ef36|/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_ef36_openband_20261105_124359/start_pose.json"
  "HY1NcmCgn3n|chair|3|hy1|/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_hy1_openband_20261105_113724/start_pose.json"
)

SUMMARY="$OUT_ROOT/ppo_raise_s070_batch_$(date +%Y%m%d_%H%M%S).jsonl"
: > "$SUMMARY"

echo "[2/2] Habitat ApexNav @ robot_scale=0.7 with PPO raise handover"
for case in "${CASES[@]}"; do
  IFS='|' read -r SCENE CAT EP TAG FORCE <<<"$case"
  RUN_ID="real_s070_pporaise_${TAG}_$(date +%Y%m%d_%H%M%S)"
  echo "===== $RUN_ID ====="
  docker exec -u root vln-rangercr10 bash -lc \
    'pkill -9 -f "roscore -p 11312" 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true' || true
  set +e
  INFLATION_PROFILE="$PROFILE" SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" GPU="$GPU" RUN_ID="$RUN_ID" \
    ROBOT_SCALE=0.7 FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="$RAISE_OUT" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
from collections import Counter
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {"run_id": "$RUN_ID", "tag": "$TAG", "rc": int("$rc"), "robot_scale": 0.7,
       "scale_tag": "scaled_robot_proxy_070", "ppo_raise": True}
sp = run / "camera_init_summary.json"
if sp.is_file():
    c = json.load(open(sp))
    h = c.get("habitat_handover") or {}
    row["tcp_agl_m"] = h.get("tcp_agl_m")
    row["d455_agl_m"] = h.get("d455_optical_agl_m")
    row["tcp_target_ok"] = h.get("tcp_target_ok")
    row["d455_level_ok"] = h.get("d455_level_ok")
    row["selected"] = c.get("selected")
sum_p = run / "summary.json"
if sum_p.is_file():
    s = json.load(open(sum_p))
    acts = []
    ap = run / "actions.jsonl"
    if ap.is_file():
        acts = [json.loads(l) for l in ap.read_text().splitlines() if l.strip()]
    expl = [a for a in acts if a.get("phase") == "explore_planner"]
    fwd = 0.25 * sum(1 for a in expl if a.get("name") == "MOVE_FORWARD")
    row.update({
        "termination": s.get("termination"),
        "entered_explore": s.get("entered_callActionPlanner"),
        "n_explore": s.get("n_explore_planner_actions"),
        "explore_actions": dict(Counter(a.get("name") for a in expl)),
        "forward_m": fwd,
        "map": (s.get("online_grid_map") or {}).get("stats"),
        "success_claimed": s.get("success_claimed"),
    })
print(json.dumps(row))
PY
done
echo "SUMMARY=$SUMMARY"
cat "$SUMMARY"
