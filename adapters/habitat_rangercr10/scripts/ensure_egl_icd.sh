#!/usr/bin/env bash
# Restore NVIDIA EGL ICD JSON inside vln-rangercr10 if emptied (conda bullet install side-effect).
set -euo pipefail
CONTAINER="${1:-vln-rangercr10}"
ICD_PATH=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
EXPECTED='{
    "file_format_version" : "1.0.0",
    "ICD" : {
        "library_path" : "libEGL_nvidia.so.0"
    }
}'

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERROR: container $CONTAINER not running" >&2
  exit 1
fi

sz=$(docker exec "$CONTAINER" bash -lc "stat -c%s $ICD_PATH 2>/dev/null || echo 0")
if [[ "$sz" -gt 20 ]]; then
  echo "EGL ICD ok ($ICD_PATH size=$sz)"
  exit 0
fi

echo "Restoring empty/missing $ICD_PATH in $CONTAINER (was size=$sz)"
docker exec "$CONTAINER" bash -lc "cat > $ICD_PATH <<'EOF'
$EXPECTED
EOF
ls -la $ICD_PATH"
echo "Restored."
