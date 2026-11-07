#!/usr/bin/env bash
# UniGoal smoke (IIN). Paper HM3D IIN: SR≈60.2 SPL≈23.7; TextNav SR≈20.2 SPL≈11.4.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GOAL_TYPE="${GOAL_TYPE:-ins-image}"
CFG="${CFG:-configs/config_habitat_luna_1ep.yaml}"
STAMP="${STAMP:-$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$ROOT/runs/UniGoal" "/media/ubuntu/D/VLN_shared/runs/UniGoal"
set -a
# shellcheck disable=SC1091
source "$ROOT/baselines/UniGoal/.env"
set +a
LOG="/workspace/runs/${STAMP}_${GOAL_TYPE}.log"
docker exec -e OPENAI_API_KEY -e GPT_OPENAI_KEY -e OPENAI_BASE_URL -e GPT_END_POINT \
  -e GPT_MODEL -e GPT_VLM_MODEL \
  -e BERT_BASE_UNCASED_PATH=/shared/cache/huggingface/bert-base-uncased \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e OPENAI_TIMEOUT="${OPENAI_TIMEOUT:-180}" \
  -e VLM_MAX_SIDE="${VLM_MAX_SIDE:-384}" \
  -e OPENAI_CALL_RETRIES="${OPENAI_CALL_RETRIES:-8}" \
  vln-unigoal bash -lc "
set -euo pipefail
cd /workspace/UniGoal
export PYTHONUNBUFFERED=1
export PYTHONPATH=/workspace/UniGoal/third_party/Grounded-Segment-Anything/segment_anything:\${PYTHONPATH:-}
python -u main.py --config-file ${CFG} --goal_type ${GOAL_TYPE} 2>&1 | tee ${LOG}
"
echo "DONE log=${LOG}"
