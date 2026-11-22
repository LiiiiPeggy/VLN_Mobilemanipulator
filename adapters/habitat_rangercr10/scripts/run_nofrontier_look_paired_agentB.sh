#!/usr/bin/env bash
# ################################
# Agent B NoFrontierLook paired batch (gated on A release + host lock).
# Phase0: hy1_plant_0 OFF/ON. Phase1: more fails + one success after switch OK.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SAFE="${B_SAFE_DIR:-/home/ubuntu/locomani/B_followup_safe}"
PAIR_DIR="$ROOT/reports/ranger_target_discovery_followup/wrong_stop_audit/paired_b"
MANIFEST="$PAIR_DIR/lists/paired_manifest.json"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentB_nofrontier}"
REPORT_DIR="${REPORT_DIR:-$PAIR_DIR/results}"
CONTAINER="${CONTAINER:-vln-rangercr10-agentB-nofrontier}"
ROS_PORT="${ROS_PORT:-11314}"
BATCH_ID="${BATCH_ID:-nofrontier_look_$(date +%Y%m%d_%H%M%S)}"
PHASE="${PHASE:-phase0_switch_verify}"
MAX_STEPS="${MAX_STEPS:-150}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
REQUIRED_COMMIT="${REQUIRED_COMMIT:-a8d16ab35c8711ff346862a2101e788800207158}"
# ################################
# A_RELEASED_LOCK = handover record only.
# Real host lock = /home/ubuntu/locomani/_sim_host_run.lock (A/B shared).
# ################################
LOCK_DIR="$SAFE/host_lock"
A_RELEASE_FLAG="${A_RELEASE_FLAG:-$LOCK_DIR/A_RELEASED_LOCK}"
HOST_LOCK_SH="$ROOT/adapters/habitat_rangercr10/scripts/host_sim_lock.sh"
export SIM_HOST_LOCK="${SIM_HOST_LOCK:-/home/ubuntu/locomani/_sim_host_run.lock}"
export LOCK_OWNER="${LOCK_OWNER:-agentB_nofrontier}"

mkdir -p "$REPORT_DIR" "$OUT_ROOT" "$LOCK_DIR"

# ---------- gates ----------
cd "$ROOT"
HEAD=$(git rev-parse HEAD)
if ! git merge-base --is-ancestor "$REQUIRED_COMMIT" HEAD; then
  echo "[B] BLOCKED: HEAD=$HEAD does not contain required $REQUIRED_COMMIT" >&2
  exit 74
fi
if [[ "${A_RELEASED_LOCK:-0}" != "1" && ! -f "$A_RELEASE_FLAG" ]]; then
  echo "[B] WAIT: A has not released lock. Place $A_RELEASE_FLAG or set A_RELEASED_LOCK=1." >&2
  exit 75
fi
# A container may remain; only block on live build/episode (ignore defunct zombies)
if docker ps --format '{{.Names}}' | grep -qx 'vln-rangercr10-agentA-navinf'; then
  if docker exec vln-rangercr10-agentA-navinf bash -lc \
      'ps -eo pid,stat,cmd | grep -E "apexnav_real_episode|catkin_make|[Mm]ake -" | grep -v grep | grep -v " Z " | head -5' \
      | grep -q .; then
    echo "[B] WAIT: agentA container still has build/episode activity." >&2
    exit 75
  fi
fi

# Acquire shared host lock (authoritative)
if ! LOCK_OWNER="$LOCK_OWNER" SIM_HOST_LOCK="$SIM_HOST_LOCK" bash "$HOST_LOCK_SH" acquire; then
  echo "[B] BLOCKED: $(LOCK_OWNER="$LOCK_OWNER" SIM_HOST_LOCK="$SIM_HOST_LOCK" bash "$HOST_LOCK_SH" status)" >&2
  exit 75
fi
echo "$(date -Is) batch=$BATCH_ID phase=$PHASE head=$HEAD lock=$SIM_HOST_LOCK" | tee -a "$LOCK_DIR/b_host_lock_meta.txt"
cleanup_lock() {
  LOCK_OWNER="$LOCK_OWNER" SIM_HOST_LOCK="$SIM_HOST_LOCK" bash "$HOST_LOCK_SH" release || true
  echo "$(date -Is) released owner=$LOCK_OWNER" >>"$LOCK_DIR/b_host_lock_meta.txt"
}
trap cleanup_lock EXIT

# ---------- ensure container (create only after lock) ----------
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "[B] starting private container $CONTAINER"
  docker compose -f "$ROOT/adapters/habitat_rangercr10/docker-compose.agentB_nofrontier.yml" up -d
fi
bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_apex_symlink_safe.sh" "$CONTAINER"

