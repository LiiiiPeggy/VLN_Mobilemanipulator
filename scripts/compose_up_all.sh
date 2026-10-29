#!/usr/bin/env bash
# Recreate all VLN containers. Must run with host-absolute cwd so bind mounts resolve on the daemon host.
set -euo pipefail
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
cd "$ROOT"
for p in VLFM ApexNav MSGNav APRR SG-Nav UniGoal; do
  docker compose -f "baselines/$p/docker-compose.yml" up -d --no-build
  echo "UP_$p"
done
docker ps --filter name=vln- --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
