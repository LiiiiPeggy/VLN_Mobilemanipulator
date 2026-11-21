#!/usr/bin/env bash
# ################################
# Shared A/B host simulation lock (same path as Agent A handoff).
# Covers build/start/run/cleanup. Flag A_RELEASED_LOCK is handover-only.
# ################################
set -euo pipefail
LOCK=${SIM_HOST_LOCK:-/home/ubuntu/locomani/_sim_host_run.lock}
OWNER=${LOCK_OWNER:-agentB_nofrontier}
cmd=${1:-status}
case "$cmd" in
  acquire)
    if [[ -f "$LOCK" ]]; then
      echo "LOCK_HELD $(cat "$LOCK")"
      exit 1
    fi
    printf 'owner=%s pid=%s time=%s\n' "$OWNER" "$$" "$(date -Iseconds)" > "$LOCK"
    echo "LOCK_ACQUIRED $LOCK"
    ;;
  release)
    if [[ -f "$LOCK" ]]; then
      if grep -q "owner=$OWNER" "$LOCK" || [[ "${FORCE:-0}" == "1" ]]; then
        rm -f "$LOCK"
        echo "LOCK_RELEASED"
      else
        echo "LOCK_NOT_OWNED $(cat "$LOCK")"; exit 1
      fi
    else
      echo "LOCK_ALREADY_FREE"
    fi
    ;;
  status)
    if [[ -f "$LOCK" ]]; then echo "LOCK_HELD $(cat "$LOCK")"; else echo "LOCK_FREE"; fi
    ;;
  *) echo "usage: $0 acquire|release|status"; exit 2;;
esac
