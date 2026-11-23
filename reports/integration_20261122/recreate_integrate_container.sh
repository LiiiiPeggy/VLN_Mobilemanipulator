#!/usr/bin/env bash
# ################################
# Recreate vln-rangercr10-integrate mounted on the single workspace root.
# Also stop retired agentA/agentB containers and wipe leftover integrate tree.
# ################################
set -euo pipefail
MAIN=/home/ubuntu/locomani/VLN_Mobilemanipulator
INT=/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate
COMPOSE="$MAIN/adapters/habitat_rangercr10/docker-compose.integrate.yml"
LOG="$MAIN/reports/integration_20261122/recreate_integrate_container.log"
exec > >(tee "$LOG") 2>&1

echo "[recreate] begin $(date -Is)"
docker stop vln-rangercr10-integrate || true
docker rm vln-rangercr10-integrate || true
docker stop vln-rangercr10-agentA-navinf || true
docker stop vln-rangercr10-agentB-nofrontier || true

docker compose -f "$COMPOSE" -p vln_rangercr10_integrate up -d
docker inspect vln-rangercr10-integrate --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
docker exec vln-rangercr10-integrate bash -lc \
  'test -f /workspace/VLN_Mobilemanipulator/reports/integration_20261122/pose_look_views/init_side_clear.png && echo CONTAINER_POSE_OK'

if [[ -d "$INT" ]]; then
  docker run --rm -v "$INT:/wt" alpine chown -R 1000:1000 /wt || true
  rm -rf "$INT" || true
fi
if [[ -e "$INT" ]]; then
  echo "WARN integrate still exists"
  ls -la "$INT" | head || true
else
  echo "integrate_gone"
fi
echo "[recreate] done $(date -Is)"
