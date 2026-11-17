# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 13 / rows 13
- micro SR_proxy: 0.25 (n_scored=12, wilson=[0.08894166839405476, 0.5323053349335656])
- macro SR_proxy: 0.25
- near_goal true: 3 (reported separately)
- wrong_stop / no_search / stalled / budget: 4 / 6 / 0 / 4
- blocked/truncated exec sum: 249 / 28
- mean moved_m / steps / elapsed_s: 4.192361111111111 / 75.46153846153847 / 502.65700241235584
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 13} / {True: 13} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 11}
- missing fields: {'code_git_sha': 13, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 1/2 | 0.5000 | [0.09453120573423074, 0.9054687942657693] | 1 | {'empty_run': 1, 'wrong_stop': 1, 'ok_success_proxy': 1} |
| chair | 1/2 | 0.5000 | [0.09453120573423074, 0.9054687942657693] | 1 | {'no_stop': 1, 'ok_success_proxy': 1} |
| plant | 0/2 | 0.0000 | [0.0, 0.6576197724933469] | 0 | {'wrong_stop': 1, 'explore_budget_exhausted': 1} |
| sofa | 0/2 | 0.0000 | [0.0, 0.6576197724933469] | 0 | {'wrong_stop': 1, 'explore_budget_exhausted': 1} |
| toilet | 0/2 | 0.0000 | [0.0, 0.6576197724933469] | 0 | {'explore_budget_exhausted': 2} |
| tv_monitor | 1/2 | 0.5000 | [0.09453120573423074, 0.9054687942657693] | 1 | {'wrong_stop': 1, 'ok_success_proxy': 1} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
