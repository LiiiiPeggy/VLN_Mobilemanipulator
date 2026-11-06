#!/usr/bin/env bash
set -euo pipefail
ROS_PORT="${ROS_PORT:-11319}"
OUT="${OUT:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/map_turndown_probe_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUT"
APEX=/workspace/ApexNav
SRC="source /opt/ros/noetic/setup.bash; source $APEX/devel/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}; export ROS_IP=127.0.0.1; export ROS_HOSTNAME=127.0.0.1; cd $APEX"
LAUNCH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/launch/exploration_rangercr10.launch
OVERLAY=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_legacy018.yaml

docker exec -u root vln-rangercr10 bash -lc "pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; pkill -9 -f tsp_node 2>/dev/null; sleep 2; true" || true
docker exec -d vln-rangercr10 bash -lc "$SRC; roscore -p ${ROS_PORT} >$OUT/roscore.log 2>&1"
sleep 3
docker exec -d vln-rangercr10 bash -lc "$SRC; roslaunch $LAUNCH ranger_overlay:=$OVERLAY >$OUT/exp.log 2>&1"
sleep 8

HOST_PY="$(cd "$(dirname "$0")" && pwd)/_probe_turndown_map.py"
docker cp "$HOST_PY" vln-rangercr10:/tmp/_probe_turndown_map.py

docker exec \
  -e OUT="$OUT" \
  -e ROS_MASTER_URI="http://127.0.0.1:${ROS_PORT}" \
  -e ROS_IP=127.0.0.1 -e ROS_HOSTNAME=127.0.0.1 \
  -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  -e TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch \
  -e HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface \
  vln-rangercr10 bash -lc \
  "source /opt/ros/noetic/setup.bash; source /workspace/ApexNav/devel/setup.bash; \
   cd /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10; \
   python3 /tmp/_probe_turndown_map.py" >"$OUT/run.log" 2>&1 || true

echo "OUT=$OUT"
tail -20 "$OUT/run.log" || true
test -f "$OUT/td.json" && cat "$OUT/td.json" || true
