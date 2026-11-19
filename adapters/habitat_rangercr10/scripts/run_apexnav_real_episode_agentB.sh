#!/usr/bin/env bash
# ################################
# Agent B episode runner — private container, safe ApexNav symlink, NoFrontierLook param.
# Does NOT touch vln-rangercr10-agentA-navinf or wipe source mounts.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CONTAINER="${CONTAINER:-vln-rangercr10-agentB-nofrontier}"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentB_nofrontier}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
OUT="$OUT_ROOT/$RUN_ID"
MAX_STEPS="${MAX_STEPS:-150}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
GPU="${GPU:-0}"
ROS_PORT="${ROS_PORT:-11314}"
ENABLE_NO_FRONTIER_LOOK="${ENABLE_NO_FRONTIER_LOOK:-false}"
LOGDIR="$OUT/launch_logs"
mkdir -p "$LOGDIR"

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: container $CONTAINER not running. Start via docker-compose.agentB_nofrontier.yml after lock." >&2
  exit 2
fi

bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" "$CONTAINER"
bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_apex_symlink_safe.sh" "$CONTAINER"

APEX="/workspace/ApexNav"
# Prefer private devel prefix if present; else ApexNav/devel under B clone.
DEVEL_SETUP="/workspace/VLN_Mobilemanipulator/.catkin_devel_agentB/setup.bash"
SRC_ROS="source /opt/ros/noetic/setup.bash; if [[ -f $DEVEL_SETUP ]]; then source $DEVEL_SETUP; else source $APEX/devel/setup.bash; fi; export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}; export ROS_IP=127.0.0.1; export ROS_HOSTNAME=127.0.0.1; cd $APEX"

echo "[B][1/4] roscore :${ROS_PORT} container=$CONTAINER enable_no_frontier_look=$ENABLE_NO_FRONTIER_LOOK"
docker exec -d "$CONTAINER" bash -lc "$SRC_ROS; roscore -p ${ROS_PORT} >$LOGDIR/roscore.log 2>&1"
sleep 2

LAUNCH_FILE="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/launch/exploration_rangercr10.launch"
PROFILE="${INFLATION_PROFILE:-legacy018}"
case "$PROFILE" in
  ranger_safe)
    OVERLAY="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay.yaml"
    ;;
  mid030)
    OVERLAY="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_mid030.yaml"
    ;;
  *)
    OVERLAY="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_legacy018.yaml"
    ;;
esac
PLAN_DIAG_ENABLE="${PLAN_DIAG_ENABLE:-true}"
PIPELINE_DIAG_ENABLE="${PIPELINE_DIAG_ENABLE:-true}"
STARTUP_PRIOR_MODE="${STARTUP_PRIOR_MODE:-initial_footprint}"
ROBOT_SCALE="${ROBOT_SCALE:-0.7}"
STARTUP_PRIOR_EXPAND_M="${STARTUP_PRIOR_EXPAND_M:-0.3}"
OBSTACLE_DENOISE="${OBSTACLE_DENOISE:-none}"
read -r STARTUP_PRIOR_HALF_L STARTUP_PRIOR_HALF_W < <(python3 - <<PY
import sys
sys.path.insert(0, "$ROOT/adapters/habitat_rangercr10")
from src.robot_scale import footprint_at_scale
fp = footprint_at_scale(float("${ROBOT_SCALE}"))
print(fp["chassis_half_length_m"], fp["chassis_half_width_m"])
PY
)
DIAG_DIR="$OUT/native_diag"
mkdir -p "$DIAG_DIR"