# ---------- build private devel if needed ----------
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  echo "[B] building full ApexNav catkin into .catkin_devel_agentB"
  docker exec "$CONTAINER" bash -lc '
    set -eo pipefail
    export ROS_DISTRO=noetic
    source /opt/ros/noetic/setup.bash
    APEX=/workspace/ApexNav
    SRC=/workspace/VLN_Mobilemanipulator/baselines/ApexNav
    DEVEL=/workspace/VLN_Mobilemanipulator/.catkin_devel_agentB
    if [[ ! -L $APEX ]]; then
      echo "ApexNav must be symlink; refusing build" >&2; exit 3
    fi
    mkdir -p "$DEVEL"
    cd "$SRC"
    # ################################
    # Prefer system libtiff/curl over conda when linking exploration_node
    # (otherwise gdal/opencv pull unresolved LIBTIFF_4.0 / CURL_OPENSSL_4).
    # ################################
    export LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu
    catkin_make -DCMAKE_BUILD_TYPE=Release -DCATKIN_ENABLE_TESTING=OFF \
      -DCATKIN_DEVEL_PREFIX="$DEVEL" \
      -DCMAKE_EXE_LINKER_FLAGS="-L/usr/lib/x86_64-linux-gnu -ltiff -lcurl" \
      --pkg plan_env --pkg path_searching --pkg exploration_manager \
      -j"$(nproc)" 2>&1 | tee /tmp/agentB_build.log
    test -x "$DEVEL/lib/exploration_manager/exploration_node"
    strings "$DEVEL/lib/exploration_manager/exploration_node" | grep -E "NoFrontierLook" | head -5
  '
fi

SUMMARY="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: >"$SUMMARY"
echo "protocol_budget_MAX_STEPS_${MAX_STEPS}_EXPLORE_${MAX_EXPLORE_ACTIONS}" >"$REPORT_DIR/budget_label_${BATCH_ID}.txt"

python3 - <<PY >"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"
import json
from pathlib import Path
doc=json.loads(Path("$MANIFEST").read_text())
phase=doc["phases"]["$PHASE"]
by={e["id"]:e for e in doc["episodes"]}
for eid in phase["episodes"]:
    e=by[eid]
    for arm in phase["arms"]:
        tag="ON" if arm else "OFF"
        print("\t".join([
            e["id"], tag, "true" if arm else "false",
            e["scene_filter"], e["category"], str(e["episode_id"]),
            e["force_spawn_json"], e.get("bucket",""),
        ]))
PY

echo "[B] phase=$PHASE jobs=$(wc -l <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv") summary=$SUMMARY"

while IFS=$'\t' read -r EP_ID ARM_TAG ENABLE SCENE CAT EP FORCE BUCKET; do
  RUN_ID="agentB_${BATCH_ID}_${EP_ID}_${ARM_TAG}"
  echo "===== $RUN_ID enable=$ENABLE ====="
  # Only clear OUR ros port / our container leftovers
  docker exec -u root "$CONTAINER" bash -lc \
    "pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true" || true
  set +e
  CONTAINER="$CONTAINER" ROS_PORT="$ROS_PORT" \
    ENABLE_NO_FRONTIER_LOOK="$ENABLE" \
    SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" \
    RUN_ID="$RUN_ID" OUT_DIR="$OUT_ROOT" \
    ROBOT_SCALE=0.7 CAMERA_MODE=fixed_base_gimbal \
    FORCE_SPAWN_JSON="$FORCE" \
    STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none SKIP_DEMO=1 \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode_agentB.sh" \
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
    "arm": "$ARM_TAG",
    "enable_no_frontier_look": "$ENABLE" == "true",
    "scene": "$SCENE",
    "category": "$CAT",
    "episode_id": "$EP",
    "force_spawn_json": "$FORCE",
    "bucket_prior": "$BUCKET",
    "max_steps": int("$MAX_STEPS"),
    "max_explore_actions": int("$MAX_EXPLORE_ACTIONS"),
    "rc": int("$rc"),
    "run_dir": str(run),
}
sum_p = run / "summary.json"
if sum_p.is_file():
    s=json.loads(sum_p.read_text())
    row["termination"]=s.get("termination")
    row["n_steps"]=s.get("n_steps")
    row["sum_moved_m"]=s.get("sum_moved_m")
    row["final_dtg"]=s.get("final_distance_to_goal_eval_only")
    row["success_claimed"]=s.get("success_claimed")
    row["spawn_status"]=s.get("spawn_status")
print(json.dumps(row))
PY
  # Analyze pair answers after each run
  python3 "$ROOT/adapters/habitat_rangercr10/scripts/analyze_nofrontier_pair_run.py" \
    --run_dir "$OUT_ROOT/$RUN_ID" \
    --enable "$ENABLE" \
    --out "$REPORT_DIR/analyze_${RUN_ID}.json" || true
done <"$REPORT_DIR/_jobs_${BATCH_ID}.tsv"

echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
echo "[B] done batch=$BATCH_ID — lock will release on exit"
