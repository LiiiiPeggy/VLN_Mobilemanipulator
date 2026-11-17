# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 27 / rows 27
- micro SR_proxy: 0.3076923076923077 (n_scored=26, wilson=[0.16501315595463767, 0.4998825832219837])
- macro SR_proxy: 0.3361111111111111
- near_goal true: 10 (reported separately)
- wrong_stop / no_search / stalled / budget: 7 / 15 / 0 / 10
- blocked/truncated exec sum: 616 / 39
- mean moved_m / steps / elapsed_s: 4.86025641025641 / 86.5925925925926 / 600.2146140027929
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 27} / {True: 27} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 25}
- missing fields: {'code_git_sha': 27, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 2/3 | 0.6667 | [0.20765960080204765, 0.9385080552796037] | 2 | {'empty_run': 1, 'wrong_stop': 1, 'ok_success_proxy': 2} |
| chair | 2/5 | 0.4000 | [0.11762077423264783, 0.769275718723987] | 3 | {'no_stop': 1, 'ok_success_proxy': 2, 'explore_budget_exhausted': 2} |
| plant | 1/5 | 0.2000 | [0.036224108632430085, 0.6244653702374747] | 1 | {'wrong_stop': 2, 'explore_budget_exhausted': 2, 'ok_success_proxy': 1} |
| sofa | 1/4 | 0.2500 | [0.04558726080970055, 0.6993581574175981] | 1 | {'wrong_stop': 2, 'explore_budget_exhausted': 1, 'ok_success_proxy': 1} |
| toilet | 0/5 | 0.0000 | [0.0, 0.43448246478317476] | 0 | {'explore_budget_exhausted': 4, 'wrong_stop': 1} |
| tv_monitor | 2/4 | 0.5000 | [0.15003898915214953, 0.8499610108478505] | 3 | {'wrong_stop': 1, 'ok_success_proxy': 2, 'explore_budget_exhausted': 1} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