echo "[B][2/4] exploration launch"
docker exec -d "$CONTAINER" bash -lc \
  "$SRC_ROS; roslaunch $LAUNCH_FILE ranger_overlay:=$OVERLAY plan_diag_enable:=$PLAN_DIAG_ENABLE plan_diag_dir:=$DIAG_DIR pipeline_diag_enable:=$PIPELINE_DIAG_ENABLE pipeline_diag_dir:=$DIAG_DIR startup_prior_mode:=$STARTUP_PRIOR_MODE startup_prior_half_length:=$STARTUP_PRIOR_HALF_L startup_prior_half_width:=$STARTUP_PRIOR_HALF_W startup_prior_expand_m:=$STARTUP_PRIOR_EXPAND_M obstacle_denoise:=$OBSTACLE_DENOISE enable_no_frontier_look:=$ENABLE_NO_FRONTIER_LOOK >$LOGDIR/exploration.log 2>&1"
sleep 4

docker exec "$CONTAINER" bash -lc \
  "$SRC_ROS; rosparam get /exploration_node/enable_no_frontier_look; rosparam get /exploration_node/sdf_map/obstacles_inflation; strings \$(rosparam get /rosout 2>/dev/null || true)" \
  >"$LOGDIR/effective_params.txt" 2>&1 || true
# Record FSM binary identity
docker exec "$CONTAINER" bash -lc \
  "$SRC_ROS; echo enable_param=\$(rosparam get /exploration_node/enable_no_frontier_look); BIN=\$(rosrun exploration_manager exploration_node --help 2>/dev/null || true); ls -la $APEX/devel/lib/exploration_manager/exploration_node 2>/dev/null || ls -la /workspace/VLN_Mobilemanipulator/.catkin_devel_agentB/lib/exploration_manager/exploration_node; strings /workspace/VLN_Mobilemanipulator/.catkin_devel_agentB/lib/exploration_manager/exploration_node 2>/dev/null | grep -E 'NoFrontierLook|enable_no_frontier' | head; strings $APEX/devel/lib/exploration_manager/exploration_node 2>/dev/null | grep -E 'NoFrontierLook|enable_no_frontier' | head" \
  >"$LOGDIR/fsm_binary_identity.txt" 2>&1 || true

echo "[B][3/4] VLM servers on 12181-12184 (requires B host lock; do not clash with A)"
docker exec "$CONTAINER" bash -lc 'ln -sfn /media/ubuntu/D/VLN_shared/cache/huggingface/bert-base-uncased /workspace/ApexNav/bert-base-uncased'
HF_ENV="export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface TRANSFORMERS_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface HUGGINGFACE_HUB_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface/hub TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1"
docker exec -d "$CONTAINER" bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.detector.yolov7 --port 12184 >$LOGDIR/yolov7.log 2>&1"
docker exec -d "$CONTAINER" bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.detector.grounding_dino --port 12181 >$LOGDIR/dino.log 2>&1"
docker exec -d "$CONTAINER" bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.itm.blip2itm --port 12182 >$LOGDIR/blip2.log 2>&1"
docker exec -d "$CONTAINER" bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.segmentor.sam --port 12183 >$LOGDIR/sam.log 2>&1"

ok=0
for i in $(seq 1 60); do
  if docker exec "$CONTAINER" bash -lc "$SRC_ROS; rosnode list 2>/dev/null | grep -q exploration_node"; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "ERROR: exploration_node failed; see $LOGDIR/exploration.log" >&2
  docker exec "$CONTAINER" bash -lc "tail -80 $LOGDIR/exploration.log" || true
  exit 2
fi
# Confirm enable string in exploration log
docker exec "$CONTAINER" bash -lc "rg -n 'NoFrontierLook|enable=' $LOGDIR/exploration.log | head -5" \
  >>"$LOGDIR/fsm_binary_identity.txt" 2>&1 || true

for i in $(seq 1 90); do
  if docker exec "$CONTAINER" bash -lc 'python - <<"PY"
import socket
ok=True
for p in (12181,12182,12183,12184):
  s=socket.socket(); s.settimeout(0.5)
  try:
    s.connect(("127.0.0.1",p)); s.close()
  except Exception:
    ok=False
print("OK" if ok else "WAIT")
PY'; then
    break
  fi
  sleep 2
done

