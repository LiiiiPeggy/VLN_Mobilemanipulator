#!/usr/bin/env bash
# Host wrapper: paper-scale ApexNav HM3D-v2 full val (1000 ep) + failure aggregation.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
STAMP=$(date +%Y%m%d_%H%M%S)
OUT=/media/ubuntu/D/VLN_shared/runs/ApexNav/hm3dv2_full_${STAMP}
REPORT=$ROOT/reports/apexnav_hm3dv2_full_${STAMP}
mkdir -p "$OUT" "$REPORT"
echo "$OUT" | tee "$REPORT/out_path.txt" "$OUT/out_path.txt"
chmod +x "$ROOT/baselines/ApexNav/run_hm3dv2_full_inner.sh"
# Sync script into container workspace if bind-mounted; ApexNav root is usually the baseline dir.
docker exec -u root vln-apexnav bash -lc \
  "cp -f /workspace/VLN_Mobilemanipulator/baselines/ApexNav/run_hm3dv2_full_inner.sh /workspace/ApexNav/run_hm3dv2_full_inner.sh && chmod +x /workspace/ApexNav/run_hm3dv2_full_inner.sh" \
  2>/dev/null || true
docker exec -w /workspace/ApexNav \
  -e APEXNAV_FULL_OUT="$OUT" \
  -e APEXNAV_FULL_STAMP="$STAMP" \
  vln-apexnav bash /workspace/ApexNav/run_hm3dv2_full_inner.sh
# Copy summary into reports when finished
if [[ -f "$OUT/summary.json" ]]; then
  cp -f "$OUT/summary.json" "$OUT/failure_hist.json" "$REPORT/" 2>/dev/null || true
fi
echo "DONE out=$OUT report=$REPORT"
