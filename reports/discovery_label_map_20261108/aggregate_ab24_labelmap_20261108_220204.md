# Startup prior ObjectNav e2e aggregate (ab24_labelmap_20261108_220204)

Task: **ObjectNav** (HM3D-v2 val) via `apexnav_real_episode` / ApexNav planner.
Success proxy: `termination==planner_stop` AND `near_goal` (dtg ≤ 1.0 m).
Official challenge SPL not available in this adapter path (no geodesic).

| mode | n | SR_proxy | entered_explore | start_blocked | mid_nopass/stuck | explore_no_goal | mean_fwd_m | mean_n_explore |
|------|---|----------|-----------------|---------------|------------------|-----------------|------------|----------------|
| initial_footprint | 24 | 0.208 (5/24) | 1.000 | 0.000 | 0.000 | 0.458 | 9.20 | 76.5 |

## Fail class histogram
- **initial_footprint**: `{'stop_not_near_goal': 8, 'ok_success_proxy': 5, 'explore_no_goal': 11}`

