#!/usr/bin/env bash
set -euo pipefail
CASE="${1:-/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/nav_inflation_softcost_20261118/case_wide_teesav_sofa0_seq9}"
PORT=11329
read -r CX CY YAW < <(python3 -c "import json;m=json.load(open('${CASE}/freeze_meta.json'));c=m['chassis'];print(c[0],c[1],m.get('yaw_ros') or 0)")
docker exec vln-rangercr10 bash -lc "
set -e
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
export ROS_MASTER_URI=http://127.0.0.1:${PORT}
export ROS_IP=127.0.0.1
roscore -p ${PORT} >/tmp/roscore_inf_${PORT}.log 2>&1 &
sleep 2
for spec in 'P0 0.18 0.0 0.0' 'P1 0.30429 0.0 0.0' 'P2 0.30429 0.40 2.0'; do
  set -- \$spec
  tag=\$1; inf=\$2; R=\$3; w=\$4
  echo RUNNING \$tag
  rosrun path_searching test_inflation_softcost_astar \
    _cells_csv:=${CASE}/cells.csv _candidates_csv:=${CASE}/candidates.csv \
    _chassis_x:=${CX} _chassis_y:=${CY} _yaw:=${YAW} \
    _half_l:=0.4557 _half_w:=0.30429 _expand_m:=0.3 \
    _inflate_m:=\${inf} _soft_R:=\${R} _soft_w:=\${w} \
    _startup_prior_mode:=initial_footprint \
    _out_json:=${CASE}/native_\${tag}.json
done
kill \$(pgrep -f 'roscore -p ${PORT}') 2>/dev/null || true
"
python3 -c "
import json
from pathlib import Path
case=Path('${CASE}')
for tag in ['P0','P1','P2']:
  d=json.load(open(case/f'native_{tag}.json'))
  print(tag, {k:d[k] for k in d if k!='path'})
"
