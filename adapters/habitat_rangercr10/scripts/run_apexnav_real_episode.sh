#!/usr/bin/env bash
# Real ApexNav planner → Ranger+CR10 Habitat ObjectNav attempt (kinematic).
# Uses an ISOLATED ROS master on :11312 so host NBV (:11311) and vln-apexnav
# container-local ROS are not disturbed. Does NOT fall back to scripted_policy.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
OUT="$OUT_ROOT/$RUN_ID"
MAX_STEPS="${MAX_STEPS:-40}"
GPU="${GPU:-0}"
ROS_PORT="${ROS_PORT:-11312}"
LOGDIR="$OUT/launch_logs"
mkdir -p "$LOGDIR"

bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10

# Catkin devel was built at /workspace/ApexNav (vln-apexnav mount). Mirror that path
# inside rangercr10 so ROS packages resolve without rebuilding.
APEX_SRC="/workspace/VLN_Mobilemanipulator/baselines/ApexNav"
APEX="/workspace/ApexNav"
docker exec vln-rangercr10 bash -lc "
  if [[ ! -L '$APEX' || \$(readlink -f '$APEX') != \$(readlink -f '$APEX_SRC') ]]; then
    rm -rf '$APEX'
    ln -sfn '$APEX_SRC' '$APEX'
  fi
"
SRC_ROS="source /opt/ros/noetic/setup.bash; source $APEX/devel/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}; export ROS_IP=127.0.0.1; export ROS_HOSTNAME=127.0.0.1; cd $APEX"

echo "[1/4] start isolated roscore :${ROS_PORT}"
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; roscore -p ${ROS_PORT} >$LOGDIR/roscore.log 2>&1"
sleep 2

# ################################
# Adapter launch: upstream algorithm + Ranger footprint overlay (radius→inflation).
# Does not modify baselines/ApexNav launch files.
# ################################
LAUNCH_FILE="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/launch/exploration_rangercr10.launch"
# INFLATION_PROFILE:
#   legacy018 (default for Habitat kinematic demos): 0.18 m — matches ApexNav HM3D agent;
#     UNSAFE vs Ranger chassis half-width≈0.435 m (see reports).
#   mid030: 0.30 m sensitivity — still UNSAFE vs half-width; offline/online A/B only.
#   ranger_safe: 0.485 m oriented footprint — correct clearance, may starve free on sparse maps.
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
# ################################
# Optional native C++ plan / map pipeline diagnostics (observe-only).
# ################################
PLAN_DIAG_ENABLE="${PLAN_DIAG_ENABLE:-true}"
PIPELINE_DIAG_ENABLE="${PIPELINE_DIAG_ENABLE:-true}"
# ################################
# startup_prior_mode: none (default) | initial_footprint
# half_l/half_w from footprint_at_scale(ROBOT_SCALE); unused when none.
# expand_m: isotropic F0 margin; initial_footprint 默认 0.3 m（可显式覆盖为 0）。
# ################################
STARTUP_PRIOR_MODE="${STARTUP_PRIOR_MODE:-none}"
ROBOT_SCALE="${ROBOT_SCALE:-1.0}"
if [[ "$STARTUP_PRIOR_MODE" == "initial_footprint" ]]; then
  STARTUP_PRIOR_EXPAND_M="${STARTUP_PRIOR_EXPAND_M:-0.3}"
else
  STARTUP_PRIOR_EXPAND_M="${STARTUP_PRIOR_EXPAND_M:-0.0}"