CAMERA_MODE="${CAMERA_MODE:-fixed_base_gimbal}"
FORCE_SPAWN_JSON="${FORCE_SPAWN_JSON:-}"
PPO_RAISE_JSON="${PPO_RAISE_JSON:-}"
SCALE_ARGS="--robot_scale $ROBOT_SCALE --camera_mode $CAMERA_MODE"
if [[ -n "$FORCE_SPAWN_JSON" ]]; then
  SCALE_ARGS="$SCALE_ARGS --force_spawn_json '$FORCE_SPAWN_JSON'"
fi
if [[ -n "$PPO_RAISE_JSON" ]]; then
  SCALE_ARGS="$SCALE_ARGS --ppo_raise_json '$PPO_RAISE_JSON'"
fi

echo "[B][4/4] episode → $OUT"
LOOK_MODE="${CHASSIS_LOOK_MODE:-none}"
LOOK_PUBS="${CHASSIS_LOOK_EXTRA_PUBS:-40}"
LOOK_HZ="${CHASSIS_LOOK_EXTRA_HZ:-4}"
set +e
docker exec \
  -e ROS_MASTER_URI="http://127.0.0.1:${ROS_PORT}" \
  -e ROS_IP=127.0.0.1 \
  -e ROS_HOSTNAME=127.0.0.1 \
  -e CHASSIS_LOOK_MODE="$LOOK_MODE" \
  -e CHASSIS_LOOK_EXTRA_PUBS="$LOOK_PUBS" \
  -e CHASSIS_LOOK_EXTRA_HZ="$LOOK_HZ" \
  "$CONTAINER" bash -lc "$SRC_ROS; export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:\${PYTHONPATH}; python -m src.apexnav_real_episode --out_dir '$OUT_ROOT' --run_id '$RUN_ID' --max_steps $MAX_STEPS --max_explore_actions $MAX_EXPLORE_ACTIONS --gpu $GPU --scene_filter '${SCENE_FILTER:-TEEsavR23oF}' --category_filter '${CATEGORY_FILTER:-chair}' --episode_id '${EPISODE_ID:-4}' --llm_answer_path $APEX/llm/answers/llm_answer_hm3d.txt --llm_response_path $APEX/llm/answers/llm_response_list.txt $SCALE_ARGS"
rc=$?
set -e

docker exec "$CONTAINER" bash -lc "$SRC_ROS; rosnode kill -a 2>/dev/null || true; kill \$(pgrep -f 'roscore -p ${ROS_PORT}') 2>/dev/null || true" || true

SKIP_DEMO="${SKIP_DEMO:-1}"
if [[ "$SKIP_DEMO" != "1" ]] && docker exec "$CONTAINER" bash -lc "compgen -G '$OUT/demo/frame_*.png' >/dev/null"; then
  docker exec "$CONTAINER" bash -lc \
    "ffmpeg -y -framerate 2 -i '$OUT/demo/frame_%04d.png' -c:v libx264 -pix_fmt yuv420p -crf 23 \
     '$OUT/demo/apexnav_ranger_paper_demo.mp4' >/dev/null 2>&1; chown -R 1000:1000 '$OUT' || true" || true
else
  docker exec "$CONTAINER" bash -lc "chown -R 1000:1000 '$OUT' || true" || true
fi

SUM="$OUT/summary.json"
if [[ ! -f "$SUM" ]]; then
  echo "ERROR: missing summary (rc=$rc)" >&2
  exit "${rc:-1}"
fi
python3 - <<PY
import json,sys
s=json.load(open("$SUM"))
rc=int("$rc")
task_ok = s.get("status")=="ok" and s.get("scripted_policy_used") is False
print("task_status=", s.get("status"), "termination=", s.get("termination"),
      "n_steps=", s.get("n_steps"), "container_rc=", rc,
      "enable_no_frontier_look=", "$ENABLE_NO_FRONTIER_LOOK")
n=int(s.get("n_steps") or 0)
accept = task_ok and n >= 1 and s.get("seen_plan_actions", n) >= 1
sys.exit(0 if accept else 1)
PY
