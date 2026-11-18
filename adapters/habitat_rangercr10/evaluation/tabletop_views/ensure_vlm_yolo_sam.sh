#!/usr/bin/env bash
# ################################
# VLN adapt: ensure YOLO:12184 + MobileSAM:12183 inside vln-rangercr10
# (DINO/BLIP optional — COCO cup/bowl/remote/bottle uses YOLO+SAM only)
# ################################
set -euo pipefail
CONTAINER="${CONTAINER:-vln-rangercr10}"
LOGDIR="${LOGDIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/vlm_stable_logs/tabletop_pilot}"
SRC_ROS='source /opt/ros/noetic/setup.bash; source /workspace/ApexNav/devel/setup.bash; cd /workspace/ApexNav; export PYTHONPATH=/workspace/ApexNav:${PYTHONPATH}'
HF_ENV="export TORCH_HOME=/media/ubuntu/D/VLN_shared/cache/torch HF_HOME=/media/ubuntu/D/VLN_shared/cache/huggingface TRANSFORMERS_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface HUGGINGFACE_HUB_CACHE=/media/ubuntu/D/VLN_shared/cache/huggingface/hub TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1"

docker exec "$CONTAINER" bash -lc "mkdir -p $LOGDIR"

need_start_yolo=1
need_start_sam=1
if docker exec "$CONTAINER" bash -lc 'python - <<"PY"
import socket
for p in (12184,12183):
  s=socket.socket(); s.settimeout(0.4)
  try:
    s.connect(("127.0.0.1",p)); s.close(); print(p,"UP")
  except Exception:
    print(p,"DOWN")
PY'; then
  :
fi
# always try start if down
docker exec "$CONTAINER" bash -lc 'python - <<"PY"
import socket
def up(p):
  s=socket.socket(); s.settimeout(0.4)
  try:
    s.connect(("127.0.0.1",p)); s.close(); return True
  except Exception:
    return False
open("/tmp/vlm_need_yolo","w").write("0" if up(12184) else "1")
open("/tmp/vlm_need_sam","w").write("0" if up(12183) else "1")
PY'

yolo_need=$(docker exec "$CONTAINER" cat /tmp/vlm_need_yolo)
sam_need=$(docker exec "$CONTAINER" cat /tmp/vlm_need_sam)
if [[ "$yolo_need" == "1" ]]; then
  echo "[vlm] starting yolov7 :12184"
  docker exec -d "$CONTAINER" bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.detector.yolov7 --port 12184 >$LOGDIR/yolov7.log 2>&1"
fi
if [[ "$sam_need" == "1" ]]; then
  echo "[vlm] starting mobile_sam :12183"
  docker exec -d "$CONTAINER" bash -lc "$SRC_ROS; $HF_ENV; python -m vlm.segmentor.sam --port 12183 >$LOGDIR/sam.log 2>&1"
fi

ok=0
for i in $(seq 1 60); do
  if docker exec "$CONTAINER" bash -lc 'python - <<"PY"
import socket
ok=True
for p in (12183,12184):
  s=socket.socket(); s.settimeout(0.5)
  try:
    s.connect(("127.0.0.1",p)); s.close()
  except Exception:
    ok=False
raise SystemExit(0 if ok else 1)
PY'; then
    ok=1
    break
  fi
  sleep 2
done
if [[ "$ok" != "1" ]]; then
  echo "ERROR: YOLO/SAM not ready; see $LOGDIR" >&2
  docker exec "$CONTAINER" bash -lc "tail -40 $LOGDIR/yolov7.log; tail -40 $LOGDIR/sam.log" || true
  exit 2
fi
echo "[vlm] YOLO+SAM ready"
