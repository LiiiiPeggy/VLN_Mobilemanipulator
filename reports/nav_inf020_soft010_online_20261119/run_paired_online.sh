#!/usr/bin/env bash
# ################################
# Paired online: legacy018 vs inf020_soft010 on fixed spawns.
# Budget/camera/executor match formal gimbal protocol (150/100, fixed_base_gimbal, F0+0.3).
# Guard against mid-batch branch flips by restoring pinned sources from src_backup.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
REPORT="$(cd "$(dirname "$0")" && pwd)"
JOBS="${1:-$REPORT/jobs.tsv}"
GPU="${GPU:-0}"
ROS_PORT="${ROS_PORT:-11313}"
MAX_STEPS="${MAX_STEPS:-150}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
SKIP_DEMO="${SKIP_DEMO:-1}"
BATCH_ID="${BATCH_ID:-navinf020_$(date +%Y%m%d_%H%M%S)}"
RESULTS="$REPORT/batch_${BATCH_ID}.jsonl"
NAV_SHA="${NAV_SHA:-6ec6b20}"
SRC_BACKUP="$REPORT/src_backup_${NAV_SHA}"

# ################################
# Restore adapter + planner sources from pin (do not git-checkout mid-batch).
# Rebuild libs only when soft_cost string missing from .so.
# ################################
restore_nav_pin() {
  local reason="${1:-pre}"
  echo "[guard:$reason] restore pin $NAV_SHA from $SRC_BACKUP"
  mkdir -p \
    "$ROOT/baselines/ApexNav/src/planner/path_searching/src" \
    "$ROOT/baselines/ApexNav/src/planner/path_searching/include/path_searching" \
    "$ROOT/baselines/ApexNav/src/planner/plan_env/src" \
    "$ROOT/baselines/ApexNav/src/planner/plan_env/include/plan_env" \
    "$ROOT/adapters/habitat_rangercr10/config" \
    "$ROOT/adapters/habitat_rangercr10/launch" \
    "$ROOT/adapters/habitat_rangercr10/scripts"
  cp -a "$SRC_BACKUP/path_searching/src/astar2d.cpp" \
    "$ROOT/baselines/ApexNav/src/planner/path_searching/src/astar2d.cpp"
  cp -a "$SRC_BACKUP/path_searching/include/astar2d.h" \
    "$ROOT/baselines/ApexNav/src/planner/path_searching/include/path_searching/astar2d.h"
  cp -a "$SRC_BACKUP/plan_env/src/sdf_map2d.cpp" \
    "$ROOT/baselines/ApexNav/src/planner/plan_env/src/sdf_map2d.cpp"
  cp -a "$SRC_BACKUP/plan_env/include/sdf_map2d.h" \
    "$ROOT/baselines/ApexNav/src/planner/plan_env/include/plan_env/sdf_map2d.h"
  cp -a "$SRC_BACKUP/config/"*.yaml "$ROOT/adapters/habitat_rangercr10/config/"
  cp -a "$SRC_BACKUP/launch/"* "$ROOT/adapters/habitat_rangercr10/launch/"
  cp -a "$SRC_BACKUP/scripts/run_apexnav_real_episode.sh" \
    "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh"
  if ! grep -q "inf020_soft010" "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh"; then
    echo "[guard] FATAL: run script missing inf020_soft010 after restore" >&2
    exit 2
  fi
  if ! grep -q "soft_cost enabled" "$ROOT/baselines/ApexNav/src/planner/path_searching/src/astar2d.cpp"; then
    echo "[guard] FATAL: astar2d.cpp missing soft_cost after restore" >&2
    exit 2
  fi
}

ensure_soft_libs() {
  if docker exec vln-rangercr10 bash -lc 'strings /workspace/ApexNav/devel/lib/libpath_searching.so | grep -q "soft_cost enabled"'; then
    echo "[guard] libpath_searching.so already has soft_cost"
    return 0
  fi
  echo "[guard] rebuilding plan_env + path_searching (once)"
  docker exec vln-rangercr10 bash -lc '
    set -e
    source /opt/ros/noetic/setup.bash
    cd /workspace/ApexNav
    touch src/planner/plan_env/src/sdf_map2d.cpp src/planner/path_searching/src/astar2d.cpp
    source devel/setup.bash || true
    cmake --build build --target plan_env path_searching -j$(nproc)
    strings devel/lib/libpath_searching.so | grep "soft_cost enabled"
  '
}

