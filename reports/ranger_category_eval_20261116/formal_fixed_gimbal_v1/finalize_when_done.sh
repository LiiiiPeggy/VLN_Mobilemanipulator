#!/usr/bin/env bash
# ################################
# Poll formal JSONL until n_jobs reached, then write accounting + archive pointer.
# Does not kill any processes; safe alongside Cursor A queue.
# ################################
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
REP=$ROOT/reports/ranger_category_eval_20261116
FORM=$REP/formal_fixed_gimbal_v1
BATCH_ID="${BATCH_ID:-formal150_full_20261117_190344}"
JSONL=$FORM/batch_${BATCH_ID}.jsonl
META=$FORM/batch_${BATCH_ID}_meta.json
VALIDITY=$REP/lists/independent_list_validity_v1_post.json
[[ -f "$VALIDITY" ]] || VALIDITY=$REP/lists/independent_list_validity_v1.json
N_EXPECT=$(python3 -c "import json; print(json.load(open('$META')).get('n_jobs',109))")
LOG=$FORM/finalize_watcher.log
exec >>"$LOG" 2>&1
echo "[finalize] watch $JSONL expect=$N_EXPECT $(date -Is)"

while true; do
  n=0
  [[ -f "$JSONL" ]] && n=$(wc -l <"$JSONL")
  echo "[finalize] have=$n / $N_EXPECT $(date -Is)"
  if [[ "$n" -ge "$N_EXPECT" ]]; then
    break
  fi
  # also exit if formal launcher died and no progress for long — still write partial
  if [[ -f "$FORM/latest_full_pid.txt" ]]; then
    fp=$(cat "$FORM/latest_full_pid.txt" || true)
    if [[ -n "${fp:-}" ]] && ! kill -0 "$fp" 2>/dev/null; then
      echo "[finalize] formal pid dead with have=$n; writing partial accounting"
      break
    fi
  fi
  sleep 120
done

python3 "$ROOT/adapters/habitat_rangercr10/evaluation/scripts/write_formal_accounting_report.py" \
  "$JSONL" \
  --validity "$VALIDITY" \
  --out_json "$FORM/accounting_${BATCH_ID}.json" \
  --out_md "$FORM/accounting_${BATCH_ID}.md"

python3 "$ROOT/adapters/habitat_rangercr10/evaluation/scripts/summarize_category_metrics.py" \
  "$JSONL" --out "$FORM/summary_${BATCH_ID}.json" || true

# Archive pointer (do not mix with short50)
python3 - <<PY
import json
from pathlib import Path
from datetime import datetime, timezone
rep = Path("$REP")
arch = rep / "archives"
arch.mkdir(exist_ok=True)
doc = {
  "archive_id": "formal_independent_v1_150_100",
  "batch_id": "$BATCH_ID",
  "role": "frozen_independent_eval",
  "jsonl": str(Path("$JSONL")),
  "accounting": str(Path("$FORM/accounting_${BATCH_ID}.json")),
  "validity": "$VALIDITY",
  "camera_mode": "fixed_base_gimbal",
  "budget": {"max_steps": 150, "max_explore_actions": 100},
  "written_utc": datetime.now(timezone.utc).isoformat(),
  "note": "Per-run executor_version/SHA from artifacts; do not mix with short50 or hist 8/24.",
}
(arch / "02_formal_independent_v1.json").write_text(json.dumps(doc, indent=2) + "\n")
print("wrote", arch / "02_formal_independent_v1.json")
PY

echo "[finalize] done $(date -Is)"
