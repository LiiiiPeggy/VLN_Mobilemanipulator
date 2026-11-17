# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 2 / rows 2
- micro SR_proxy: 0.0 (n_scored=1, wilson=[0.0, 0.7934506856227626])
- macro SR_proxy: 0.0
- near_goal true: 0 (reported separately)
- wrong_stop / no_search / stalled / budget: 0 / 0 / 0 / 0
- blocked/truncated exec sum: 0 / 0
- mean moved_m / steps / elapsed_s: 4.9999999999999964 / 46.5 / 662.093842625618
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 2} / {True: 2} / {'kinematic_collision_v1.1': 2}
- missing fields: {'code_git_sha': 2, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 0/0 | nan | [nan, nan] | 0 | {'empty_run': 1} |
| chair | 0/1 | 0.0000 | [0.0, 0.7934506856227626] | 0 | {'no_stop': 1} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
