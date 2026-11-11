#!/usr/bin/env bash
# Host: MSGNav 20ep with GPT-4o + API usage summary.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
OUT=/media/ubuntu/D/VLN_shared/runs/MSGNav_gpt4o_20ep/gpt4o_20ep_20261106
HOST_STATUS="$ROOT/runs/MSGNav/gpt4o_20ep_status.md"
mkdir -p "$OUT" "$(dirname "$HOST_STATUS")"
chmod +x "$ROOT/baselines/MSGNav/run_20ep_gpt4o_inner.sh"

docker exec -w /workspace/MSGNav \
  -e GPT_MODEL=gpt-4o \
  -e API_MODE=gpt \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e HF_HOME=/shared/cache/huggingface \
  -e HUGGINGFACE_HUB_CACHE=/shared/cache/huggingface/hub \
  -e PYTHONUNBUFFERED=1 \
  vln-msgnav \
  bash /workspace/MSGNav/run_20ep_gpt4o_inner.sh

{
  echo "# MSGNav GPT-4o 20ep — $(date '+%Y-%m-%d %H:%M %Z')"
  echo
  echo "## Metrics"
  echo '```'
  cat "$OUT/metrics.csv" 2>/dev/null || true
  echo '```'
  echo
  echo "## API usage"
  echo '```'
  cat "$OUT/api_usage_summary.json" 2>/dev/null || true
  echo '```'
  echo
  echo "| Item | Path |"
  echo "|------|------|"
  echo "| Metrics | \`$OUT/metrics.csv\` |"
  echo "| API summary | \`$OUT/api_usage_summary.json\` |"
  echo "| Usage jsonl | \`$OUT/api_usage.jsonl\` |"
} > "$HOST_STATUS"
echo "Wrote $HOST_STATUS"
