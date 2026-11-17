# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 33 / rows 33
- micro SR_proxy: 0.3125 (n_scored=32, wilson=[0.17952541633609737, 0.48566678300955407])
- macro SR_proxy: 0.30476190476190473
- near_goal true: 13 (reported separately)
- wrong_stop / no_search / stalled / budget: 9 / 18 / 0 / 12
- blocked/truncated exec sum: 811 / 45
- mean moved_m / steps / elapsed_s: 4.988802083333334 / 87.81818181818181 / 587.5985840522882
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 33} / {True: 33} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 31}
- missing fields: {'code_git_sha': 33, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 3/5 | 0.6000 | [0.2307242812760128, 0.882379225767352] | 3 | {'empty_run': 1, 'wrong_stop': 2, 'ok_success_proxy': 3} |
| chair | 3/7 | 0.4286 | [0.15821985525146975, 0.7495416354723428] | 5 | {'no_stop': 1, 'ok_success_proxy': 3, 'explore_budget_exhausted': 3} |
| plant | 1/5 | 0.2000 | [0.036224108632430085, 0.6244653702374747] | 1 | {'wrong_stop': 2, 'explore_budget_exhausted': 2, 'ok_success_proxy': 1} |
| sofa | 1/5 | 0.2000 | [0.036224108632430085, 0.6244653702374747] | 1 | {'wrong_stop': 3, 'explore_budget_exhausted': 1, 'ok_success_proxy': 1} |
| toilet | 0/5 | 0.0000 | [0.0, 0.43448246478317476] | 0 | {'explore_budget_exhausted': 4, 'wrong_stop': 1} |
| tv_monitor | 2/5 | 0.4000 | [0.11762077423264783, 0.769275718723987] | 3 | {'wrong_stop': 1, 'ok_success_proxy': 2, 'explore_budget_exhausted': 2} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
