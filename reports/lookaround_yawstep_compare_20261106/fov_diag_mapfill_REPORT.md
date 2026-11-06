# Lookaround FOV diag — `real_s070_pporaise_yr17_mapfill_20261105_212419`

- HFOV/VFOV: **79.00° / ≈63.45°**（方像素）；旧报告 59.25° 为错误 fy 推论，已降级
- Mean TURN yaw step: **29.999998102822403°**
- Overlap @ mean step: `{'hfov_deg': 79.0, 'yaw_step_deg': 29.999998102822403, 'overlap_deg': 49.0000018971776, 'overlap_frac_of_hfov': 0.6202531885718683, 'gap_if_negative_deg': 0.0}`
- Overlap table: `{"15": {"hfov_deg": 79.0, "yaw_step_deg": 15.0, "overlap_deg": 64.0, "overlap_frac_of_hfov": 0.810126582278481, "gap_if_negative_deg": 0.0}, "20": {"hfov_deg": 79.0, "yaw_step_deg": 20.0, "overlap_deg": 59.0, "overlap_frac_of_hfov": 0.7468354430379747, "gap_if_negative_deg": 0.0}, "30": {"hfov_deg": 79.0, "yaw_step_deg": 30.0, "overlap_deg": 49.0, "overlap_frac_of_hfov": 0.620253164556962, "gap_if_negative_deg": 0.0}, "45": {"hfov_deg": 79.0, "yaw_step_deg": 45.0, "overlap_deg": 34.0, "overlap_frac_of_hfov": 0.43037974683544306, "gap_if_negative_deg": 0.0}}`

## Findings
- D455/Habitat FOV from ApexNav fx/fy: H=79.00° V=59.25° (matches EE_RGB_HFOV_DEG=79).
- Measured lookaround turn step ≈30.0° → horizontal overlap 49.0° (62% of HFOV).
- Yaw step alone does NOT create horizontal FOV blind wedges; white radial gaps are mostly unknown between sparse free-ray sectors and height-filtered occupied endpoints — not missing FOV coverage.
- Camera pitch during lookaround: min=-1.6° max=31.2° (TURN_DOWN/UP change optical pitch via arm FK).

## Passability (first plan)
```json
{
  "base_cell_state": "free",
  "free_component_from_start": 440,
  "frontier_seed_cells": 468,
  "frontier_clusters": 16,
  "astar_trials_n": 16,
  "astar_ok_n": 4,
  "occupied_pts": 584,
  "free_pts": 1067,
  "unknown_pts": 21478,
  "inflate_pts": 1649,
  "hypothesis": "If base_cell_state!=free or free_component small and astar_ok_n==0, NO_PASSABLE is map connectivity / start occupancy \u2014 not missing frontiers."
}
```
