#!/usr/bin/env bash
# Short open-band ApexNav episodes on Top-5 HM3D scenes (adapter-only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
MAX_STEPS="${MAX_STEPS:-50}"
GPU="${GPU:-0}"
PROFILE="${INFLATION_PROFILE:-legacy018}"

# scene|category|episode_id|tag
CASES=(
  "eF36g7L6Z9M|chair|4|ef36"
  "LT9Jq6dN3Ea|chair|3|lt9"
  "k1cupFYWXJ6|chair|1|k1cup"
)

mkdir -p "$OUT_ROOT"
SUMMARY="$OUT_ROOT/top5_openband_batch_$(date +%Y%m%d_%H%M%S).jsonl"
: > "$SUMMARY"

for case in "${CASES[@]}"; do
  IFS='|' read -r SCENE CAT EP TAG <<<"$case"
  RUN_ID="real_wide_${TAG}_openband_$(date +%Y%m%d_%H%M%S)"
  echo "===== $RUN_ID scene=$SCENE cat=$CAT ep=$EP ====="
  docker exec -u root vln-rangercr10 bash -lc \
    'pkill -9 -f "roscore -p 11312" 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true' || true
  set +e
  INFLATION_PROFILE="$PROFILE" SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" GPU="$GPU" RUN_ID="$RUN_ID" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
from collections import Counter
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {"run_id": "$RUN_ID", "scene": "$SCENE", "category": "$CAT", "episode_id": "$EP", "rc": int("$rc")}
sum_p = run / "summary.json"
if sum_p.is_file():
    s = json.load(open(sum_p))
    acts_p = run / "actions.jsonl"
    expl = []
    if acts_p.is_file():
        acts = [json.loads(l) for l in acts_p.read_text().splitlines() if l.strip()]
        expl = [a for a in acts if a.get("phase")=="explore_planner"]
    row.update({
        "status": s.get("status"),
        "termination": s.get("termination"),
        "error": s.get("error"),
        "n_explore": s.get("n_explore_planner_actions"),
        "entered_explore": s.get("entered_callActionPlanner"),
        "adapted_episode": s.get("adapted_episode"),
        "spawn_offset_m": (s.get("spawn") or {}).get("offset_from_episode_m"),
        "spawn_nav_clearance_m": (s.get("spawn") or {}).get("nav_clearance_m"),
        "explore_actions": dict(Counter(a.get("name") for a in expl)),
        "map": (s.get("online_grid_map") or {}).get("stats"),
        "success_claimed": s.get("success_claimed"),
        "dist_goal_eval": s.get("final_distance_to_goal_eval_only"),
    })
else:
    row["error"] = "missing_summary"
print(json.dumps(row))
PY
  echo "----- done $RUN_ID rc=$rc -----"
done
echo "SUMMARY=$SUMMARY"
cat "$SUMMARY"
