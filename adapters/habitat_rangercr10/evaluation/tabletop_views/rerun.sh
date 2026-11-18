#!/usr/bin/env bash
# ################################
# VLN adapt: Cursor D tabletop pilot rerun (inside vln-rangercr10)
# ################################
set -euo pipefail
ROOT="${ROOT:-/workspace/VLN_Mobilemanipulator}"
export PYTHONPATH="${ROOT}/baselines/ApexNav:${PYTHONPATH:-}"
cd "$ROOT"
TV=adapters/habitat_rangercr10/evaluation/tabletop_views
python "$TV/test_match_unit.py"
if [[ "${1:-}" == "--watch" ]]; then
  python "$TV/watch_captures.py" --once --poll_s "${POLL_S:-10}"
else
  python "$TV/run_pilot.py" "$@"
fi
