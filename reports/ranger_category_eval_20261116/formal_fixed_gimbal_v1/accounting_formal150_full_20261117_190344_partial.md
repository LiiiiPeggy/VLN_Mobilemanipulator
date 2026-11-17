# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 57 / rows 57
- micro SR_proxy: 0.25 (n_scored=56, wilson=[0.15517054688270684, 0.376926421476675])
- macro SR_proxy: 0.25833333333333336
- near_goal true: 17 (reported separately)
- wrong_stop / no_search / stalled / budget: 22 / 37 / 0 / 19
- blocked/truncated exec sum: 2009 / 92
- mean moved_m / steps / elapsed_s: 3.656696428571429 / 87.03508771929825 / 514.869051983482
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 57} / {True: 57} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 55}
- missing fields: {'code_git_sha': 57, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 4/9 | 0.4444 | [0.18877852109766458, 0.7333487065045069] | 4 | {'empty_run': 1, 'wrong_stop': 4, 'ok_success_proxy': 4, 'explore_budget_exhausted': 1} |
| chair | 5/9 | 0.5556 | [0.2666512934954931, 0.8112214789023354] | 7 | {'no_stop': 1, 'ok_success_proxy': 5, 'explore_budget_exhausted': 3} |
| plant | 1/10 | 0.1000 | [0.017876213095072868, 0.4041500267952385] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 5, 'ok_success_proxy': 1} |
| sofa | 2/10 | 0.2000 | [0.05668215145437519, 0.5098375284633583] | 2 | {'wrong_stop': 7, 'explore_budget_exhausted': 1, 'ok_success_proxy': 2} |
| toilet | 0/10 | 0.0000 | [0.0, 0.2775327998628892] | 0 | {'explore_budget_exhausted': 7, 'wrong_stop': 3} |
| tv_monitor | 2/8 | 0.2500 | [0.071479212752109, 0.5907245696898311] | 3 | {'wrong_stop': 4, 'ok_success_proxy': 2, 'explore_budget_exhausted': 2} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
