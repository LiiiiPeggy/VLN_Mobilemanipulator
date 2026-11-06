#!/usr/bin/env bash
# Serial HY1 fixed-pose baseline repeats (≥5). Full ROS/map reset between runs.
# Does NOT change lookaround / ground / inflation / A*. Experimental only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
# ################################
# Pin paths explicitly — do NOT inherit polluted FORCE_SPAWN_JSON from the
# parent shell (a prior yr17 export contaminated an earlier batch).
# ################################
RAISE="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json"
FORCE="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_hy1_openband_20261105_113724/start_pose.json"
unset FORCE_SPAWN_JSON PPO_RAISE_JSON SCENE_FILTER CATEGORY_FILTER EPISODE_ID || true
N_REPEATS="${N_REPEATS:-5}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BATCH_TAG="${BATCH_TAG:-hy1_base_rep}"
SUMMARY="$OUT_ROOT/${BATCH_TAG}_${STAMP}.jsonl"
: > "$SUMMARY"
echo "SUMMARY=$SUMMARY N_REPEATS=$N_REPEATS FORCE=$FORCE"
test -f "$FORCE" && test -f "$RAISE"

hard_reset() {
  docker exec -u root vln-rangercr10 bash -lc '
    pkill -9 -f "roscore -p 11312" 2>/dev/null || true
    pkill -9 -f exploration_node 2>/dev/null || true
    pkill -9 -f "roslaunch .*exploration_rangercr10" 2>/dev/null || true
    pkill -9 -f "python -m vlm" 2>/dev/null || true
    sleep 2
    true
  ' || true
}

for i in $(seq 1 "$N_REPEATS"); do
  RUN_ID="real_s070_${BATCH_TAG}_r${i}_${STAMP}"
  echo "===== repeat $i/$N_REPEATS $RUN_ID ====="
  hard_reset
  set +e
  INFLATION_PROFILE=legacy018 SCENE_FILTER=HY1NcmCgn3n CATEGORY_FILTER=chair EPISODE_ID=3 \
    MAX_STEPS=50 MAX_EXPLORE_ACTIONS=20 GPU="${GPU:-0}" RUN_ID="$RUN_ID" \
    ROBOT_SCALE=0.7 FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="$RAISE" \
    PLAN_DIAG_ENABLE=true PIPELINE_DIAG_ENABLE=true \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
from collections import Counter
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {"repeat": int("$i"), "run_id": "$RUN_ID", "rc": int("$rc"), "group": "A_baseline"}
s = json.loads((run/"summary.json").read_text()) if (run/"summary.json").is_file() else {}
meta = json.loads((run/"process_meta.json").read_text()) if (run/"process_meta.json").is_file() else {}
acts = []
if (run/"actions.jsonl").is_file():
  acts = [json.loads(l) for l in (run/"actions.jsonl").read_text().splitlines() if l.strip()]
expl = [a for a in acts if a.get("phase")=="explore_planner"]
pipe, plans = [], []
pp = run/"native_diag"/"map_pipeline_diag.jsonl"
pl = run/"native_diag"/"native_plan_diag.jsonl"
if pp.is_file():
  pipe = [json.loads(l) for l in pp.read_text().splitlines() if l.strip()]
if pl.is_file():
  plans = [json.loads(l) for l in pl.read_text().splitlines() if l.strip()]
depth_before = None
last_depth_stamp = pipe[-1].get("stamp") if pipe else None
last_pose_cam = pipe[-1].get("camera_pos") if pipe else None
map_updated = None
if plans and pipe:
  t0 = plans[0].get("stamp")
  depth_before = sum(1 for f in pipe if f.get("stamp", 0) <= t0)
  # frames with local update evidence: free_grids or rays
  map_updated = sum(1 for f in pipe if f.get("stamp", 0) <= t0 and (f.get("rays_into_occupancy") or 0) > 0)
elif pipe:
  depth_before = len(pipe)
fp = plans[0] if plans else {}
row.update({
  "git_sha_vln": meta.get("git_sha_vln"),
  "termination": s.get("termination"),
  "status": s.get("status"),
  "n_explore": len(expl),
  "explore_actions": dict(Counter(a.get("name") for a in expl)),
  "outcome_class": (
    "NO_PASSABLE" if any(p.get("result")=="NO_PASSABLE_FRONTIER" for p in plans[:1])
    else ("explore_budget" if s.get("termination")=="explore_budget_exhausted"
    else ("action_timeout" if s.get("termination")=="planner_action_timeout"
    else s.get("termination")))
  ),
  "depth_frames_total": len(pipe),
  "depth_frames_before_first_plan": depth_before,
  "depth_frames_with_rays_before_first_plan": map_updated,
  "last_depth_stamp": last_depth_stamp,
  "last_camera_pos_before_end": last_pose_cam,
  "first_plan": {
    "result": fp.get("result"),
    "start_raw_occ": fp.get("start_raw_occ"),
    "start_inflate": fp.get("start_inflate"),
    "free_within_0p3": fp.get("free_within_0p3"),
    "unk_within_0p3": fp.get("unk_within_0p3"),
    "nearest_free_m": fp.get("nearest_free_m"),
    "path_relied_near_start_exemption": fp.get("any_success_path_relied_near_start_exemption"),
    "n_reachable": fp.get("n_reachable_candidates"),
  } if fp else None,
  "plan_diag_n": len(plans),
  "n_NO_PASSABLE": sum(1 for p in plans if p.get("result")=="NO_PASSABLE_FRONTIER"),
})
print(json.dumps(row))
PY
done
echo "DONE $SUMMARY"
cat "$SUMMARY"
