#!/usr/bin/env bash
# Recovery runner: jobs from REPORT/_jobs_ab24b_recovery.tsv
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
REPORT="${REPORT_DIR:-$ROOT/reports/exec_collision_gimbal_20261116}"
# Prefer D-disk OUT; fall back to workspace reports/runs if host cannot write D.
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
if ! mkdir -p "$OUT_ROOT" 2>/dev/null || ! touch "$OUT_ROOT/.wtest" 2>/dev/null; then
  OUT_ROOT="$REPORT/runs"
fi
rm -f "$OUT_ROOT/.wtest" 2>/dev/null || true
mkdir -p "$OUT_ROOT"
BATCH_ID="${BATCH_ID:-ab24b_rec_$(date +%Y%m%d_%H%M%S)}"
JOBS="${JOBS:-$REPORT/_jobs_ab24b_recovery.tsv}"
SUMMARY="$REPORT/batch_${BATCH_ID}.jsonl"
: > "$SUMMARY"
echo "[recovery] OUT_ROOT=$OUT_ROOT"
echo "[recovery] jobs=$(wc -l <"$JOBS") batch=$BATCH_ID"
while IFS=$'\t' read -r EP_ID SCENE CAT EP FORCE; do
  RUN_ID="execgimbal_${BATCH_ID}_${EP_ID}"
  echo "===== $RUN_ID ====="
  docker exec -u root vln-rangercr10 bash -lc \
    'pkill -9 -f "roscore -p 11312" 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 2; true' || true
  set +e
  INFLATION_PROFILE=legacy018 \
    SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS=50 MAX_EXPLORE_ACTIONS=100 GPU="${GPU:-0}" \
    RUN_ID="$RUN_ID" ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal \
    FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON= \
    STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none SKIP_DEMO=1 \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {
  "batch_id": "$BATCH_ID", "run_id": "$RUN_ID", "episode_list_id": "$EP_ID",
  "scene": "$SCENE", "category": "$CAT", "episode_id": "$EP",
  "robot_scale": 0.7, "camera_mode": "fixed_base_gimbal",
  "executor_version": "kinematic_collision_v1.1", "rc": int("$rc"), "recovery": True,
}
sum_p = run / "summary.json"
if sum_p.is_file():
  s = json.load(open(sum_p))
  steps = []
  sp = run / "steps.jsonl"
  if sp.is_file():
    steps = [json.loads(l) for l in sp.read_text().splitlines() if l.strip()]
  expl = [st for st in steps if st.get("phase") == "explore_planner"]
  row.update({
    "status": s.get("status"), "termination": s.get("termination"),
    "n_steps": s.get("n_steps"), "n_explore": s.get("n_explore_planner_actions"),
    "near_goal": s.get("near_goal"),
    "initial_penetration": (s.get("initial_penetration") or {}).get("initial_penetration"),
    "n_blocked_exec": sum(1 for st in steps if (st.get("exec") or {}).get("blocked")),
    "n_truncated_exec": sum(1 for st in steps if (st.get("exec") or {}).get("truncated")),
    "sum_moved_m": sum(float((st.get("exec") or {}).get("moved_m") or 0) for st in steps),
    "sr_proxy": any(
      ((st.get("exec") or {}).get("action_name") == "STOP" or st.get("raw_action") == 0)
      and st.get("distance_to_goal_eval_only") is not None
      and float(st.get("distance_to_goal_eval_only")) <= 1.0
      for st in expl
    ),
  })
else:
  row["status"] = "missing_summary"
print(json.dumps(row), flush=True)
PY
done < "$JOBS"
echo "$BATCH_ID" > "$REPORT/latest_recovery_batch_id.txt"
echo "[recovery] done $BATCH_ID"
