#!/usr/bin/env bash
# ################################
# Main-session joint4 runner (holds host sim lock for the whole batch).
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/adapters/habitat_rangercr10/scripts/run_integrate_defaults.env"
JOBS="${1:-$ROOT/reports/integration_20261122/joint4/jobs.tsv}"
BATCH_ID="${BATCH_ID:-joint4_$(date +%Y%m%d_%H%M%S)}"
OUT_ROOT="${OUT_DIR}/$BATCH_ID"
REPORT_DIR="$ROOT/reports/integration_20261122/joint4/results_$BATCH_ID"
mkdir -p "$OUT_ROOT" "$REPORT_DIR"
LOCK_SCRIPT="$ROOT/adapters/habitat_rangercr10/scripts/host_sim_lock.sh"
export LOCK_OWNER=integrate_main

"$LOCK_SCRIPT" acquire
cleanup() {
  "$LOCK_SCRIPT" release || true
}
trap cleanup EXIT

# Fixed protocol knobs
export MAX_STEPS="${MAX_STEPS:-150}"
export MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
export ENABLE_NO_FRONTIER_LOOK="${ENABLE_NO_FRONTIER_LOOK:-false}"
export STARTUP_PRIOR_MODE=initial_footprint
export STARTUP_PRIOR_EXPAND_M=0.3
export ROBOT_SCALE=0.7
export CAMERA_MODE=fixed_base_gimbal
export SKIP_DEMO=1
export PLAN_DIAG_ENABLE=true
export PIPELINE_DIAG_ENABLE=true

JSONL="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: >"$JSONL"
echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"

tail -n +2 "$JOBS" | while IFS=$'\t' read -r tag profile recovery scene category episode spawn; do
  [[ -z "${tag:-}" ]] && continue
  export INFLATION_PROFILE="$profile"
  export BLOCKED_RECOVERY_MODE="$recovery"
  export SCENE_FILTER="$scene"
  export CATEGORY_FILTER="$category"
  export EPISODE_ID="$episode"
  export FORCE_SPAWN_JSON="$spawn"
  export RUN_ID="${BATCH_ID}_${tag}"
  export OUT_DIR="$OUT_ROOT"
  echo "[joint4] start $tag profile=$profile recovery=$recovery" | tee -a "$REPORT_DIR/host.log"
  set +e
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$REPORT_DIR/${tag}_host.log" 2>&1
  rc=$?
  set -e
  SUM="$OUT_ROOT/$RUN_ID/summary.json"
  python3 - <<PY >>"$JSONL"
import json, pathlib, time
tag="$tag"; profile="$profile"; recovery="$recovery"; rc=int("$rc")
p=pathlib.Path("$SUM")
row={"tag":tag,"profile":profile,"recovery":recovery,"container_rc":rc,"t":time.time()}
if p.exists():
  s=json.loads(p.read_text())
  row.update({
    "run_id": s.get("run_id") or "$RUN_ID",
    "status": s.get("status"),
    "termination": s.get("termination"),
    "success": s.get("success"),
    "n_steps": s.get("n_steps"),
    "sum_moved_m": s.get("sum_moved_m"),
    "final_distance_to_goal": s.get("final_distance_to_goal") or s.get("distance_to_goal"),
    "n_blocked_exec": s.get("n_blocked_exec"),
    "n_truncated_exec": s.get("n_truncated_exec"),
    "n_blocked_recovery": s.get("n_blocked_recovery"),
    "blocked_recovery_mode": s.get("blocked_recovery_mode"),
    "spawn_status": s.get("spawn_status"),
    "out": str(p.parent),
  })
else:
  row.update({"status":"missing_summary","out":"$OUT_ROOT/$RUN_ID"})
print(json.dumps(row, ensure_ascii=False))
PY
  echo "[joint4] done $tag rc=$rc" | tee -a "$REPORT_DIR/host.log"
done

echo "BATCH_DONE $BATCH_ID -> $REPORT_DIR"
