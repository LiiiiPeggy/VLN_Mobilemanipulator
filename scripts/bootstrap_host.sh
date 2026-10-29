#!/usr/bin/env bash
# Host bootstrap: shared links, containers, small weight downloads.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
SHARED=/media/ubuntu/D/VLN_shared
cd "$ROOT"

docker run --rm \
  -v "$SHARED:/shared" \
  -v /home/ubuntu/locomani:/locomani \
  -v "$ROOT:/w" \
  alpine:3.20 sh -c '
set -e
chown -R 1000:1000 /shared
rm -f /shared/checkpoints/grounding_dino/* /shared/checkpoints/pointnav/* /shared/checkpoints/clip/* || true
ln -sfn /home/ubuntu/locomani/NBV_Mobilemanipulator/checkpoints/grounding_dino/groundingdino_swint_ogc.pth /shared/checkpoints/grounding_dino/groundingdino_swint_ogc.pth
ln -sfn /home/ubuntu/locomani/NBV_Mobilemanipulator/checkpoints/grounding_dino/GroundingDINO_SwinT_OGC.py /shared/checkpoints/grounding_dino/GroundingDINO_SwinT_OGC.py
ln -sfn /home/ubuntu/locomani/VLN_Mobilemanipulator/baselines/VLFM/data/pointnav_weights.pth /shared/checkpoints/pointnav/pointnav_weights.pth
ln -sfn /home/ubuntu/locomani/VLN_Mobilemanipulator/baselines/VLFM/data/spot_pointnav_weights.pth /shared/checkpoints/pointnav/spot_pointnav_weights.pth
ln -sfn /home/ubuntu/locomani/DovSG/checkpoints/CLIP-ViT-H-14-laion2B-s32B-b79K /shared/checkpoints/clip/CLIP-ViT-H-14-laion2B-s32B-b79K
mkdir -p /w/baselines/VLFM/data /w/baselines/ApexNav/data
ln -sfn /media/ubuntu/D/VLN_shared/checkpoints/grounding_dino/groundingdino_swint_ogc.pth /w/baselines/VLFM/data/groundingdino_swint_ogc.pth
ln -sfn /media/ubuntu/D/VLN_shared/checkpoints/grounding_dino/groundingdino_swint_ogc.pth /w/baselines/ApexNav/data/groundingdino_swint_ogc.pth
chown -R 1000:1000 /shared /w/baselines/VLFM/data /w/baselines/ApexNav/data
echo FIX_OK
'

docker tag pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime vln-lite:latest
docker tag vln-lite:latest vln-habitat024:latest
docker tag vln-lite:latest vln-habitat025:latest
docker tag vln-lite:latest vln-apexnav:latest

for p in VLFM ApexNav MSGNav APRR SG-Nav UniGoal; do
  docker compose -f "baselines/$p/docker-compose.yml" up -d --no-build
  echo "UP_$p"
done
docker ps --filter name=vln- --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

export https_proxy="${https_proxy:-http://127.0.0.1:7897}"
export http_proxy="${http_proxy:-http://127.0.0.1:7897}"
wget -c -O "$SHARED/checkpoints/mobile_sam/mobile_sam.pt" \
  https://github.com/ChaoningZhang/MobileSAM/raw/master/weights/mobile_sam.pt
wget -c -O "$SHARED/checkpoints/yolov7/yolov7-e6e.pt" \
  https://github.com/WongKinYiu/yolov7/releases/download/v0.1/yolov7-e6e.pt
ls -lh "$SHARED/checkpoints/mobile_sam/mobile_sam.pt" "$SHARED/checkpoints/yolov7/yolov7-e6e.pt"
ln -sfn "$SHARED/checkpoints/mobile_sam/mobile_sam.pt" baselines/VLFM/data/mobile_sam.pt
ln -sfn "$SHARED/checkpoints/yolov7/yolov7-e6e.pt" baselines/VLFM/data/yolov7-e6e.pt
ln -sfn "$SHARED/checkpoints/mobile_sam/mobile_sam.pt" baselines/ApexNav/data/mobile_sam.pt
ln -sfn "$SHARED/checkpoints/yolov7/yolov7-e6e.pt" baselines/ApexNav/data/yolov7-e6e.pt
bash scripts/verify_shared_assets.sh || true
echo ALL_DONE
