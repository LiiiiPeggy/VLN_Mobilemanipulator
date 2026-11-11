#!/usr/bin/env bash
# Inside vln-msgnav: 20 scenes × 1 ep with GPT-4o + API usage log.
set -eo pipefail
OUT=/media/ubuntu/D/VLN_shared/runs/MSGNav_gpt4o_20ep/gpt4o_20ep_20261106
mkdir -p "$OUT"
CSV="$OUT/metrics.csv"
USAGE_JSONL="$OUT/api_usage.jsonl"
USAGE_SUMMARY="$OUT/api_usage_summary.json"
echo "specific_idx,scene_file,status,success_by_distance,spl_by_distance,wall_s,peak_mem_mib,api_calls_cum,api_total_tokens_cum,logfile" > "$CSV"

cd /workspace/MSGNav
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=/shared/cache/huggingface
export HUGGINGFACE_HUB_CACHE=/shared/cache/huggingface/hub
export PYTHONUNBUFFERED=1
export GPT_MODEL="${GPT_MODEL:-gpt-4o}"
export API_MODE="${API_MODE:-gpt}"
export MSGNAV_API_USAGE_LOG="$USAGE_JSONL"
: > "$USAGE_JSONL"

mapfile -t SCENES < <(ls -1 data/objectnav_hm3d_20ep | sort)
N=${#SCENES[@]}
echo "N_SCENES=$N GPT_MODEL=$GPT_MODEL" | tee "$OUT/driver.log"

for i in $(seq 0 $((N - 1))); do
  LOG="$OUT/ep_${i}.log"
  MEM="$OUT/ep_${i}.mem"
  SCENE="${SCENES[$i]:-unknown}"
  echo "==== MSGNav gpt4o ep $i ($SCENE) ====" | tee -a "$OUT/driver.log"
  ( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 20; done ) >"$MEM" &
  MPID=$!
  START=$(date +%s)
  set +e
  python -u run_hm3d_evaluation.py -cf cfg/eval_hm3d_20ep_gpt4o.yaml --specific "$i" >"$LOG" 2>&1
  EC=$?
  set -e
  END=$(date +%s)
  kill $MPID 2>/dev/null || true
  wait $MPID 2>/dev/null || true
  PEAK=$(awk 'BEGIN{m=0}{if($1+0>m)m=$1+0}END{print m}' "$MEM")
  SR=$(grep -oE 'Success rate by distance:[[:space:]]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  SPL=$(grep -oE 'SPL by distance:[[:space:]]*[0-9.]+' "$LOG" 2>/dev/null | grep -oE '[0-9.]+$' | tail -1 || true)
  # cumulative API from last jsonl line
  CALLS=$(python -c "import json; lines=open('$USAGE_JSONL').read().splitlines(); print(json.loads(lines[-1])['cum']['calls'] if lines else 0)" 2>/dev/null || echo 0)
  TOKS=$(python -c "import json; lines=open('$USAGE_JSONL').read().splitlines(); print(json.loads(lines[-1])['cum']['total_tokens'] if lines else 0)" 2>/dev/null || echo 0)
  if [ "$EC" != 0 ]; then ST=CRASH
  elif [ "${SR:-0}" = "100.00" ] || [ "${SR:-0}" = "100" ] || [ "${SR:-0}" = "1.0" ]; then ST=TASK_SUCCESS
  else ST=TASK_FAIL
  fi
  echo "$i,$SCENE,$ST,${SR:-},${SPL:-},$((END-START)),$PEAK,$CALLS,$TOKS,$LOG" | tee -a "$CSV"
done

python - <<PY
import json
from collections import defaultdict
path="$USAGE_JSONL"
calls=ok=err=pt=ct=tt=0
models=defaultdict(lambda: {"calls":0,"prompt_tokens":0,"completion_tokens":0,"total_tokens":0})
if open(path).read().strip():
  for line in open(path):
    d=json.loads(line)
    calls+=1
    if d.get("error"): err+=1
    else: ok+=1
    pt+=d.get("prompt_tokens",0); ct+=d.get("completion_tokens",0); tt+=d.get("total_tokens",0)
    m=models[d.get("model","?")]
    m["calls"]+=1; m["prompt_tokens"]+=d.get("prompt_tokens",0); m["completion_tokens"]+=d.get("completion_tokens",0); m["total_tokens"]+=d.get("total_tokens",0)
summary={"calls":calls,"ok":ok,"errors":err,"prompt_tokens":pt,"completion_tokens":ct,"total_tokens":tt,"models":dict(models),
         "note":"USD cost depends on model8.run billing; tokens are from API usage fields when present."}
json.dump(summary, open("$USAGE_SUMMARY","w"), indent=2)
print(json.dumps(summary, indent=2))
PY

echo DONE | tee -a "$OUT/driver.log"
