#!/usr/bin/env bash
# cand05 static multi-frame map validation (no chassis motion, no VLM required).
# CHASSIS_LOOK_MODE stays none; STATIC_OBS_ENABLE=1 selects cand05.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# Host path (also mounted as /workspace/VLN_Mobilemanipulator inside vln-rangercr10)
HOST_OUT="${HOST_OUT:-$ROOT/reports/hy1_cand05_static_multiframe_20261106}"
OUT="${OUT_DIR:-/workspace/VLN_Mobilemanipulator/reports/hy1_cand05_static_multiframe_20261106}"
ROS_PORT="${ROS_PORT:-11312}"
GPU="${GPU:-0}"
LOGDIR_HOST="$HOST_OUT/launch_logs"
DIAG_DIR_HOST="$HOST_OUT/native_diag"
LOGDIR="$OUT/launch_logs"
DIAG_DIR="$OUT/native_diag"
mkdir -p "$LOGDIR_HOST" "$DIAG_DIR_HOST"

APEX_SRC="/workspace/VLN_Mobilemanipulator/baselines/ApexNav"
APEX="/workspace/ApexNav"
docker exec vln-rangercr10 bash -lc "
  if [[ ! -L '$APEX' || \$(readlink -f '$APEX') != \$(readlink -f '$APEX_SRC') ]]; then
    rm -rf '$APEX'; ln -sfn '$APEX_SRC' '$APEX'
  fi
"
SRC_ROS="source /opt/ros/noetic/setup.bash; source $APEX/devel/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}; export ROS_IP=127.0.0.1; export ROS_HOSTNAME=127.0.0.1; cd $APEX"

echo "[0] kill prior ROS on :${ROS_PORT}"
docker exec -u root vln-rangercr10 bash -lc "
  pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null || true
  pkill -9 -f exploration_node 2>/dev/null || true
  sleep 1; true
" || true

bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10

echo "[1] offline gate stage-loss diag (C + cand05)"
docker exec -u root vln-rangercr10 bash -lc "
  chown -R 1000:1000 /workspace/VLN_Mobilemanipulator/reports 2>/dev/null || true
  export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:\$PYTHONPATH
  export HABITAT_SIM_LOG=quiet
  python /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/scripts/hy1_gate_stage_loss_diag.py \
    --out $OUT --gpu $GPU \
    >$LOGDIR/gate_stage_loss.log 2>&1
  echo gate_diag_exit:\$?
  tail -30 $LOGDIR/gate_stage_loss.log
"

echo "[2] start roscore :${ROS_PORT}"
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; roscore -p ${ROS_PORT} >$LOGDIR/roscore.log 2>&1"
sleep 2

LAUNCH_FILE="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/launch/exploration_rangercr10.launch"
OVERLAY="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_legacy018.yaml"
echo "[3] start exploration_node (pipeline_diag on; no VLM)"
docker exec -d vln-rangercr10 bash -lc \
  "$SRC_ROS; roslaunch $LAUNCH_FILE ranger_overlay:=$OVERLAY plan_diag_enable:=true plan_diag_dir:=$DIAG_DIR pipeline_diag_enable:=true pipeline_diag_dir:=$DIAG_DIR >$LOGDIR/exploration.log 2>&1"

ok=0
for i in $(seq 1 60); do
  if docker exec vln-rangercr10 bash -lc "$SRC_ROS; rosnode list 2>/dev/null | grep -q exploration_node"; then
    ok=1; break
  fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "ERROR: exploration_node failed" >&2
  docker exec vln-rangercr10 bash -lc "tail -80 $LOGDIR/exploration.log" || true
  exit 2
fi
echo "exploration_node OK"
docker exec vln-rangercr10 bash -lc \
  "$SRC_ROS; { rosparam get /exploration_node/map_ros/ground_free_ray_enable; rosparam get /exploration_node/map_ros/ground_free_max_agl; rosparam get /exploration_node/map_ros/filter_min_height; } >$LOGDIR/effective_map_params.txt 2>&1" \
  || true

echo "[4] static multi-frame cand05"
docker exec vln-rangercr10 bash -lc "
  export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:\$PYTHONPATH
  export HABITAT_SIM_LOG=quiet
  export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}
  export ROS_IP=127.0.0.1
  export ROS_HOSTNAME=127.0.0.1
  export CHASSIS_LOOK_MODE=none
  export STATIC_OBS_ENABLE=1
  export STATIC_OBS_POSE=cand05
  source /opt/ros/noetic/setup.bash
  source $APEX/devel/setup.bash
  python /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/scripts/hy1_cand05_static_multiframe.py \
    --out $OUT \
    --pipeline_diag $DIAG_DIR/map_pipeline_diag.jsonl \
    --checkpoints 1,5,10,20,40 \
    --gpu $GPU \
    --publish_hz 4 \
    >$LOGDIR/static_multiframe.log 2>&1
  echo static_exit:\$?
  tail -60 $LOGDIR/static_multiframe.log
"

echo "[5] cleanup ROS"
docker exec -u root vln-rangercr10 bash -lc "
  pkill -9 -f exploration_node 2>/dev/null || true
  pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null || true
  chown -R 1000:1000 $OUT 2>/dev/null || true
  true
" || true

# sync to host reports if distinct
if [[ -d /home/ubuntu/locomani/VLN_Mobilemanipulator/reports ]]; then
  mkdir -p "$HOST_OUT"
  # OUT may already be on the mount
  if [[ -f "$OUT/summary.json" ]]; then
    cp -a "$OUT/." "$HOST_OUT/" 2>/dev/null || true
  fi
fi
echo "DONE OUT=$OUT"
ls -la "$OUT" 2>/dev/null | head -30 || docker exec vln-rangercr10 bash -lc "ls -la $OUT | head -30"
