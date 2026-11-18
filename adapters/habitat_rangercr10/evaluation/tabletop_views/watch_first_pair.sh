#!/usr/bin/env bash
# ################################
# VLN adapt: wait for A's first paired capture, then smoke detect+match+overlay
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
CAP="${CAPTURES:-$ROOT/reports/tabletop_views_pilot/captures}"
OUT="${OUT_DIR:-$ROOT/reports/tabletop_views_pilot/evaluation}"
POLL_SEC="${POLL_SEC:-30}"

echo "[watch] captures=$CAP"
while true; do
  # first pair with both modes having at least one rgb
  hit=""
  if [[ -d "$CAP" ]]; then
    for d in "$CAP"/*/; do
      [[ -d "$d" ]] || continue
      name=$(basename "$d")
      [[ "$name" == ".*" ]] && continue
      fg=$(find "$d/fixed_base_gimbal" -name 'rgb.png' -o -name 'rgb.jpg' 2>/dev/null | head -1 || true)
      ar=$(find "$d/arm_ee" -name 'rgb.png' -o -name 'rgb.jpg' 2>/dev/null | head -1 || true)
      if [[ -n "$fg" && -n "$ar" ]]; then
        hit="$name"
        break
      fi
    done
  fi
  if [[ -n "$hit" ]]; then
    echo "[watch] first pair ready: $hit"
    bash "$ROOT/adapters/habitat_rangercr10/evaluation/tabletop_views/ensure_vlm_yolo_sam.sh"
    # run inside container so get_object clients hit localhost VLM
    docker exec vln-rangercr10 bash -lc "
      source /opt/ros/noetic/setup.bash
      source /workspace/ApexNav/devel/setup.bash
      cd /workspace/ApexNav
      export PYTHONPATH=/workspace/ApexNav:/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/evaluation/tabletop_views:\${PYTHONPATH}
      python /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/evaluation/tabletop_views/run_pilot.py \
        --captures /workspace/VLN_Mobilemanipulator/reports/tabletop_views_pilot/captures \
        --out /workspace/VLN_Mobilemanipulator/reports/tabletop_views_pilot/evaluation \
        --pair '$hit'
    "
    echo "[watch] smoke done for $hit → $OUT/tables/"
    exit 0
  fi
  echo "[watch] no complete pair yet; sleep ${POLL_SEC}s"
  sleep "$POLL_SEC"
done
