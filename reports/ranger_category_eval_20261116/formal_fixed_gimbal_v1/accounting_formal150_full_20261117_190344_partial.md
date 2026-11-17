# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 75 / rows 75
- micro SR_proxy: 0.28378378378378377 (n_scored=74, wilson=[0.19373547108022535, 0.3951725416317253])
- macro SR_proxy: 0.29036241536241536
- near_goal true: 26 (reported separately)
- wrong_stop / no_search / stalled / budget: 25 / 48 / 0 / 27
- blocked/truncated exec sum: 2356 / 101
- mean moved_m / steps / elapsed_s: 4.3083333333333345 / 89.42666666666666 / 529.9617580191294
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 75} / {True: 75} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 73}
- missing fields: {'code_git_sha': 75, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 6/13 | 0.4615 | [0.232060678095383, 0.7085620428549398] | 7 | {'empty_run': 1, 'wrong_stop': 4, 'ok_success_proxy': 6, 'explore_budget_exhausted': 3} |
| chair | 7/11 | 0.6364 | [0.35380117450784887, 0.8483352890463243] | 9 | {'no_stop': 1, 'ok_success_proxy': 7, 'explore_budget_exhausted': 3} |
| plant | 1/12 | 0.0833 | [0.014865094404917095, 0.35387991114111694] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 7, 'ok_success_proxy': 1} |
| sofa | 4/13 | 0.3077 | [0.12680703655710515, 0.5763065681945096] | 4 | {'wrong_stop': 8, 'explore_budget_exhausted': 1, 'ok_success_proxy': 4} |
| toilet | 1/14 | 0.0714 | [0.012722215247890939, 0.31468704424151117] | 2 | {'explore_budget_exhausted': 9, 'wrong_stop': 4, 'ok_success_proxy': 1} |
| tv_monitor | 2/11 | 0.1818 | [0.05136768974608513, 0.4769805619608442] | 3 | {'wrong_stop': 5, 'ok_success_proxy': 2, 'explore_budget_exhausted': 4} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
