#!/usr/bin/env bash
# Verify shared VLN assets on A6000 after manual downloads.
set -euo pipefail
ROOT=/media/ubuntu/D/VLN_shared
ok=0; miss=0

check() {
  local path="$1"; local min_bytes="${2:-1}"; local label="$3"
  if [[ -e "$path" ]]; then
    local sz
    sz=$(stat -c%s "$path" 2>/dev/null || echo 0)
    if [[ "$sz" -ge "$min_bytes" ]]; then
      echo "OK  $label  ($sz bytes)  $path"
      ok=$((ok+1))
    else
      echo "SMALL $label  ($sz < $min_bytes)  $path"
      miss=$((miss+1))
    fi
  else
    echo "MISS $label  $path"
    miss=$((miss+1))
  fi
}

echo "=== checkpoints ==="
check "$ROOT/checkpoints/grounding_dino/groundingdino_swint_ogc.pth" 600000000 "GroundingDINO"
check "$ROOT/checkpoints/mobile_sam/mobile_sam.pt" 30000000 "MobileSAM"
check "$ROOT/checkpoints/yolov7/yolov7-e6e.pt" 100000000 "YOLOv7-e6e"
check "$ROOT/checkpoints/pointnav/pointnav_weights.pth" 10000000 "PointNav"
check "$ROOT/checkpoints/sam/sam_l.pt" 1000000000 "SAM-L (MSGNav)"

echo "=== datasets ==="
check "$ROOT/datasets/objectnav/hm3d/v1/val/val.json.gz" 1000 "ObjectNav HM3D v1 val"
check "$ROOT/datasets/objectnav/hm3d/v2/val/val.json.gz" 1000 "ObjectNav HM3D v2 val"
# scene dataset: any scene folder under val
if compgen -G "$ROOT/datasets/scene_datasets/hm3d/val/*/" > /dev/null; then
  echo "OK  HM3D val scenes under $ROOT/datasets/scene_datasets/hm3d/val"
  ok=$((ok+1))
else
  echo "MISS HM3D val scenes  $ROOT/datasets/scene_datasets/hm3d/val/*"
  miss=$((miss+1))
fi

echo "=== summary: ok=$ok miss=$miss ==="
exit $(( miss > 0 ? 2 : 0 ))