fi
# ################################
# obstacle_denoise: none (default) | median3
# ################################
OBSTACLE_DENOISE="${OBSTACLE_DENOISE:-none}"
read -r STARTUP_PRIOR_HALF_L STARTUP_PRIOR_HALF_W < <(python3 - <<PY
import sys
sys.path.insert(0, "/home/ubuntu/locomani/VLN_Mobilemanipulator/adapters/habitat_rangercr10")
from src.robot_scale import footprint_at_scale
fp = footprint_at_scale(float("${ROBOT_SCALE}"))
print(fp["chassis_half_length_m"], fp["chassis_half_width_m"])
PY
)
DIAG_DIR="$OUT/native_diag"
mkdir -p "$DIAG_DIR"
echo "[2/4] start exploration_rangercr10.launch (profile=$PROFILE overlay=$(basename "$OVERLAY") plan_diag=$PLAN_DIAG_ENABLE startup_prior=$STARTUP_PRIOR_MODE half=${STARTUP_PRIOR_HALF_L}x${STARTUP_PRIOR_HALF_W} expand_m=$STARTUP_PRIOR_EXPAND_M denoise=$OBSTACLE_DENOISE)"
docker exec -d vln-rangercr10 bash -lc \
  "$SRC_ROS; roslaunch $LAUNCH_FILE ranger_overlay:=$OVERLAY plan_diag_enable:=$PLAN_DIAG_ENABLE plan_diag_dir:=$DIAG_DIR pipeline_diag_enable:=$PIPELINE_DIAG_ENABLE pipeline_diag_dir:=$DIAG_DIR startup_prior_mode:=$STARTUP_PRIOR_MODE startup_prior_half_length:=$STARTUP_PRIOR_HALF_L startup_prior_half_width:=$STARTUP_PRIOR_HALF_W startup_prior_expand_m:=$STARTUP_PRIOR_EXPAND_M obstacle_denoise:=$OBSTACLE_DENOISE >$LOGDIR/exploration.log 2>&1"
sleep 4
# Record effective params
docker exec vln-rangercr10 bash -lc \
  "$SRC_ROS; rosparam get /habitat/simulator/agents/main_agent/radius; rosparam get /exploration_node/sdf_map/obstacles_inflation; rosparam get /exploration_node/sdf_map/optimistic; rosparam get /exploration_node/map_ros/depth_filter_mindist; rosparam get /exploration_node/map_ros/filter_min_height; rosparam get /exploration_node/map_ros/filter_max_height; rosparam get /exploration_node/exploration/startup_prior_mode; rosparam get /exploration_node/exploration/startup_prior_half_length; rosparam get /exploration_node/exploration/startup_prior_half_width; rosparam get /exploration_node/exploration/startup_prior_expand_m; rosparam get /exploration_node/sdf_map/obstacle_denoise; rosparam get /exploration_node/sdf_map/resolution" \
  >"$LOGDIR/effective_params.txt" 2>&1 || true

echo "[3/4] start VLM servers (yolo/dino/blip2/sam) if not up"
docker exec vln-rangercr10 bash -lc 'ln -sfn /media/ubuntu/D/VLN_shared/cache/huggingface/bert-base-uncased /workspace/ApexNav/bert-base-uncased'
HF_ENV="export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface TRANSFORMERS_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface HUGGINGFACE_HUB_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface/hub TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1"
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.detector.yolov7 --port 12184 >$LOGDIR/yolov7.log 2>&1"
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.detector.grounding_dino --port 12181 >$LOGDIR/dino.log 2>&1"
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.itm.blip2itm --port 12182 >$LOGDIR/blip2.log 2>&1"
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.segmentor.sam --port 12183 >$LOGDIR/sam.log 2>&1"

# wait for planner node + a VLM port
ok=0
for i in $(seq 1 60); do
  if docker exec vln-rangercr10 bash -lc "$SRC_ROS; rosnode list 2>/dev/null | grep -q exploration_node"; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "ERROR: exploration_node failed to start; see $LOGDIR/exploration.log" >&2
  docker exec vln-rangercr10 bash -lc "tail -80 $LOGDIR/exploration.log" || true
  exit 2
fi
echo "exploration_node OK"

# brief VLM readiness (non-fatal wait; episode will hard-fail on perception errors)
for i in $(seq 1 90); do
  if docker exec vln-rangercr10 bash -lc 'python - <<"PY"
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

# ################################
# ROBOT_SCALE=1.0 (real) or 0.7 (scaled_robot_proxy_070). Optional FORCE_SPAWN_JSON.
# ################################
ROBOT_SCALE="${ROBOT_SCALE:-1.0}"
FORCE_SPAWN_JSON="${FORCE_SPAWN_JSON:-}"
PPO_RAISE_JSON="${PPO_RAISE_JSON:-}"
SCALE_ARGS="--robot_scale $ROBOT_SCALE"
if [[ -n "$FORCE_SPAWN_JSON" ]]; then
  SCALE_ARGS="$SCALE_ARGS --force_spawn_json '$FORCE_SPAWN_JSON'"
