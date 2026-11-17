# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 72 / rows 72
- micro SR_proxy: 0.2676056338028169 (n_scored=71, wilson=[0.17852803486507762, 0.3805398865785474])
- macro SR_proxy: 0.27224164724164723
- near_goal true: 24 (reported separately)
- wrong_stop / no_search / stalled / budget: 25 / 47 / 0 / 26
- blocked/truncated exec sum: 2356 / 101
- mean moved_m / steps / elapsed_s: 4.155868544600939 / 89.33333333333333 / 522.1771507561207
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 72} / {True: 72} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 70}
- missing fields: {'code_git_sha': 72, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 5/12 | 0.4167 | [0.19326031365875668, 0.6804886874504503] | 6 | {'empty_run': 1, 'wrong_stop': 4, 'ok_success_proxy': 5, 'explore_budget_exhausted': 3} |
| chair | 7/11 | 0.6364 | [0.35380117450784887, 0.8483352890463243] | 9 | {'no_stop': 1, 'ok_success_proxy': 7, 'explore_budget_exhausted': 3} |
| plant | 1/11 | 0.0909 | [0.016232172885884855, 0.37735843645159567] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 6, 'ok_success_proxy': 1} |
| sofa | 4/13 | 0.3077 | [0.12680703655710515, 0.5763065681945096] | 4 | {'wrong_stop': 8, 'explore_budget_exhausted': 1, 'ok_success_proxy': 4} |
| toilet | 0/13 | 0.0000 | [0.0, 0.22809537235419838] | 1 | {'explore_budget_exhausted': 9, 'wrong_stop': 4} |
| tv_monitor | 2/11 | 0.1818 | [0.05136768974608513, 0.4769805619608442] | 3 | {'wrong_stop': 5, 'ok_success_proxy': 2, 'explore_budget_exhausted': 4} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
