#!/usr/bin/env bash
# Verify shared VLN assets on A6000 after manual downloads.
set -euo pipefail
ROOT=/media/ubuntu/D/VLN_shared
ok=0; miss=0

# Dereference symlinks when measuring size (GNU stat: -L).
filesize() {
  local path="$1"
  if [[ -L "$path" ]]; then
    if [[ ! -e "$path" ]]; then
      echo 0
      return
    fi
    stat -L -c%s "$path" 2>/dev/null || echo 0
  else
    stat -c%s "$path" 2>/dev/null || echo 0
  fi
}

check() {
  local path="$1"; local min_bytes="${2:-1}"; local label="$3"
  if [[ -e "$path" || -L "$path" ]]; then
    if [[ -L "$path" && ! -e "$path" ]]; then
      echo "BROKEN_SYMLINK $label  $path -> $(readlink "$path")"
      miss=$((miss+1))
      return
    fi
    local sz
    sz=$(filesize "$path")
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

# ObjectNav episode indexes (val.json.gz) are intentionally tiny; payload is under content/.
check_objectnav_split() {
  local split_dir="$1"; local label="$2"
  local index="$split_dir/$(basename "$split_dir").json.gz"
  # Habitat uses val/val.json.gz, val_mini/val_mini.json.gz, etc.
  local base
  base=$(basename "$split_dir")
  index="$split_dir/${base}.json.gz"
  local content="$split_dir/content"
  if [[ ! -e "$index" ]]; then
    echo "MISS $label index  $index"
    miss=$((miss+1))
    return
  fi
  if [[ ! -d "$content" ]]; then
    echo "MISS $label content/  $content"
    miss=$((miss+1))
    return
  fi
  local n bytes
  n=$(find "$content" -type f -name '*.json.gz' 2>/dev/null | wc -l)
  bytes=$(du -sb "$content" 2>/dev/null | awk '{print $1}')
  bytes=${bytes:-0}
  if [[ "$n" -ge 10 && "$bytes" -ge 500000 ]]; then
    local idx_sz
    idx_sz=$(filesize "$index")
    echo "OK  $label  (index=${idx_sz}B content_files=$n content_bytes=$bytes)  $split_dir"
    ok=$((ok+1))
  else
    echo "SMALL $label  (content_files=$n content_bytes=$bytes)  $split_dir"
    miss=$((miss+1))
  fi
  # Warn if index unreadable (e.g. root:0600)
  if [[ ! -r "$index" ]]; then
    echo "WARN $label index not readable by current user: $index (fix perms)"
  fi
}

echo "=== checkpoints ==="
check "$ROOT/checkpoints/grounding_dino/groundingdino_swint_ogc.pth" 600000000 "GroundingDINO"
check "$ROOT/checkpoints/mobile_sam/mobile_sam.pt" 30000000 "MobileSAM"
check "$ROOT/checkpoints/yolov7/yolov7-e6e.pt" 100000000 "YOLOv7-e6e"
check "$ROOT/checkpoints/pointnav/pointnav_weights.pth" 10000000 "PointNav"
check "$ROOT/checkpoints/sam/sam_vit_l_0b3195.pth" 1100000000 "SAM-L file"
check "$ROOT/checkpoints/sam/sam_l.pt" 1100000000 "SAM-L alias (MSGNav)"

echo "=== datasets ==="
check_objectnav_split "$ROOT/datasets/objectnav/hm3d/v1/val" "ObjectNav HM3D v1 val"
check_objectnav_split "$ROOT/datasets/objectnav/hm3d/v2/val" "ObjectNav HM3D v2 val"
check "$ROOT/datasets/textnav/val/val_text.json.gz" 1000 "UniGoal textnav"
check "$ROOT/datasets/scene_datasets/hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb" 1000000 "HM3D val sample glb"
# scene dataset: any scene folder under val
n_val=$(find "$ROOT/datasets/scene_datasets/hm3d/val" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
if [[ "$n_val" -ge 50 ]]; then
  echo "OK  HM3D val scenes count=$n_val under $ROOT/datasets/scene_datasets/hm3d/val"
  ok=$((ok+1))
else
  echo "MISS HM3D val scenes count=$n_val  $ROOT/datasets/scene_datasets/hm3d/val/*"
  miss=$((miss+1))
fi

echo "=== summary: ok=$ok miss=$miss ==="
exit $(( miss > 0 ? 2 : 0 ))
