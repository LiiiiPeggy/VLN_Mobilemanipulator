#!/usr/bin/env bash
# Runs entirely inside vln-rangercr10-agentA-navinf (no nested docker).
set -euo pipefail
OUT_ROOT=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentA_navinf
BATCH_ID=${BATCH_ID:-sofa_legacy_A_$(date +%Y%m%d_%H%M%S)}
RUN_ID=${BATCH_ID}_sofa_legacy018
OUT=$OUT_ROOT/$RUN_ID
LOGDIR=$OUT/launch_logs
DIAG=$OUT/native_diag
mkdir -p "$LOGDIR" "$DIAG"
echo "$BATCH_ID" > /workspace/VLN_Mobilemanipulator/reports/nav_inf020_soft010_online_20261119/latest_sofa_legacy_batch.txt
echo "===== INSIDE $RUN_ID ====="

set +u
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
set -u
export ROS_DISTRO="${ROS_DISTRO:-noetic}"
export ROS_MASTER_URI=http://127.0.0.1:11323
export ROS_IP=127.0.0.1
export ROS_HOSTNAME=127.0.0.1
export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch
export HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface
export TRANSFORMERS_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface
export HUGGINGFACE_HUB_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface/hub
export TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1
export PYTHONPATH=/workspace/ApexNav/GroundingDINO:/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:${PYTHONPATH:-}
cd /workspace/ApexNav

# Prove libs
echo "[libs] path_searching=$(readlink -f devel/lib/libpath_searching.so)"
echo "[libs] plan_env=$(readlink -f devel/lib/libplan_env.so)"
strings devel/lib/libpath_searching.so | grep -c "soft_cost enabled" || true
ldd devel/lib/exploration_manager/exploration_node | grep -E "path_searching|plan_env"

set +e
pkill -f "roscore -p 11323" 2>/dev/null || true
pkill -f "ROS_MASTER_URI=http://127.0.0.1:11323" 2>/dev/null || true
set -e
sleep 1

roscore -p 11323 >"$LOGDIR/roscore.log" 2>&1 &
sleep 3
rosparam list >/dev/null 2>&1 || { echo "roscore failed"; cat "$LOGDIR/roscore.log"; exit 10; }

OVERLAY=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_legacy018.yaml
LAUNCH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/launch/exploration_rangercr10.launch
roslaunch "$LAUNCH" \
  ranger_overlay:="$OVERLAY" \
  plan_diag_enable:=true plan_diag_dir:="$DIAG" \
  pipeline_diag_enable:=true pipeline_diag_dir:="$DIAG" \
  startup_prior_mode:=initial_footprint \
  startup_prior_half_length:=0.4557 startup_prior_half_width:=0.30429 \
  startup_prior_expand_m:=0.3 obstacle_denoise:=none \
  obstacles_inflation:=0.18 lock_obstacles_inflation:=false \
  soft_cost_range_m:=0.0 soft_cost_weight:=0.0 \
  >"$LOGDIR/exploration.log" 2>&1 &
EXP_PID=$!
sleep 5
# wait exploration_node
for i in $(seq 1 30); do
  if pgrep -f exploration_node >/dev/null; then echo "exploration_node OK"; break; fi
  sleep 1
done

# Capture effective params
{
  rosparam get /habitat/simulator/agents/main_agent/radius || true
  rosparam get /exploration_node/sdf_map/obstacles_inflation || true
  rosparam get /exploration_node/sdf_map/lock_obstacles_inflation || true
  rosparam get /exploration_node/astar/soft_cost_range_m || true
  rosparam get /exploration_node/astar/soft_cost_weight || true
  rosparam get /exploration_node/sdf_map/resolution || true
} >"$LOGDIR/effective_params.txt" 2>&1 || true

# Reuse stable VLMs on 11312 ports if already up; do not start new heavy ones if ports listen
python3 - <<'PY'
import socket
for p in (12181,12182,12183,12184):
    s=socket.socket(); s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", p)); print(f"port {p} up")
    except Exception:
        print(f"port {p} DOWN")
    finally:
        s.close()
PY

SPAWN=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/formalgimbal_formal150_full_20261117_190344_TEEsavR23oF_sofa_0/start_pose.json
set +e
python -m src.apexnav_real_episode \
  --out_dir "$OUT_ROOT" --run_id "$RUN_ID" \
  --max_steps 150 --max_explore_actions 100 --gpu 0 \
  --scene_filter TEEsavR23oF --category_filter sofa --episode_id 0 \
  --llm_answer_path /workspace/ApexNav/llm/answers/llm_answer_hm3d.txt \
  --llm_response_path /workspace/ApexNav/llm/answers/llm_response_list.txt \
  --robot_scale 0.7 --camera_mode fixed_base_gimbal \
  --force_spawn_json "$SPAWN" \
  >"$LOGDIR/episode_stdout.log" 2>&1
rc=$?
set -e
echo "EPISODE_RC=$rc"

# dump inflation lines
grep -E "effective obstacles|soft_cost|lock_obstacles|free\(\)|process has died" "$LOGDIR/exploration.log" | head -40 || true
if [[ -f $OUT/summary.json ]]; then
  python3 -c "import json;s=json.load(open('$OUT/summary.json'));print({k:s.get(k) for k in ('termination','n_steps','status','error','n_blocked_exec','n_truncated_exec','executor_version','camera_mode','robot_scale','max_steps','max_explore_actions')})"
fi

# cleanup our ROS only
kill $EXP_PID 2>/dev/null || true
pkill -f "roscore -p 11323" 2>/dev/null || true
pkill -f "ROS_MASTER_URI=http://127.0.0.1:11323" 2>/dev/null || true
echo DONE_INSIDE rc=$rc RUN_ID=$RUN_ID
exit $rc