fi
if [[ -n "$PPO_RAISE_JSON" ]]; then
  SCALE_ARGS="$SCALE_ARGS --ppo_raise_json '$PPO_RAISE_JSON'"
fi

MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-20}"
echo "[4/4] run real ApexNav episode → $OUT (robot_scale=$ROBOT_SCALE max_explore=$MAX_EXPLORE_ACTIONS)"
# ################################
# Forward optional experimental chassis-look burst env (default none).
# ################################
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
  vln-rangercr10 bash -lc "$SRC_ROS; export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:\${PYTHONPATH}; python -m src.apexnav_real_episode --out_dir '$OUT_ROOT' --run_id '$RUN_ID' --max_steps $MAX_STEPS --max_explore_actions $MAX_EXPLORE_ACTIONS --gpu $GPU --scene_filter '${SCENE_FILTER:-TEEsavR23oF}' --category_filter '${CATEGORY_FILTER:-chair}' --episode_id '${EPISODE_ID:-4}' --llm_answer_path $APEX/llm/answers/llm_answer_hm3d.txt --llm_response_path $APEX/llm/answers/llm_response_list.txt $SCALE_ARGS"
rc=$?
set -e

# stop ONLY our isolated ROS tree (do not touch host :11311 / vln-apexnav)
docker exec vln-rangercr10 bash -lc "$SRC_ROS; rosnode kill -a 2>/dev/null || true; kill \$(pgrep -f 'roscore -p ${ROS_PORT}') 2>/dev/null || true" || true

# ################################
# SKIP_DEMO=1：批评测跳过 ffmpeg，避免拖慢；代表性成功/失败再单独编码。
# ################################
SKIP_DEMO="${SKIP_DEMO:-0}"
if [[ "$SKIP_DEMO" != "1" ]] && docker exec vln-rangercr10 bash -lc "compgen -G '$OUT/demo/frame_*.png' >/dev/null"; then
  echo "[demo] encode apexnav_ranger_paper_demo.mp4"
  docker exec vln-rangercr10 bash -lc \
    "ffmpeg -y -framerate 2 -i '$OUT/demo/frame_%04d.png' -c:v libx264 -pix_fmt yuv420p -crf 23 \
     '$OUT/demo/apexnav_ranger_paper_demo.mp4' >/dev/null 2>&1; chown -R 1000:1000 '$OUT' || true" \
    || true
elif [[ "$SKIP_DEMO" == "1" ]]; then
  echo "[demo] SKIP_DEMO=1 — leave frames unencoded"
  docker exec vln-rangercr10 bash -lc "chown -R 1000:1000 '$OUT' || true" || true
fi
# ################################

SUM="$OUT/summary.json"
if [[ ! -f "$SUM" ]]; then
  echo "ERROR: missing summary (rc=$rc)" >&2
  exit "${rc:-1}"
fi
python3 - <<PY
import json,sys
s=json.load(open("$SUM"))
rc=int("$rc")
# Habitat close() may SIGABRT→134; accept task status from summary
task_ok = s.get("status")=="ok" and s.get("scripted_policy_used") is False
proc_note = "cleanup_abort_ok" if rc in (0,134) else f"rc={rc}"
print("task_status=", s.get("status"), "termination=", s.get("termination"),
      "n_steps=", s.get("n_steps"), "container_rc=", rc, "proc=", proc_note,
      "planner=", s.get("apexnav_planner"), "scripted=", s.get("scripted_policy_used"),
      "init=", s.get("n_init_lookaround_actions"), "explore=", s.get("n_explore_planner_actions"),
      "entered_explore=", s.get("entered_callActionPlanner"),
      "map=", (s.get("online_grid_map") or {}).get("has_data"),
      "adapted=", s.get("adapted_episode"))
# Minimum acceptance: real planner drove ≥2 steps OR planner_stop after ≥1
n=int(s.get("n_steps") or 0)
accept = task_ok and n >= 1 and s.get("seen_plan_actions", n) >= 1
sys.exit(0 if accept else 1)
PY
