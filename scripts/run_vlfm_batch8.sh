#!/usr/bin/env bash
# Host wrapper: VLFM ObjectNav first 8 val episodes via in-container runner.
set -euo pipefail
chmod +x /home/ubuntu/locomani/VLN_Mobilemanipulator/baselines/VLFM/run_batch8_inner.sh
docker exec -w /workspace/VLFM vln-vlfm bash /workspace/VLFM/run_batch8_inner.sh
