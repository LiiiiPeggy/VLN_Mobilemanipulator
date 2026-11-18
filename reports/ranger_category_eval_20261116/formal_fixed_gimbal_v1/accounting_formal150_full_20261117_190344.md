# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 109 / rows 109
- micro SR_proxy: 0.3055555555555556 (n_scored=108, wilson=[0.22660233791018655, 0.39786607976903])
- macro SR_proxy: 0.3204453441295546
- near_goal true: 40 (reported separately)
- wrong_stop / no_search / stalled / budget: 34 / 68 / 0 / 40
- blocked/truncated exec sum: 3597 / 156
- mean moved_m / steps / elapsed_s: 4.386496913580248 / 91.5045871559633 / 527.3439017698305
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 109} / {True: 109} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 107}
- missing fields: {'code_git_sha': 109, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 9/18 | 0.5000 | [0.29031021505169974, 0.7096897849483003] | 10 | {'empty_run': 1, 'wrong_stop': 5, 'ok_success_proxy': 9, 'explore_budget_exhausted': 4} |
| chair | 7/13 | 0.5385 | [0.29143795714506004, 0.7679393219046169] | 10 | {'no_stop': 1, 'ok_success_proxy': 7, 'explore_budget_exhausted': 4, 'wrong_stop': 1} |
| plant | 2/19 | 0.1053 | [0.02935856029887013, 0.31394082711109006] | 3 | {'wrong_stop': 5, 'explore_budget_exhausted': 12, 'ok_success_proxy': 2} |
| sofa | 7/19 | 0.3684 | [0.19149512745135072, 0.5896046683519693] | 7 | {'wrong_stop': 9, 'explore_budget_exhausted': 3, 'ok_success_proxy': 7} |
| toilet | 4/19 | 0.2105 | [0.0850767663291625, 0.43334278443814167] | 5 | {'explore_budget_exhausted': 11, 'wrong_stop': 4, 'ok_success_proxy': 4} |
| tv_monitor | 4/20 | 0.2000 | [0.08065766257979809, 0.4160174322518936] | 5 | {'wrong_stop': 10, 'ok_success_proxy': 4, 'explore_budget_exhausted': 6} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
