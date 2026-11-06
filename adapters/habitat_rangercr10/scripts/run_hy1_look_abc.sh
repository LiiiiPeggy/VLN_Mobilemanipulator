#!/usr/bin/env bash
# HY1 A/B/C chassis-look contrast (experimental; default deploy unchanged).
# A: CHASSIS_LOOK_MODE=none
# B: budget_match (extra pubs/wait at raised forward pose)
# C: chassis_ground (LOOK_DOWN joint3−0.60 then restore; same pub budget as B)
# Fixed before run: EXTRA_PUBS=40 @ 4 Hz; no yaw-step / ground / planner changes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
RAISE="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json"
FORCE="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_hy1_openband_20261105_113724/start_pose.json"
unset FORCE_SPAWN_JSON PPO_RAISE_JSON SCENE_FILTER CATEGORY_FILTER EPISODE_ID || true
N_REPEATS="${N_REPEATS:-5}"
EXTRA_PUBS="${CHASSIS_LOOK_EXTRA_PUBS:-40}"
EXTRA_HZ="${CHASSIS_LOOK_EXTRA_HZ:-4}"
STAMP="$(date +%Y%m%d_%H%M%S)"
SUMMARY="$OUT_ROOT/hy1_look_abc_${STAMP}.jsonl"
: > "$SUMMARY"
echo "SUMMARY=$SUMMARY scheme: EXTRA_PUBS=$EXTRA_PUBS HZ=$EXTRA_HZ"

hard_reset() {
  docker exec -u root vln-rangercr10 bash -lc '
    pkill -9 -f "roscore -p 11312" 2>/dev/null || true
    pkill -9 -f exploration_node 2>/dev/null || true
    pkill -9 -f "roslaunch .*exploration_rangercr10" 2>/dev/null || true
    pkill -9 -f "python -m vlm" 2>/dev/null || true
    sleep 2; true
  ' || true
}

run_one() {
  local group="$1" mode="$2" i="$3"
  local RUN_ID="real_s070_hy1_look_${group}_r${i}_${STAMP}"
  echo "===== $group/$mode repeat $i $RUN_ID ====="
  hard_reset
  set +e
  CHASSIS_LOOK_MODE="$mode" CHASSIS_LOOK_EXTRA_PUBS="$EXTRA_PUBS" CHASSIS_LOOK_EXTRA_HZ="$EXTRA_HZ" \
  INFLATION_PROFILE=legacy018 SCENE_FILTER=HY1NcmCgn3n CATEGORY_FILTER=chair EPISODE_ID=3 \
    MAX_STEPS=50 MAX_EXPLORE_ACTIONS=20 GPU="${GPU:-0}" RUN_ID="$RUN_ID" \
    ROBOT_SCALE=0.7 FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="$RAISE" \
    PLAN_DIAG_ENABLE=true PIPELINE_DIAG_ENABLE=true \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  local rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json, math
from pathlib import Path
from collections import Counter
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {"group": "$group", "look_mode": "$mode", "repeat": int("$i"), "run_id": "$RUN_ID", "rc": int("$rc")}
s = json.loads((run/"summary.json").read_text()) if (run/"summary.json").is_file() else {}
burst = json.loads((run/"chassis_look_burst.json").read_text()) if (run/"chassis_look_burst.json").is_file() else {}
acts = [json.loads(l) for l in (run/"actions.jsonl").read_text().splitlines() if l.strip()] if (run/"actions.jsonl").is_file() else []
expl = [a for a in acts if a.get("phase")=="explore_planner"]
pipe, plans = [], []
if (run/"native_diag"/"map_pipeline_diag.jsonl").is_file():
  pipe=[json.loads(l) for l in (run/"native_diag"/"map_pipeline_diag.jsonl").read_text().splitlines() if l.strip()]
if (run/"native_diag"/"native_plan_diag.jsonl").is_file():
  plans=[json.loads(l) for l in (run/"native_diag"/"native_plan_diag.jsonl").read_text().splitlines() if l.strip()]
depth_before=None
if plans and pipe:
  t0=plans[0].get("stamp")
  depth_before=sum(1 for f in pipe if f.get("stamp",0)<=t0)
fp=plans[0] if plans else {}
# net disp from plan chassis first/last
disp=None
if len(plans)>=2:
  a=plans[0]["chassis_start"]; b=plans[-1]["chassis_start"]
  disp=math.hypot(b[0]-a[0], b[1]-a[1])
elif len(plans)==1:
  disp=0.0
# selected path exemption from first successful candidate if any
relied=fp.get("any_success_path_relied_near_start_exemption")
row.update({
  "burst": burst,
  "termination": s.get("termination"),
  "n_explore": len(expl),
  "explore_actions": dict(Counter(a.get("name") for a in expl)),
  "depth_frames_before_first_plan": depth_before,
  "depth_frames_total": len(pipe),
  "first_plan_result": fp.get("result"),
  "first_start_raw": fp.get("start_raw_occ"),
  "free_within_0p3": fp.get("free_within_0p3"),
  "unk_within_0p3": fp.get("unk_within_0p3"),
  "nearest_free_m": fp.get("nearest_free_m"),
  "path_relied_exemption": relied,
  "n_NO_PASSABLE": sum(1 for p in plans if p.get("result")=="NO_PASSABLE_FRONTIER"),
  "action_timeout": s.get("termination")=="planner_action_timeout",
  "explore_budget_done": s.get("termination")=="explore_budget_exhausted",
  "net_disp_m": disp,
  "note_blocked0_not_footprint_safe": True,
})
print(json.dumps(row))
PY
}

# Paired repeats: for each i, run A then B then C
for i in $(seq 1 "$N_REPEATS"); do
  run_one A none "$i"
  run_one B budget_match "$i"
  run_one C chassis_ground "$i"
done
echo "DONE $SUMMARY"
cat "$SUMMARY"
