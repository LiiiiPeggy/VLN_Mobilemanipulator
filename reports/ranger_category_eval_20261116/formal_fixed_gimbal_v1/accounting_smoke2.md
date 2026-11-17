# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 2 / rows 2
- micro SR_proxy: 0.0 (n_scored=2, wilson=[0.0, 0.6576197724933469])
- macro SR_proxy: 0.0
- near_goal true: 0 (reported separately)
- wrong_stop / no_search / stalled / budget: 1 / 1 / 0 / 1
- blocked/truncated exec sum: 111 / 6
- mean moved_m / steps / elapsed_s: 4.295833333333335 / 115.0 / 1010.9611706733704
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 2} / {True: 2} / {'kinematic_collision_v1.1': 2}
- missing fields: {'code_git_sha': 2, 'max_steps_config': 2, 'max_explore_actions_config': 2}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 0/1 | 0.0000 | [0.0, 0.7934506856227626] | 0 | {'explore_budget_exhausted': 1} |
| chair | 0/1 | 0.0000 | [0.0, 0.7934506856227626] | 0 | {'wrong_stop': 1} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
