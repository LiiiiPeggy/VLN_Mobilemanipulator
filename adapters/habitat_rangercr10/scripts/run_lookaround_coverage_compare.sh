#!/usr/bin/env bash
# Mapping-only yaw-step coverage compare (DIAGNOSTIC — not formal ObjectNav eval).
# Restarts exploration_node between step sizes so /grid_map does not accumulate.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT_ROOT="${OUT_ROOT:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/lookaround_coverage_compare_$(date +%Y%m%d_%H%M%S)}"
FORCE_SPAWN_JSON="${FORCE_SPAWN_JSON:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_yr17_openband_20261105_012302/start_pose.json}"
PPO_RAISE_JSON="${PPO_RAISE_JSON:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json}"
SCENE_GLB="${SCENE_GLB:-/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d_v0.2/val/00831-yr17PDCnDDW/yr17PDCnDDW.basis.glb}"
GPU="${GPU:-0}"
STEPS="${STEPS:-30,15,45}"
ROBOT_SCALE="${ROBOT_SCALE:-0.7}"
LABEL="${LABEL:-chair}"
ROS_PORT="${ROS_PORT:-11312}"
PROFILE="${INFLATION_PROFILE:-legacy018}"

mkdir -p "$OUT_ROOT"
# docker writes as root; keep host-writable for merge step
chmod 777 "$OUT_ROOT" || true
echo "OUT_ROOT=$OUT_ROOT"

bash "$ROOT/adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh" vln-rangercr10 || true
APEX_SRC="/workspace/VLN_Mobilemanipulator/baselines/ApexNav"
APEX="/workspace/ApexNav"
docker exec vln-rangercr10 bash -lc "
  if [[ ! -L '$APEX' || \$(readlink -f '$APEX') != \$(readlink -f '$APEX_SRC') ]]; then
    rm -rf '$APEX'; ln -sfn '$APEX_SRC' '$APEX'
  fi
"
SRC_ROS="source /opt/ros/noetic/setup.bash; source $APEX/devel/setup.bash; export ROS_MASTER_URI=http://127.0.0.1:${ROS_PORT}; export ROS_IP=127.0.0.1; export ROS_HOSTNAME=127.0.0.1; cd $APEX"
LAUNCH_FILE="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/launch/exploration_rangercr10.launch"
case "$PROFILE" in
  ranger_safe) OVERLAY="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay.yaml" ;;
  mid030) OVERLAY="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_mid030.yaml" ;;
  *) OVERLAY="/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/config/apexnav_rangercr10_overlay_legacy018.yaml" ;;
esac
HF_ENV="export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1"

docker exec -u root vln-rangercr10 bash -lc "pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; sleep 1; true" || true
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; roscore -p ${ROS_PORT} >$OUT_ROOT/roscore.log 2>&1"
sleep 2
docker exec vln-rangercr10 bash -lc 'ln -sfn /media/ubuntu/D/VLN_shared/cache/huggingface/bert-base-uncased /workspace/ApexNav/bert-base-uncased' || true
docker exec -d vln-rangercr10 bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.itm.blip2itm --port 12182 >$OUT_ROOT/blip2.log 2>&1" || true
sleep 5

IFS=',' read -r -a STEP_ARR <<< "$STEPS"
for Sraw in "${STEP_ARR[@]}"; do
  S="$(echo "$Sraw" | tr -d ' ')"
  echo "=== condition yaw_step=${S} ==="
  docker exec -u root vln-rangercr10 bash -lc "pkill -9 -f exploration_node 2>/dev/null; sleep 1; true" || true
  docker exec -d vln-rangercr10 bash -lc \
    "$SRC_ROS; roslaunch $LAUNCH_FILE ranger_overlay:=$OVERLAY >$OUT_ROOT/exploration_${S}.log 2>&1"
  # wait for node
  ok=0
  for i in $(seq 1 40); do
    if docker exec vln-rangercr10 bash -lc "$SRC_ROS; rosnode list 2>/dev/null | grep -q exploration_node"; then
      ok=1; break
    fi
    sleep 2
  done
  if [[ "$ok" != "1" ]]; then
    echo "WARN: exploration_node not up for step=$S" >&2
    docker exec vln-rangercr10 bash -lc "tail -40 $OUT_ROOT/exploration_${S}.log" || true
    continue
  fi
  docker exec \
    -e ROS_MASTER_URI="http://127.0.0.1:${ROS_PORT}" \
    -e ROS_IP=127.0.0.1 \
    -e ROS_HOSTNAME=127.0.0.1 \
    -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
    vln-rangercr10 bash -lc "$SRC_ROS; $HF_ENV; python -m src.lookaround_coverage_compare \
      --out_root '$OUT_ROOT' \
      --scene '$SCENE_GLB' \
      --gpu $GPU \
      --robot_scale $ROBOT_SCALE \
      --force_spawn_json '$FORCE_SPAWN_JSON' \
      --ppo_raise_json '$PPO_RAISE_JSON' \
      --label '$LABEL' \
      --steps '$S' \
      >'$OUT_ROOT/run_${S}.log' 2>&1" || true
done

docker exec -u root vln-rangercr10 bash -lc "pkill -9 -f 'roscore -p ${ROS_PORT}' 2>/dev/null; pkill -9 -f exploration_node 2>/dev/null; pkill -9 -f tsp_node 2>/dev/null; true" || true
docker exec -u root vln-rangercr10 chown -R 1000:1000 "$OUT_ROOT" || true
python3 - <<PY
import json
from pathlib import Path
root=Path("$OUT_ROOT")
steps=[s.strip() for s in "$STEPS".split(",") if s.strip()]
merged={"note":"DIAGNOSTIC mapping-only; exploration_node restarted per step_deg; TURN_DOWN before yaw","inflation_profile":"$PROFILE","conditions":{}}
lines=["# Lookaround yaw-step coverage compare (diagnostic)","","| step_deg | n_views | overlap_deg | occ | free | val | false_occ |","|---|---|---|---|---|---|---|"]
for s in steps:
  p=root/f"yawstep_{int(float(s)):02d}"/"summary.json"
  if not p.exists():
    lines.append(f"| {s} | ERR | | | | | |")
    err=root/f"run_{s}.log"
    if err.exists():
      print("----", err, "tail ----"); print("\n".join(err.read_text().splitlines()[-40:]))
    continue
  c=json.loads(p.read_text())
  merged["conditions"][str(s)]=c
  m=c.get("final_map") or {}
  ov=(c.get("overlap") or {}).get("overlap_deg")
  gt=c.get("gt_false_occupied_probe") or {}
  gt_r=gt.get("false_occupied_rate_est", gt.get("false_occupied_rate"))
  lines.append(f"| {s} | {c.get('n_views')} | {ov} | {m.get('occupied')} | {m.get('free')} | {m.get('value_map')} | {gt_r} |")
(root/"compare_summary.json").write_text(json.dumps(merged, indent=2))
(root/"COMPARE.md").write_text("\n".join(lines)+"\n\nNot formal ObjectNav eval. Same spawn/arm/scale/inflation; TURN_DOWN then yaw-only.\n")
print((root/"COMPARE.md").read_text())
PY
echo "DONE $OUT_ROOT"
