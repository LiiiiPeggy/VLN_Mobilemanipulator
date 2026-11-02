#!/usr/bin/env bash
# Host wrapper: ApexNav hm3dv2 episodes 0..7 via in-container runner.
# VLM = project-local python -m vlm.{detector,itm,segmentor}.* (NOT vlfm.vlm)
set -euo pipefail
chmod +x /home/ubuntu/locomani/VLN_Mobilemanipulator/baselines/ApexNav/run_batch8_inner.sh
# Pass-through APEXNAV_EP0_ONLY / APEXNAV_EPISODES
docker exec -w /workspace/ApexNav \
  -e APEXNAV_EP0_ONLY="${APEXNAV_EP0_ONLY:-0}" \
  -e APEXNAV_EPISODES="${APEXNAV_EPISODES:-}" \
  vln-apexnav bash /workspace/ApexNav/run_batch8_inner.sh
