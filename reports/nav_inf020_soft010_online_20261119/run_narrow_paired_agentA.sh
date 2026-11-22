#!/usr/bin/env bash
# ################################
# Agent A: narrow-corridor paired online (legacy018 vs inf020_soft010).
# Uses A-only container + A out dir. Caller must hold host sim lock.
# ################################
set -euo pipefail
A_ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator_agentA_navinf
OUT_ROOT=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentA_navinf
REPORT=$A_ROOT/reports/nav_inf020_soft010_online_20261119
JOBS=${1:-$REPORT/jobs_narrow.tsv}
GPU=${GPU:-0}
ROS_PORT=${ROS_PORT:-11323}
MAX_STEPS=${MAX_STEPS:-150}
MAX_EXPLORE_ACTIONS=${MAX_EXPLORE_ACTIONS:-100}
SKIP_DEMO=${SKIP_DEMO:-1}
BATCH_ID=${BATCH_ID:-navinf_narrow_A_$(date +%Y%m%d_%H%M%S)}
RESULTS=$REPORT/batch_${BATCH_ID}.jsonl
EP_SCRIPT=$A_ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode_agentA.sh
mkdir -p "$OUT_ROOT" "$REPORT"
: >"$RESULTS"
echo "$BATCH_ID" > "$REPORT/latest_narrow_batch_id.txt"
echo "[batch] $BATCH_ID budget=${MAX_STEPS}/${MAX_EXPLORE_ACTIONS} ros=$ROS_PORT"

docker exec vln-rangercr10-agentA-navinf bash -lc '
  strings /workspace/ApexNav/devel/lib/libpath_searching.so | grep -q "soft_cost enabled"
  test -x /workspace/ApexNav/devel/lib/exploration_manager/exploration_node
'

tail -n +2 "$JOBS" | while IFS=$'\t' read -r tag profile scene cat ep spawn; do
  [[ -z "${tag:-}" || "$tag" =~ ^# ]] && continue
  RUN_ID="${BATCH_ID}_${tag}"
  echo "===== RUN $RUN_ID profile=$profile ====="
  docker exec vln-rangercr10-agentA-navinf bash -lc "pkill -9 -f 'ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}' 2>/dev/null; pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null; true" || true
  sleep 2
  set +e
  INFLATION_PROFILE="$profile" SCENE_FILTER="$scene" CATEGORY_FILTER="$cat" EPISODE_ID="$ep" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" GPU="$GPU" \
    ROS_PORT="$ROS_PORT" RUN_ID="$RUN_ID" OUT_DIR="$OUT_ROOT" \
    ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal \
    FORCE_SPAWN_JSON="$spawn" PPO_RAISE_JSON= \
    STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none SKIP_DEMO="$SKIP_DEMO" \
    bash "$EP_SCRIPT"
  rc=$?
  set -e
  python3 - <<PY
import json, re
from pathlib import Path
run=Path("$OUT_ROOT/$RUN_ID")
rec={"batch_id":"$BATCH_ID","tag":"$tag","profile":"$profile","rc":int("$rc"),
     "run_id":"$RUN_ID","run_dir":str(run),"scene":"$scene","category":"$cat","episode_id":"$ep"}
sp=run/"summary.json"
if sp.exists():
  s=json.loads(sp.read_text())
  for k in ("status","termination","n_steps","success_claimed","near_goal","n_blocked_exec","n_truncated_exec","error","executor_version","camera_mode","robot_scale"):
    rec[k]=s.get(k)
exp=run/"launch_logs"/"exploration.log"
if exp.exists():
  txt=exp.read_text(errors="ignore")
  m=re.findall(r"effective obstacles_inflation_=([0-9.]+) m\s+resolution=([0-9.]+).{0,40}?([0-9]+)", txt)
  if m: rec["sdf"]={"inflation_m":float(m[-1][0]),"resolution":float(m[-1][1]),"inf_step":int(m[-1][2])}
  soft=re.findall(r"soft_cost enabled: R=([0-9.]+) m\s+w=([0-9.]+)", txt)
  if soft: rec["soft"]={"R":float(soft[-1][0]),"w":float(soft[-1][1])}
  rec["lock"]=("lock_obstacles_inflation=true" in txt)
  rec["node_abort"]=("free(): invalid pointer" in txt)
  if rec.get("soft") and rec.get("lock") and rec.get("sdf",{}).get("inflation_m")==0.2:
    rec["actual_profile"]="inf020_soft010"
  elif rec.get("sdf",{}).get("inflation_m")==0.18 and not rec.get("soft"):
    rec["actual_profile"]="legacy018"
  else:
    rec["actual_profile"]="unknown"
Path("$RESULTS").open("a").write(json.dumps(rec)+"\n")
print(json.dumps({k:rec.get(k) for k in ("tag","profile","actual_profile","rc","termination","n_steps","sdf","soft","lock","error")}, indent=2))
PY
done
echo "[batch] done → $RESULTS"
