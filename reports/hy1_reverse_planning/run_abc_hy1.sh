#!/usr/bin/env bash
# ################################
# Fair HY1 plant A/B/C reverse-planning ablation (same FORCE_SPAWN).
# Usage:
#   MODE=B BUDGET=orig bash reports/hy1_reverse_planning/run_abc_hy1.sh
#   MODE=C BUDGET=ext  bash reports/hy1_reverse_planning/run_abc_hy1.sh
# Does NOT change formal deploy defaults (REVERSE_PLANNING_MODE default remains A).
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
source adapters/habitat_rangercr10/scripts/run_integrate_defaults.env
if [[ ! -f "${CATKIN_DEVEL_PREFIX}/setup.bash" ]]; then
  export CATKIN_DEVEL_PREFIX=/workspace/ApexNav/devel
fi

MODE="${MODE:-B}"
BUDGET="${BUDGET:-orig}"  # orig | ext
REP="${REP:-1}"
GPU="${GPU:-0}"
SKIP_DEMO="${SKIP_DEMO:-0}"

case "$BUDGET" in
  orig)
    export MAX_STEPS=50
    export MAX_EXPLORE_ACTIONS=20
    ;;
  ext)
    export MAX_STEPS=100
    export MAX_EXPLORE_ACTIONS=60
    ;;
  *)
    echo "BUDGET must be orig|ext" >&2
    exit 2
    ;;
esac

BATCH_ID="hy1_rev_${MODE}_${BUDGET}_r${REP}_$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="$ROOT/reports/hy1_reverse_planning"
mkdir -p "$REPORT_DIR/logs"
LOCK=/home/ubuntu/locomani/_sim_host_run.lock
if [[ -f "$LOCK" ]]; then
  echo "ERROR: sim lock held: $(cat "$LOCK")" >&2
  exit 3
fi
echo "$$ hy1_rev_${MODE}_${BUDGET} $(date -Iseconds)" >"$LOCK"
cleanup() { rm -f "$LOCK" || true; }
trap cleanup EXIT

export RUN_ID="${BATCH_ID}_hy1_plant_0"
# ################################
# Force ablation out root (run_integrate_defaults.env may already set OUT_DIR).
# ################################
export OUT_DIR="${ABLATION_OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/hy1_reverse_planning_ablation}"
export SCENE_FILTER=HY1NcmCgn3n
export CATEGORY_FILTER=plant
export EPISODE_ID=0
export FORCE_SPAWN_JSON=/workspace/VLN_Mobilemanipulator/reports/ranger_target_discovery_followup/wrong_stop_audit/paired_b/frozen_spawns/hy1_plant_0_start_pose.json
export REVERSE_PLANNING_MODE="$MODE"
export GPU
export SOFT_REACH_ON_ANY_STUCK=false
export SKIP_DEMO

LOG="$REPORT_DIR/logs/${BATCH_ID}_host.log"
INDEX="$REPORT_DIR/runs_index.jsonl"
{
  echo "BATCH=$BATCH_ID MODE=$MODE BUDGET=$BUDGET MAX_STEPS=$MAX_STEPS MAX_EXPLORE=$MAX_EXPLORE_ACTIONS"
  echo "FORCE_SPAWN=$FORCE_SPAWN_JSON EXEC=$EXEC_BACKEND LOOK=$LOOK_BACKEND"
  echo "GIT=$(git rev-parse HEAD)"
  bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
  echo DONE_RC=$?
} 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}

OUT_PATH="$OUT_DIR/$RUN_ID"
# ################################
# Index via env (avoid fragile nested quotes in heredoc).
# ################################
export _IDX_PATH="$INDEX"
export _IDX_BATCH="$BATCH_ID"
export _IDX_MODE="$MODE"
export _IDX_BUDGET="$BUDGET"
export _IDX_REP="$REP"
export _IDX_RUN="$RUN_ID"
export _IDX_OUT="$OUT_PATH"
export _IDX_LOG="$LOG"
export _IDX_RC="$rc"
python3 - <<'PY'
import json, time, os
from pathlib import Path
idx = Path(os.environ["_IDX_PATH"])
row = {
  "batch_id": os.environ["_IDX_BATCH"],
  "mode": os.environ["_IDX_MODE"],
  "budget": os.environ["_IDX_BUDGET"],
  "rep": int(os.environ["_IDX_REP"]),
  "run_id": os.environ["_IDX_RUN"],
  "out_dir": os.environ["_IDX_OUT"],
  "log": os.environ["_IDX_LOG"],
  "rc": int(os.environ.get("_IDX_RC") or 0),
  "t": time.strftime("%Y-%m-%dT%H:%M:%S"),
}
sum_path = Path(row["out_dir"]) / "summary.json"
if sum_path.is_file():
    s = json.loads(sum_path.read_text())
    row["termination"] = s.get("termination")
    row["n_steps"] = s.get("n_steps")
    row["sum_moved_m"] = s.get("sum_moved_m")
    row["n_blocked_exec"] = s.get("n_blocked_exec")
    row["reverse_planning"] = s.get("reverse_planning")
idx.parent.mkdir(parents=True, exist_ok=True)
with idx.open("a") as f:
    f.write(json.dumps(row) + "\n")
print(json.dumps(row, indent=2))
PY
exit "$rc"
