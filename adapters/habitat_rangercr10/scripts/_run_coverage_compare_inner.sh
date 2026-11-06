#!/bin/bash
# Runs inside vln-rangercr10 as root. DIAGNOSTIC yaw-step coverage compare.
set -euo pipefail
OUT_ROOT="${1:?out_root}"
STEPS="${2:-15,30,45}"
ROS_PORT="${ROS_PORT:-11312}"
PROFILE="${INFLATION_PROFILE:-legacy018}"

mkdir -p "$OUT_ROOT"
exec > >(tee -a "$OUT_ROOT/driver.log") 2>&1
echo "OUT_ROOT=$OUT_ROOT STEPS=$STEPS"

APEX_SRC=/workspace/VLN_Mobilemanipulator/baselines/ApexNav
APEX=/workspace/ApexNav
if [[ ! -L "$APEX" || $(readlink -f "$APEX") != $(readlink -f "$APEX_SRC") ]]; then
  rm -rf "$APEX"; ln -sfn "$APEX_SRC" "$APEX"
fi
case "$PROFILE" in
  ranger_safe) OVERLAY=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay.yaml ;;
  mid030) OVERLAY=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_mid030.yaml ;;
  *) OVERLAY=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_legacy018.yaml ;;
esac
LAUNCH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/launch/exploration_rangercr10.launch

set +u
export ROS_DISTRO=noetic
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
set -u
export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}
export ROS_IP=127.0.0.1
export ROS_HOSTNAME=127.0.0.1

pkill -9 -f "roscore -p ${ROS_PORT}" 2>/dev/null || true
pkill -9 -f exploration_node 2>/dev/null || true
pkill -9 -f tsp_node 2>/dev/null || true
pkill -9 -f "blip2itm --port 12182" 2>/dev/null || true
sleep 2

roscore -p ${ROS_PORT} >"$OUT_ROOT/roscore.log" 2>&1 &
sleep 3
ln -sfn /media/ubuntu/D/VLN_shared/cache/huggingface/bert-base-uncased /workspace/ApexNav/bert-base-uncased || true
(
  export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch
  export HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface
  export TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1
  cd /workspace/ApexNav
  python3 -m vlm.itm.blip2itm --port 12182 >"$OUT_ROOT/blip2.log" 2>&1
) &
sleep 5

IFS=',' read -r -a STEP_ARR <<< "$STEPS"
for Sraw in "${STEP_ARR[@]}"; do
  S="$(echo "$Sraw" | tr -d ' ')"
  echo "=== condition yaw_step=${S} ==="
  pkill -9 -f exploration_node 2>/dev/null || true
  pkill -9 -f tsp_node 2>/dev/null || true
  sleep 1
  roslaunch "$LAUNCH" ranger_overlay:="$OVERLAY" >"$OUT_ROOT/exploration_${S}.log" 2>&1 &
  ok=0
  for i in $(seq 1 40); do
    if rosnode list 2>/dev/null | grep -q exploration_node; then ok=1; break; fi
    sleep 2
  done
  if [[ "$ok" != "1" ]]; then
    echo "WARN: exploration_node not up for step=$S"
    tail -40 "$OUT_ROOT/exploration_${S}.log" || true
    continue
  fi
  bash /tmp/_run_one_yawstep.sh "$OUT_ROOT" "$S" >"$OUT_ROOT/run_${S}.log" 2>&1 || true
  YDIR="$OUT_ROOT/yawstep_$(printf '%02d' "${S%.*}")"
  if [[ -f "$YDIR/summary.json" ]]; then
    echo "OK step=$S"
    python3 -c "import json;c=json.load(open('$YDIR/summary.json'));m=c.get('final_map',{});print('final',m)"
  else
    echo "FAIL step=$S"
    tail -40 "$OUT_ROOT/run_${S}.log" || true
  fi
done

pkill -9 -f "roscore -p ${ROS_PORT}" 2>/dev/null || true
pkill -9 -f exploration_node 2>/dev/null || true
pkill -9 -f tsp_node 2>/dev/null || true
pkill -9 -f "blip2itm --port 12182" 2>/dev/null || true

python3 - <<PY
import json
from pathlib import Path
root=Path("$OUT_ROOT")
steps=[s.strip() for s in "$STEPS".split(",") if s.strip()]
merged={"note":"DIAGNOSTIC mapping-only; TURN_DOWN then yaw; exploration restarted per step","inflation_profile":"$PROFILE","conditions":{}}
lines=["# Lookaround yaw-step coverage compare (diagnostic)","","| step_deg | n_views | overlap_deg | occ | free | val | false_occ |","|---|---|---|---|---|---|---|"]
for s in steps:
  p=root/f"yawstep_{int(float(s)):02d}"/"summary.json"
  if not p.exists():
    lines.append(f"| {s} | ERR | | | | | |")
    continue
  c=json.loads(p.read_text())
  merged["conditions"][str(s)]=c
  m=c.get("final_map") or {}
  ov=(c.get("overlap") or {}).get("overlap_deg")
  gt=c.get("gt_false_occupied_probe") or {}
  gt_r=gt.get("false_occupied_rate_est", gt.get("false_occupied_rate"))
  lines.append(f"| {s} | {c.get('n_views')} | {ov} | {m.get('occupied')} | {m.get('free')} | {m.get('value_map')} | {gt_r} |")
(root/"compare_summary.json").write_text(json.dumps(merged, indent=2))
(root/"COMPARE.md").write_text("\n".join(lines)+"\n\nNot formal ObjectNav eval. Same spawn/TURN_DOWN arm/scale/inflation.\n")
print((root/"COMPARE.md").read_text())
PY
chown -R 1000:1000 "$OUT_ROOT" || true
echo "DONE $OUT_ROOT"
