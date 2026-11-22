#!/usr/bin/env bash
# ################################
# Safely ensure /workspace/ApexNav → baselines/ApexNav without wiping B source.
# Image-baked /workspace/ApexNav is relocated to ApexNav.image_bak once.
# NEVER rm -rf a host bind-mount of the B ApexNav tree.
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
  # Detect bind-mount of the live B source (same device+inode as APEX_SRC).
  src_id=\$(stat -c '%d:%i' \"\$APEX_SRC\")
  apex_id=\$(stat -c '%d:%i' \"\$APEX\")
  if [[ \"\$src_id\" == \"\$apex_id\" ]]; then
    echo \"OK \$APEX is same inode as source (bind-mount); leave as-is (no rm)\"
    exit 0
  fi
  # Image-baked or foreign tree: relocate, do not destroy B mount.
  bak=\"\${APEX}.image_bak\"
  if [[ -e \"\$bak\" ]]; then
    echo \"ERROR: \$APEX exists and \$bak already present; manual cleanup needed\" >&2
    exit 3
  fi
  echo \"Relocating image/foreign \$APEX -> \$bak then symlink to B source\"
  mv \"\$APEX\" \"\$bak\"
  ln -sfn \"\$APEX_SRC\" \"\$APEX\"
  echo \"OK symlink \$APEX -> \$(readlink -f \$APEX)\"
  exit 0
fi
ln -sfn \"\$APEX_SRC\" \"\$APEX\"
echo \"OK created symlink \$APEX -> \$(readlink -f \$APEX)\"
"
