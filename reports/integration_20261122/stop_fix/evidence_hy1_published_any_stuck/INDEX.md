# Evidence index: hy1 published any_stuck STOP (false positive)

## Source run
- Path: `/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/stop_fix_20261123_002141/stop_fix_20261123_002141_hy1_soft_reach_on`
- Config: legacy018 + v2 + ObjectHold=8.0 + soft_reach_on_any_stuck=true (XY-only)
- Frames: original `demo/` (RGB) and `third/` (external); annotated copies are offline overlays

## Step window 92–96
| step | plan/exec | blocked | yaw_delta | role |
|------|-----------|---------|-----------|------|
| 92 | MOVE_FORWARD OK | 0 | 0 | approach |
| 93 | TURN_LEFT OK | 0 | +30° | successful turn |
| 94 | MOVE_FORWARD TRUNC | 1 | 0 | d455 partial |
| 95 | TURN_RIGHT OK | 0 | −30° | **successful turn** |
| 96 | STOP soft_reach | 0 | 0 | fired because XY idle after turn |

## Files
- `summary_lite.json` — lite metrics
- `slices/steps_090_096.jsonl` — raw steps
- `slices/exploration_soft_reach_context.log` — Hold + Reach log
- `raw/*` — clean originals
- `annotated/*` — labeled overlays
