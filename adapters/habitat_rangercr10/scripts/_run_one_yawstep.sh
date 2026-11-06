#!/bin/bash
# One yaw-step condition inside vln-rangercr10 (ROS sourced).
set -euo pipefail
OUT_ROOT="$1"
STEP="$2"
ROS_PORT="${ROS_PORT:-11312}"
PROFILE="${INFLATION_PROFILE:-legacy018}"
set +u
export ROS_DISTRO=noetic
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
set -u
export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}
export ROS_IP=127.0.0.1
export ROS_HOSTNAME=127.0.0.1
export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:${PYTHONPATH:-}
export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch
export HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
cd /workspace/ApexNav
python3 -c "import rospy; print('rospy_ok', rospy.__file__)"
cd /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10
python3 -m src.lookaround_coverage_compare \
  --out_root "$OUT_ROOT" \
  --scene /media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d_v0.2/val/00831-yr17PDCnDDW/yr17PDCnDDW.basis.glb \
  --gpu 0 \
  --robot_scale 0.7 \
  --force_spawn_json /media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_yr17_openband_20261105_012302/start_pose.json \
  --ppo_raise_json /media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json \
  --label chair \
  --steps "$STEP"
