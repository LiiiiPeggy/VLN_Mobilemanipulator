# Startup prior ObjectNav e2e aggregate (smoke_exp03_20261107_164251)

Task: **ObjectNav** (HM3D-v2 val) via `apexnav_real_episode` / ApexNav planner.
Success proxy: `termination==planner_stop` AND `near_goal` (dtg ≤ 1.0 m).
Official challenge SPL not available in this adapter path (no geodesic).

| mode | n | SR_proxy | entered_explore | start_blocked | mid_nopass/stuck | explore_no_goal | mean_fwd_m | mean_n_explore |
|------|---|----------|-----------------|---------------|------------------|-----------------|------------|----------------|
| initial_footprint | 3 | 0.667 (2/3) | 1.000 | 0.000 | 0.000 | 0.333 | 10.42 | 85.7 |

## Fail class histogram
- **initial_footprint**: `{'ok_success_proxy': 2, 'explore_no_goal': 1}`

