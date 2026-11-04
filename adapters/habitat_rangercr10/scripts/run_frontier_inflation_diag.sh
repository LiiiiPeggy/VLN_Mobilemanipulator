#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/frontier_inflation_diag}"
export PYTHONPATH="$ROOT/adapters/habitat_rangercr10:${PYTHONPATH:-}"
python3 -m src.frontier_inflation_diag --out_root "$OUT"
echo "OUT=$OUT"
ls -la "$OUT" | head
