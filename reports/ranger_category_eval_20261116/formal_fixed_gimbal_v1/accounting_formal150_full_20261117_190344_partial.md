# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 108 / rows 108
- micro SR_proxy: 0.308411214953271 (n_scored=107, wilson=[0.22881739747870233, 0.4012849086780145])
- macro SR_proxy: 0.3221997300944669
- near_goal true: 40 (reported separately)
- wrong_stop / no_search / stalled / budget: 34 / 67 / 0 / 39
- blocked/truncated exec sum: 3597 / 156
- mean moved_m / steps / elapsed_s: 4.313006230529596 / 91.18518518518519 / 523.6340793437428
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 108} / {True: 108} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 106}
- missing fields: {'code_git_sha': 108, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 9/18 | 0.5000 | [0.29031021505169974, 0.7096897849483003] | 10 | {'empty_run': 1, 'wrong_stop': 5, 'ok_success_proxy': 9, 'explore_budget_exhausted': 4} |
| chair | 7/13 | 0.5385 | [0.29143795714506004, 0.7679393219046169] | 10 | {'no_stop': 1, 'ok_success_proxy': 7, 'explore_budget_exhausted': 4, 'wrong_stop': 1} |
| plant | 2/19 | 0.1053 | [0.02935856029887013, 0.31394082711109006] | 3 | {'wrong_stop': 5, 'explore_budget_exhausted': 12, 'ok_success_proxy': 2} |
| sofa | 7/19 | 0.3684 | [0.19149512745135072, 0.5896046683519693] | 7 | {'wrong_stop': 9, 'explore_budget_exhausted': 3, 'ok_success_proxy': 7} |
| toilet | 4/19 | 0.2105 | [0.0850767663291625, 0.43334278443814167] | 5 | {'explore_budget_exhausted': 11, 'wrong_stop': 4, 'ok_success_proxy': 4} |
| tv_monitor | 4/19 | 0.2105 | [0.0850767663291625, 0.43334278443814167] | 5 | {'wrong_stop': 10, 'ok_success_proxy': 4, 'explore_budget_exhausted': 5} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
