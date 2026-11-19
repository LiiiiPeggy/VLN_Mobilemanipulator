#!/usr/bin/env bash
# ################################
# Offline/static checks: B configs never wipe ApexNav source mounts.
# ################################
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
fail=0

echo "== compose must NOT bind-mount ApexNav onto /workspace/ApexNav =="
# Ignore comments; fail only on volume bind lines targeting /workspace/ApexNav
if rg -n '^[^#]*:/workspace/ApexNav' "$ROOT/adapters/habitat_rangercr10/docker-compose.agentB_nofrontier.yml" | rg -q .; then
  echo "FAIL: compose bind-mounts onto /workspace/ApexNav"
  fail=1
else
  echo "OK: no ApexNav bind in agentB compose"
fi

echo "== agentB episode script must call safe symlink helper =="
if ! rg -q 'ensure_apex_symlink_safe' "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode_agentB.sh"; then
  echo "FAIL: agentB episode runner missing safe helper"
  fail=1
else
  echo "OK"
fi

echo "== agentB episode script must NOT rm -rf ApexNav =="
if rg -n 'rm -rf.*/workspace/ApexNav|rm -rf '\''\$APEX'\''' "$ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode_agentB.sh"; then
  echo "FAIL: dangerous rm present in agentB runner"
  fail=1
else
  echo "OK"
fi

echo "== safe helper refuses non-symlink wipe =="
if ! rg -q 'REFUSE' "$ROOT/adapters/habitat_rangercr10/scripts/ensure_apex_symlink_safe.sh"; then
  echo "FAIL: safe helper missing REFUSE path"
  fail=1
else
  echo "OK"
fi

echo "== paired runner gated on A release =="
if ! rg -q 'A_RELEASED_LOCK' "$ROOT/adapters/habitat_rangercr10/scripts/run_nofrontier_look_paired_agentB.sh"; then
  echo "FAIL: missing A release gate"
  fail=1
else
  echo "OK"
fi

echo "== dry gate (expect exit 75 without release flag) =="
set +e
A_RELEASED_LOCK=0 SKIP_BUILD=1 PHASE=phase0_switch_verify \
  bash "$ROOT/adapters/habitat_rangercr10/scripts/run_nofrontier_look_paired_agentB.sh" >/tmp/agentB_gate_test.log 2>&1
rc=$?
set -e
if [[ "$rc" != "75" ]]; then
  echo "FAIL: expected exit 75, got $rc (see /tmp/agentB_gate_test.log)"
  fail=1
else
  echo "OK: gated exit 75"
fi

# ensure we did not create B container during dry gate
if docker ps -a --format '{{.Names}}' | grep -qx 'vln-rangercr10-agentB-nofrontier'; then
  echo "WARN: agentB container exists (may be from earlier); gate should not have started episodes"
else
  echo "OK: agentB container not created by dry gate"
fi

exit "$fail"
