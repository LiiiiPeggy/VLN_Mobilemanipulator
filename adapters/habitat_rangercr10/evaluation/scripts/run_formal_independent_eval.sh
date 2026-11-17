#!/usr/bin/env bash
# ################################
# VLN adapt: formal independent eval on validity-filtered list (budget 150/100)
# ################################
# Run on HOST (needs docker). Does NOT modify A's core Python.
# Only episodes with status=valid are executed; originals retained in validity JSON.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
VALIDITY="${VALIDITY_JSON:-$ROOT/reports/ranger_category_eval_20261116/lists/independent_list_validity_v1_post.json}"
OUT_ROOT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real}"
REPORT_DIR="${REPORT_DIR:-$ROOT/reports/ranger_category_eval_20261116/formal_fixed_gimbal_v1}"
MAX_STEPS="${MAX_STEPS:-150}"
MAX_EXPLORE_ACTIONS="${MAX_EXPLORE_ACTIONS:-100}"
GPU="${GPU:-0}"
CAMERA_MODE="${CAMERA_MODE:-fixed_base_gimbal}"
BATCH_ID="${BATCH_ID:-formal150_$(date +%Y%m%d_%H%M%S)}"
CODE_SHA="${CODE_GIT_SHA:-$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)}"
SMOKE_N="${SMOKE_N:-0}"

mkdir -p "$REPORT_DIR" "$OUT_ROOT" "$REPORT_DIR/spawns"
JOBS="$REPORT_DIR/_jobs_${BATCH_ID}.tsv"
SUMMARY="$REPORT_DIR/batch_${BATCH_ID}.jsonl"
: > "$SUMMARY"

python3 - <<PY
import json
from pathlib import Path
doc = json.loads(Path("$VALIDITY").read_text())
rows = [e for e in doc["episodes"] if e.get("status") == "valid"]
smoke_n = int("$SMOKE_N")
if smoke_n > 0:
    rows = rows[:smoke_n]
out = Path("$JOBS")
lines = []
for e in rows:
    spawn = e.get("force_spawn_json") or ""
    if not spawn and e.get("spawn"):
        sp_path = Path("$REPORT_DIR") / "spawns" / f"{e['id']}.json"
        sp_path.parent.mkdir(parents=True, exist_ok=True)
        sp_path.write_text(json.dumps({"spawn": e["spawn"]}, indent=2) + "\n")
        spawn = str(sp_path)
    lines.append("\t".join([
        e["id"], e["scene_filter"], e["category"], str(e["episode_id"]), spawn,
    ]))
out.write_text("\n".join(lines) + ("\n" if lines else ""))
Path("$REPORT_DIR/batch_${BATCH_ID}_meta.json").write_text(json.dumps({
    "batch_id": "$BATCH_ID",
    "code_git_sha_shell": "$CODE_SHA",
    "note": "shell SHA is checkout hint; ingest prefers summary/run_config values",
    "max_steps": int("$MAX_STEPS"),
    "max_explore_actions": int("$MAX_EXPLORE_ACTIONS"),
    "camera_mode": "$CAMERA_MODE",
    "n_jobs": len(lines),
    "validity": "$VALIDITY",
}, indent=2) + "\n")
print(f"jobs={len(lines)} -> $JOBS")
PY

while IFS=$'\t' read -r EP_ID SCENE CAT EP FORCE; do
  [[ -z "${EP_ID:-}" ]] && continue
  RUN_ID="formalgimbal_${BATCH_ID}_${EP_ID}"
  echo "===== $RUN_ID ====="
  set +e
  INFLATION_PROFILE=legacy018 \
    SCENE_FILTER="$SCENE" CATEGORY_FILTER="$CAT" EPISODE_ID="$EP" \
    MAX_STEPS="$MAX_STEPS" MAX_EXPLORE_ACTIONS="$MAX_EXPLORE_ACTIONS" GPU="$GPU" \
    RUN_ID="$RUN_ID" ROBOT_SCALE=0.7 CAMERA_MODE="$CAMERA_MODE" \
    FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="" \
    STARTUP_PRIOR_MODE=initial_footprint \
    STARTUP_PRIOR_EXPAND_M=0.3 \
    OBSTACLE_DENOISE=none \
    SKIP_DEMO=1 \
    OUT_DIR="$OUT_ROOT" \
    bash "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh" \
    >"$REPORT_DIR/${RUN_ID}_host.log" 2>&1
  rc=$?
  set -e
  python3 - <<PY >>"$SUMMARY"
import json, sys
from pathlib import Path
sys.path.insert(0, "$ROOT/adapters/habitat_rangercr10/evaluation/scripts")
from ingest_episode_run import ingest_run
run = Path("$OUT_ROOT") / "$RUN_ID"
row = ingest_run(run, episode_list_id="$EP_ID", batch_id="$BATCH_ID")
row["shell_rc"] = int("$rc")
row["shell_claimed_max_steps"] = int("$MAX_STEPS")
row["shell_claimed_max_explore"] = int("$MAX_EXPLORE_ACTIONS")
row["shell_claimed_code_git_sha"] = "$CODE_SHA"
row["scene"] = "$SCENE"
row["category"] = "$CAT"
row["episode_id"] = "$EP"
row["archive_role"] = "formal_independent_v1"
print(json.dumps(row))
PY
done < "$JOBS"

echo "[formal] done summary=$SUMMARY"
python3 "$ROOT/adapters/habitat_rangercr10/evaluation/scripts/summarize_category_metrics.py" \
  "$SUMMARY" --out "$REPORT_DIR/summary_${BATCH_ID}.json"
