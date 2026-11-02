#!/usr/bin/env bash
# Host wrapper: MSGNav 8 scenes × 1 episode via in-container runner.
set -euo pipefail
chmod +x /home/ubuntu/locomani/VLN_Mobilemanipulator/baselines/MSGNav/run_batch8_inner.sh
docker exec -w /workspace/MSGNav vln-msgnav bash /workspace/MSGNav/run_batch8_inner.sh
