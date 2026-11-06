#!/bin/bash
set -e
export OUT=/tmp/map_turndown_probe_20261106_050414
mkdir -p "$OUT"
export ROS_MASTER_URI=http://127.0.0.1:11319
export ROS_IP=127.0.0.1
export ROS_HOSTNAME=127.0.0.1
export PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10
export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch
export HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
cd /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10
python3 /tmp/_probe_turndown_map.py >"$OUT/run.log" 2>&1
cp -f "$OUT/td.json" /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/scripts/_td_result.json 2>/dev/null || true
cat "$OUT/td.json"
