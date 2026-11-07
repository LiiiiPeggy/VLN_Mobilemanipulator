#!/usr/bin/env bash
# SG-Nav smoke / small-batch ObjectNav (MP3D). Paper: MP3D val SR≈40.2 SPL≈16.0 (GPT).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_HOST="${OUT_HOST:-/media/ubuntu/D/VLN_shared/runs/SG-Nav}"
STAMP="${STAMP:-$(date +%Y%m%d_%H%M%S)}"
RUN_DIR="${OUT_HOST}/smoke_${STAMP}"
SPLIT_L="${SPLIT_L:-0}"
SPLIT_R="${SPLIT_R:-1}"  # one scene for smoke; full paper uses 0..11
mkdir -p "$RUN_DIR" "$ROOT/runs/SG-Nav"
set -a
# shellcheck disable=SC1091
source "$ROOT/baselines/SG-Nav/.env"
set +a
docker exec -e OPENAI_API_KEY -e GPT_OPENAI_KEY -e OPENAI_BASE_URL -e GPT_END_POINT \
  -e GPT_MODEL -e GPT_VLM_MODEL -e SGNAV_LLM_BACKEND \
  -e JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64 \
  -e BERT_BASE_UNCASED_PATH=/shared/cache/huggingface/bert-base-uncased \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e SGNAV_NUM_EPISODES="${SGNAV_NUM_EPISODES:-1}" \
  -e VLM_MAX_SIDE="${VLM_MAX_SIDE:-384}" \
  -e OPENAI_TIMEOUT="${OPENAI_TIMEOUT:-180}" \
  vln-sgnav bash -lc "
set -euo pipefail
cd /workspace/SG-Nav
export PYTHONUNBUFFERED=1
export SGNAV_NUM_EPISODES=\${SGNAV_NUM_EPISODES:-1}
# Avoid cwd shadowing the editable segment_anything package
export PYTHONPATH=/workspace/SG-Nav:/workspace/SG-Nav/segment_anything:\${PYTHONPATH:-}
mkdir -p /workspace/runs/smoke_${STAMP}
python -u -X faulthandler SG_Nav.py --split_l ${SPLIT_L} --split_r ${SPLIT_R} 2>&1 | tee /workspace/runs/smoke_${STAMP}/driver.log
"
echo "DONE host mirror: $RUN_DIR"
