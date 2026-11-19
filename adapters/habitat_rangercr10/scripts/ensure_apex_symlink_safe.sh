#!/usr/bin/env bash
# ################################
# Safely ensure /workspace/ApexNav → baselines/ApexNav without wiping source.
# NEVER rm -rf a real directory or bind-mount of ApexNav.
# ################################
set -euo pipefail
CONTAINER="${1:?container name}"
APEX="${2:-/workspace/ApexNav}"
APEX_SRC="${3:-/workspace/VLN_Mobilemanipulator/baselines/ApexNav}"

docker exec "$CONTAINER" bash -lc "
set -euo pipefail
APEX='$APEX'
APEX_SRC='$APEX_SRC'
if [[ ! -d \"\$APEX_SRC\" ]]; then
  echo \"ERROR: ApexNav source missing: \$APEX_SRC\" >&2
  exit 2
fi
if [[ -L \"\$APEX\" ]]; then
  cur=\$(readlink -f \"\$APEX\" || true)
  want=\$(readlink -f \"\$APEX_SRC\")
  if [[ \"\$cur\" != \"\$want\" ]]; then
    ln -sfn \"\$APEX_SRC\" \"\$APEX\"
  fi
  echo \"OK symlink \$APEX -> \$(readlink -f \$APEX)\"
  exit 0
fi
if [[ -e \"\$APEX\" ]]; then
  # Real dir / bind-mount: only OK if it already resolves to the same source.
  if [[ \"\$(readlink -f \"\$APEX\")\" == \"\$(readlink -f \"\$APEX_SRC\")\" ]]; then
    echo \"OK \$APEX already same path as source (no rm)\"
    exit 0
  fi
  echo \"REFUSE: \$APEX exists and is not a symlink to \$APEX_SRC\" >&2
  echo \"REFUSE: will not rm -rf (would wipe source mount).\" >&2
  exit 3
fi
ln -sfn \"\$APEX_SRC\" \"\$APEX\"
echo \"OK created symlink \$APEX -> \$(readlink -f \$APEX)\"
"
