#!/usr/bin/env bash
# ################################
# Deployment baseline batch: robot_scale=0.7, camera_mode=fixed_base_gimbal,
# F0+expand0.3, denoise=none, ObjectHold/LabelMap unchanged, NO PPO.
# New execution protocol — not causally comparable to pre-fix trajectories.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LIST="${EPISODE_LIST:-$ROOT/reports/startup_prior_e2e_20261107/episode_list.json}"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/exec_collision_gimbal_20261116}"
SMOKE_ONLY="${SMOKE_ONLY:-0}"
MAX_STEPS="${MAX_STEPS:-50}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
GPU="${GPU:-0}"
PROFILE="${INFLATION_PROFILE:-legacy018}"
BATCH_ID="${BATCH_ID:-$(date +%Y%m%d_%H%M%S)}"
CAMERA_MODE="${CAMERA_MODE:-fixed_base_gimbal}"

mkdir -p "$REPORT_DIR" "$OUT_ROOT"
SUMMARY="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: > "$SUMMARY"

python3 - <<'PY' "$LIST" "$SMOKE_ONLY" >"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"
import json, sys
from pathlib import Path
doc = json.loads(Path(sys.argv[1]).read_text())
smoke_only = sys.argv[2] == "1"
eps = doc["smoke"] if smoke_only else doc["episodes"]
for ep in eps:
    print("\t".join([
        ep["id"],
        ep["scene_filter"],
        ep["category"],
        str(ep["episode_id"]),
        ep["force_spawn_json"],
    ]))
PY

echo "[baseline] jobs=$(wc -l <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv") camera=$CAMERA_MODE summary=$SUMMARY"

while IFS=$'\t' read -r EP_ID SCENE CAT EP FORCE; do
  TAG="$EP_ID"
  RUN_ID="execgimbal_${BATCH_ID}_${TAG}"
  echo "===== $RUN_ID ====="
  docker exec -u root vln-rangercr10 bash -lc \
    'pkill -9 -f "roscore -p 11312" 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true' || true
  set +e
  INFLATION_PROFILE="$PROFILE" \
    SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" GPU="$GPU" \
    RUN_ID="$RUN_ID" ROBOT_SCALE=0.7 CAMERA_MODE="$CAMERA_MODE" \
    FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="" \
    STARTUP_PRIOR_MODE=initial_footprint \
    STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none \
    SKIP_DEMO="${SKIP_DEMO:-1}" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$OUT_ROOT/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json
from pathlib import Path
run = Path("$OUT_ROOT") / "$RUN_ID"
row = {
    "batch_id": "$BATCH_ID",
    "run_id": "$RUN_ID",
    "episode_list_id": "$EP_ID",
    "scene": "$SCENE",
    "category": "$CAT",
    "episode_id": "$EP",
    "robot_scale": 0.7,
    "scale_tag": "scaled_robot_proxy_070",
    "camera_mode": "$CAMERA_MODE",
    "executor_version": "kinematic_collision_v1.1",
    "startup_prior_mode": "initial_footprint",
    "startup_prior_expand_m": 0.3,
    "obstacle_denoise": "none",
    "ppo_raise": False,
    "rc": int("$rc"),
}
sum_p = run / "summary.json"
if sum_p.is_file():
    s = json.load(open(sum_p))
    steps = []
    sp = run / "steps.jsonl"
    if sp.is_file():
        steps = [json.loads(l) for l in sp.read_text().splitlines() if l.strip()]
    expl = [st for st in steps if st.get("phase") == "explore_planner"]
    blocked = sum(1 for st in steps if (st.get("exec") or {}).get("blocked"))
    truncated = sum(1 for st in steps if (st.get("exec") or {}).get("truncated"))
    moved = [float((st.get("exec") or {}).get("moved_m") or 0) for st in steps]
    row.update({
        "status": s.get("status"),
        "termination": s.get("termination"),
        "n_steps": s.get("n_steps"),
        "n_explore": s.get("n_explore_planner_actions"),
        "near_goal": s.get("near_goal"),
        "final_dtg": s.get("final_distance_to_goal_eval_only"),
        "camera_mode_summary": s.get("camera_mode"),
        "simulated_gimbal": s.get("simulated_gimbal"),
        "executor_version_run": s.get("executor_version"),
        "initial_penetration": (s.get("initial_penetration") or {}).get("initial_penetration"),
        "n_blocked_exec": blocked,
        "n_truncated_exec": truncated,
        "sum_moved_m": sum(moved),
        "planner_stop": any(
            (st.get("exec") or {}).get("action_name") == "STOP"
            or (st.get("raw_action") == 0)
            for st in expl
        ),
    })
    # SR_proxy from explore STOP near goal if present in step logs
    sr = False
    for st in expl:
        ex = st.get("exec") or {}
        if ex.get("action_name") == "STOP" or st.get("raw_action") == 0:
            dtg = st.get("distance_to_goal_eval_only")
            if dtg is not None and float(dtg) <= 1.0:
                sr = True
    row["sr_proxy"] = sr
else:
    row["status"] = "missing_summary"
print(json.dumps(row), flush=True)
PY
done <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"

echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
echo "[baseline] done batch=$BATCH_ID summary=$SUMMARY"
