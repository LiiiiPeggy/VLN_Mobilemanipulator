#!/usr/bin/env bash
# Compare ApexNav open-band episodes at robot_scale=0.7 vs prior 1.0× starts.
# Marks runs as scaled_robot_proxy_070 — NOT real Ranger scores.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
MAX_STEPS="${MAX_STEPS:-50}"
GPU="${GPU:-0}"
PROFILE="${INFLATION_PROFILE:-legacy018}"
ROBOT_SCALE="${ROBOT_SCALE:-0.7}"

# tag|scene|category|episode_id|force_spawn_json(from 1.0×)
CASES=(
  "yr17|yr17PDCnDDW|chair|0|/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_yr17_openband_20261105_012302/start_pose.json"
  "ef36|eF36g7L6Z9M|chair|4|/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_ef36_openband_20261105_124359/start_pose.json"
  "dd4b|Dd4bFSTQ8gi|chair|5|/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_ctrl_dd4b_chair5_20261105_001053/start_pose.json"
  "hy1|HY1NcmCgn3n|chair|3|/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_hy1_openband_20261105_113724/start_pose.json"
)

mkdir -p "$OUT_ROOT"
SUMMARY="$OUT_ROOT/scale070_compare_batch_$(date +%Y%m%d_%H%M%S).jsonl"
: > "$SUMMARY"

for case in "${CASES[@]}"; do
  IFS='|' read -r TAG SCENE CAT EP FORCE <<<"$case"
  RUN_ID="real_s070_${TAG}_openband_$(date +%Y%m%d_%H%M%S)"
  echo "===== $RUN_ID scale=$ROBOT_SCALE scene=$SCENE ep=$EP ====="
  docker exec -u root vln-rangercr10 bash -lc \
    'pkill -9 -f "roscore -p 11312" 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true' || true
  set +e
  INFLATION_PROFILE="$PROFILE" SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" GPU="$GPU" RUN_ID="$RUN_ID" \
    ROBOT_SCALE="$ROBOT_SCALE" FORCE_SPAWN_JSON="$FORCE" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
from collections import Counter
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {"run_id": "$RUN_ID", "tag": "$TAG", "scene": "$SCENE", "episode_id": "$EP",
       "robot_scale": float("$ROBOT_SCALE"), "scale_tag": "scaled_robot_proxy_070", "rc": int("$rc")}
sum_p = run / "summary.json"
if sum_p.is_file():
    s = json.load(open(sum_p))
    acts = []
    ap = run / "actions.jsonl"
    if ap.is_file():
        acts = [json.loads(l) for l in ap.read_text().splitlines() if l.strip()]
    expl = [a for a in acts if a.get("phase") == "explore_planner"]
    modes = Counter()
    for a in expl:
        for k, v in (a.get("expl_result") or {}).items() if isinstance(a.get("expl_result"), dict) else []:
            pass
    # planner modes from steps if present
    steps_p = run / "steps.jsonl"
    mode_c = Counter()
    fwd = 0.0
    if steps_p.is_file():
        for line in steps_p.read_text().splitlines():
            if not line.strip():
                continue
            st = json.loads(line)
            if st.get("phase") != "explore_planner":
                continue
            er = st.get("expl_result")
            if er is not None:
                mode_c[str(er)] += 1
            if st.get("planner_action_name") == "MOVE_FORWARD":
                fwd += 0.25
    row.update({
        "status": s.get("status"),
        "termination": s.get("termination"),
        "entered_explore": s.get("entered_callActionPlanner"),
        "n_explore": s.get("n_explore_planner_actions"),
        "explore_actions": dict(Counter(a.get("name") for a in expl)),
        "forward_m": fwd,
        "map": (s.get("online_grid_map") or {}).get("stats"),
        "scale_tag_summary": s.get("scale_tag"),
        "success_claimed": s.get("success_claimed"),
        "cam_height_target_m": (s.get("initial_camera") or {}).get("cam_height_target_m"),
    })
else:
    row["error"] = "missing_summary"
print(json.dumps(row))
PY
  echo "----- done $RUN_ID rc=$rc -----"
done
echo "SUMMARY=$SUMMARY"
cat "$SUMMARY"