mkdir -p "$REPORT"
: >"$RESULTS"
echo "[batch] $BATCH_ID jobs=$JOBS results=$RESULTS budget=${MAX_STEPS}/${MAX_EXPLORE_ACTIONS}"
restore_nav_pin start
ensure_soft_libs

tail -n +2 "$JOBS" | while IFS=$'\t' read -r tag profile scene cat ep spawn; do
  [[ -z "${tag:-}" || "$tag" =~ ^# ]] && continue
  RUN_ID="${BATCH_ID}_${tag}"
  echo "===== RUN $RUN_ID profile=$profile ====="
  restore_nav_pin "$tag"
  # ################################
  # Do NOT rebuild here — mid-run .so replace previously aborted exploration_node.
  # ################################
  set +e
  INFLATION_PROFILE="$profile" \
    SCENE_FILTER="$scene" CATEGORY_FILTER="$cat" EPISODE_ID="$ep" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" GPU="$GPU" \
    ROS_PORT="$ROS_PORT" RUN_ID="$RUN_ID" OUT_DIR="$OUT_ROOT" \
    ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal \
    FORCE_SPAWN_JSON="$spawn" PPO_RAISE_JSON="" \
    STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none SKIP_DEMO="$SKIP_DEMO" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh"
  rc=$?
  set -e
  python3 - <<PY
import json, re
from pathlib import Path
run=Path("$OUT_ROOT/$RUN_ID")
rec={
  "batch_id":"$BATCH_ID","tag":"$tag","profile":"$profile","rc":int("$rc"),
  "run_id":"$RUN_ID","run_dir":str(run),
  "scene":"$scene","category":"$cat","episode_id":"$ep",
  "spawn":"$spawn","max_steps":int("$MAX_STEPS"),
  "max_explore_actions":int("$MAX_EXPLORE_ACTIONS"),
}
sum_p=run/"summary.json"
if sum_p.exists():
  s=json.loads(sum_p.read_text())
  for k in ("status","termination","n_steps","success_claimed","near_goal","robot_scale","error"):
    rec[k]=s.get(k)
  rec["executor_version"]= (s.get("process_meta") or {}).get("executor_version") or s.get("executor_version")
  rec["n_blocked_exec"]=s.get("n_blocked_exec")
  rec["n_truncated_exec"]=s.get("n_truncated_exec")
eff=run/"launch_logs"/"effective_params.txt"
if eff.exists():
  lines=[ln.strip() for ln in eff.read_text().splitlines() if ln.strip() and not ln.strip().startswith("*") and "error" not in ln.lower()]
  # labeled when 15 numeric/string values present
  keys=["agent_radius","obstacles_inflation","lock_obstacles_inflation","soft_cost_range_m","soft_cost_weight",
        "optimistic","depth_filter_mindist","filter_min_height","filter_max_height","startup_prior_mode",
        "startup_prior_half_length","startup_prior_half_width","startup_prior_expand_m","obstacle_denoise","resolution"]
  if len(lines)>=15:
    rec["effective_params"]={k:lines[i] for i,k in enumerate(keys)}
  else:
    rec["effective_params_raw"]="\n".join(lines[:20])
exp=run/"launch_logs"/"exploration.log"
if exp.exists():
  txt=exp.read_text(errors="ignore")
  m=re.findall(r"effective obstacles_inflation_=([0-9.]+) m\s+resolution=([0-9.]+).{0,30}?([0-9]+)", txt)
  if m: rec["sdf_inflation_log"]={"inflation_m":float(m[-1][0]),"resolution":float(m[-1][1]),"inf_step":int(m[-1][2])}
  m2=re.findall(r"soft_cost enabled: R=([0-9.]+) m\s+w=([0-9.]+)", txt)
  if m2: rec["soft_cost_log"]={"R":float(m2[-1][0]),"w":float(m2[-1][1])}
  rec["lock_seen"]=("lock_obstacles_inflation=true" in txt)
  rec["node_abort"]=("free(): invalid pointer" in txt)
Path("$RESULTS").open("a").write(json.dumps(rec)+"\n")
print(json.dumps({k:rec.get(k) for k in ("tag","profile","rc","status","termination","n_steps","sdf_inflation_log","soft_cost_log","lock_seen","effective_params","error")}, indent=2))
PY
done
echo "[batch] done → $RESULTS"
