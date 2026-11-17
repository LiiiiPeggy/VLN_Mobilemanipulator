# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 62 / rows 62
- micro SR_proxy: 0.2459016393442623 (n_scored=61, wilson=[0.1550665770122629, 0.3668442410998928])
- macro SR_proxy: 0.25067340067340066
- near_goal true: 19 (reported separately)
- wrong_stop / no_search / stalled / budget: 23 / 40 / 0 / 22
- blocked/truncated exec sum: 2009 / 92
- mean moved_m / steps / elapsed_s: 4.000409836065574 / 88.11290322580645 / 525.2334574307165
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 62} / {True: 62} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 60}
- missing fields: {'code_git_sha': 62, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 4/10 | 0.4000 | [0.16818032970623614, 0.6873262302663417] | 5 | {'empty_run': 1, 'wrong_stop': 4, 'ok_success_proxy': 4, 'explore_budget_exhausted': 2} |
| chair | 6/10 | 0.6000 | [0.31267376973365824, 0.8318196702937638] | 8 | {'no_stop': 1, 'ok_success_proxy': 6, 'explore_budget_exhausted': 3} |
| plant | 1/10 | 0.1000 | [0.017876213095072868, 0.4041500267952385] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 5, 'ok_success_proxy': 1} |
| sofa | 2/11 | 0.1818 | [0.05136768974608513, 0.4769805619608442] | 2 | {'wrong_stop': 8, 'explore_budget_exhausted': 1, 'ok_success_proxy': 2} |
| toilet | 0/11 | 0.0000 | [0.0, 0.2588329669680317] | 0 | {'explore_budget_exhausted': 8, 'wrong_stop': 3} |
| tv_monitor | 2/9 | 0.2222 | [0.06322510711784673, 0.5474110308930111] | 3 | {'wrong_stop': 4, 'ok_success_proxy': 2, 'explore_budget_exhausted': 3} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
