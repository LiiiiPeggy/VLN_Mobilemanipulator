# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 40 / rows 40
- micro SR_proxy: 0.3333333333333333 (n_scored=39, wilson=[0.20632956189598375, 0.4902260560065401])
- macro SR_proxy: 0.33253968253968247
- near_goal true: 16 (reported separately)
- wrong_stop / no_search / stalled / budget: 12 / 21 / 0 / 13
- blocked/truncated exec sum: 1096 / 62
- mean moved_m / steps / elapsed_s: 4.742307692307692 / 87.9 / 564.8625672638416
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 40} / {True: 40} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 38}
- missing fields: {'code_git_sha': 40, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 4/6 | 0.6667 | [0.299993315138392, 0.9032285888942195] | 4 | {'empty_run': 1, 'wrong_stop': 2, 'ok_success_proxy': 4} |
| chair | 4/8 | 0.5000 | [0.21521606221387757, 0.7847839377861224] | 6 | {'no_stop': 1, 'ok_success_proxy': 4, 'explore_budget_exhausted': 3} |
| plant | 1/7 | 0.1429 | [0.02567962434474355, 0.5131278292743189] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 2, 'ok_success_proxy': 1} |
| sofa | 2/7 | 0.2857 | [0.08221892400405678, 0.6410655481673808] | 2 | {'wrong_stop': 4, 'explore_budget_exhausted': 1, 'ok_success_proxy': 2} |
| toilet | 0/6 | 0.0000 | [0.0, 0.39033428790216534] | 0 | {'explore_budget_exhausted': 5, 'wrong_stop': 1} |
| tv_monitor | 2/5 | 0.4000 | [0.11762077423264783, 0.769275718723987] | 3 | {'wrong_stop': 1, 'ok_success_proxy': 2, 'explore_budget_exhausted': 2} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
