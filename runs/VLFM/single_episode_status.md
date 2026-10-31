# VLFM single episode status

**Result: OK** (pipeline completed; task success=0 due to false_positive)

| Item | Value |
|------|-------|
| Time | 2026-11-01 00:11–00:12 CST |
| Container | `vln-vlfm` (`vln-habitat024:latest` = `fe6b1ca643fd`) |
| Command | `python -m vlfm.run habitat_baselines.test_episode_count=1` |
| Log | `/media/ubuntu/D/VLN_shared/runs/VLFM/single_episode_20261101_001121.log` (also prior OK run `..._20261031_234730.log`) |
| Scene / ep | `5cdEh9F2hJL` episode 45 |
| Failure reason | `false_positive` (agent stopped; not a crash) |
| Duration | ~29 s after init |

## Key metrics

- success: **0.0000**
- spl: **0.0000**
- soft_spl: **0.0000**
- distance_to_goal: **12.8316**
- reward: **-2.4169**
- target_detected: **1.0000**
- stop_called: **1.0000**
- yaw: **150.0000**

## VLM servers

Ports **12181–12184** accepting connections inside `vln-vlfm` (grounding_dino / blip2itm / sam / yolov7). Logs: `/workspace/runs/vlm_servers/*.log`.

## Notes

- Dummy policy: `data/dummy_policy.pth` present.
- Runtime image committed after deps + `dash<3` (open3d/pydantic import fix).
- No algorithm code changes; config/weights paths OK.
