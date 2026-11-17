# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 22 / rows 22
- micro SR_proxy: 0.2857142857142857 (n_scored=21, wilson=[0.1381386295212213, 0.49956380716085597])
- macro SR_proxy: 0.29166666666666663
- near_goal true: 7 (reported separately)
- wrong_stop / no_search / stalled / budget: 5 / 11 / 0 / 9
- blocked/truncated exec sum: 445 / 32
- mean moved_m / steps / elapsed_s: 5.193253968253968 / 87.18181818181819 / 581.6538483337922
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 22} / {True: 22} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 20}
- missing fields: {'code_git_sha': 22, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 2/3 | 0.6667 | [0.20765960080204765, 0.9385080552796037] | 2 | {'empty_run': 1, 'wrong_stop': 1, 'ok_success_proxy': 2} |
| chair | 2/4 | 0.5000 | [0.15003898915214953, 0.8499610108478505] | 2 | {'no_stop': 1, 'ok_success_proxy': 2, 'explore_budget_exhausted': 1} |
| plant | 1/4 | 0.2500 | [0.04558726080970055, 0.6993581574175981] | 1 | {'wrong_stop': 1, 'explore_budget_exhausted': 2, 'ok_success_proxy': 1} |
| sofa | 0/3 | 0.0000 | [0.0, 0.5614970317550455] | 0 | {'wrong_stop': 2, 'explore_budget_exhausted': 1} |
| toilet | 0/4 | 0.0000 | [0.0, 0.4898908364545973] | 0 | {'explore_budget_exhausted': 4} |
| tv_monitor | 1/3 | 0.3333 | [0.06149194472039615, 0.7923403991979523] | 2 | {'wrong_stop': 1, 'ok_success_proxy': 1, 'explore_budget_exhausted': 1} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
