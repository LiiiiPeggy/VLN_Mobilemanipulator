#!/usr/bin/env bash
# ################################
# Short hy1 smoke with default EXEC_BACKEND=ppo_chassis + demo on.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
source adapters/habitat_rangercr10/scripts/run_integrate_defaults.env
# ################################
# .catkin_devel_integrate may be absent; ApexNav devel is enough for soft_reach=false.
# ################################
if [[ ! -f "${CATKIN_DEVEL_PREFIX}/setup.bash" ]]; then
  export CATKIN_DEVEL_PREFIX=/workspace/ApexNav/devel
fi

BATCH_ID="ppo_chassis_hy1_$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="$ROOT/reports/integration_20261122/ppo_chassis"
mkdir -p "$REPORT_DIR"
echo "$BATCH_ID" >"$REPORT_DIR/latest_batch_id.txt"
echo "$$ ppo_chassis_hy1 $(date -Iseconds)" >/home/ubuntu/locomani/_sim_host_run.lock

export RUN_ID="${BATCH_ID}_hy1_plant_0"
export OUT_DIR="${OUT_DIR:-/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate}"
export SCENE_FILTER=HY1NcmCgn3n
export CATEGORY_FILTER=plant
export EPISODE_ID=0
export FORCE_SPAWN_JSON=/workspace/VLN_Mobilemanipulator/reports/ranger_target_discovery_followup/wrong_stop_audit/paired_b/frozen_spawns/hy1_plant_0_start_pose.json
export MAX_STEPS=50
export MAX_EXPLORE_ACTIONS=20
export SKIP_DEMO=0
export GPU="${GPU:-0}"
export SOFT_REACH_ON_ANY_STUCK=false

LOG="$REPORT_DIR/${BATCH_ID}_host.log"
{
  echo "RUN_ID=$RUN_ID LOOK=$LOOK_BACKEND EXEC=$EXEC_BACKEND CHASSIS=$PPO_CHASSIS_DIR"
  bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
  echo DONE_RC=$?
} 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
rm -f /home/ubuntu/locomani/_sim_host_run.lock || true
exit "$rc"
