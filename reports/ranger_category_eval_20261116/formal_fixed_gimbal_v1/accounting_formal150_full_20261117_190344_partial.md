# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 15 / rows 15
- micro SR_proxy: 0.2857142857142857 (n_scored=14, wilson=[0.11721378644576919, 0.5464908432989318])
- macro SR_proxy: 0.3055555555555555
- near_goal true: 4 (reported separately)
- wrong_stop / no_search / stalled / budget: 4 / 7 / 0 / 5
- blocked/truncated exec sum: 249 / 28
- mean moved_m / steps / elapsed_s: 4.986309523809524 / 81.2 / 559.3251399199168
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 15} / {True: 15} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 13}
- missing fields: {'code_git_sha': 15, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 1/2 | 0.5000 | [0.09453120573423074, 0.9054687942657693] | 1 | {'empty_run': 1, 'wrong_stop': 1, 'ok_success_proxy': 1} |
| chair | 1/2 | 0.5000 | [0.09453120573423074, 0.9054687942657693] | 1 | {'no_stop': 1, 'ok_success_proxy': 1} |
| plant | 1/3 | 0.3333 | [0.06149194472039615, 0.7923403991979523] | 1 | {'wrong_stop': 1, 'explore_budget_exhausted': 1, 'ok_success_proxy': 1} |
| sofa | 0/2 | 0.0000 | [0.0, 0.6576197724933469] | 0 | {'wrong_stop': 1, 'explore_budget_exhausted': 1} |
| toilet | 0/3 | 0.0000 | [0.0, 0.5614970317550455] | 0 | {'explore_budget_exhausted': 3} |
| tv_monitor | 1/2 | 0.5000 | [0.09453120573423074, 0.9054687942657693] | 1 | {'wrong_stop': 1, 'ok_success_proxy': 1} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
