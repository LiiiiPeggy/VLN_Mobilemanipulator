# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 85 / rows 85
- micro SR_proxy: 0.2857142857142857 (n_scored=84, wilson=[0.20015034121612774, 0.39002039953301215])
- macro SR_proxy: 0.28840048840048843
- near_goal true: 30 (reported separately)
- wrong_stop / no_search / stalled / budget: 28 / 54 / 0 / 31
- blocked/truncated exec sum: 2639 / 110
- mean moved_m / steps / elapsed_s: 4.5317460317460325 / 90.70588235294117 / 539.6075946976157
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 85} / {True: 85} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 83}
- missing fields: {'code_git_sha': 85, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 7/14 | 0.5000 | [0.26799202452413634, 0.7320079754758637] | 8 | {'empty_run': 1, 'wrong_stop': 4, 'ok_success_proxy': 7, 'explore_budget_exhausted': 3} |
| chair | 7/13 | 0.5385 | [0.29143795714506004, 0.7679393219046169] | 10 | {'no_stop': 1, 'ok_success_proxy': 7, 'explore_budget_exhausted': 4, 'wrong_stop': 1} |
| plant | 1/14 | 0.0714 | [0.012722215247890939, 0.31468704424151117] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 9, 'ok_success_proxy': 1} |
| sofa | 6/15 | 0.4000 | [0.1982449614134158, 0.6425316987937539] | 6 | {'wrong_stop': 8, 'explore_budget_exhausted': 1, 'ok_success_proxy': 6} |
| toilet | 1/15 | 0.0667 | [0.011866895493268553, 0.2981652987378003] | 2 | {'explore_budget_exhausted': 10, 'wrong_stop': 4, 'ok_success_proxy': 1} |
| tv_monitor | 2/13 | 0.1538 | [0.043258178358081184, 0.4223463101948254] | 3 | {'wrong_stop': 7, 'ok_success_proxy': 2, 'explore_budget_exhausted': 4} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
