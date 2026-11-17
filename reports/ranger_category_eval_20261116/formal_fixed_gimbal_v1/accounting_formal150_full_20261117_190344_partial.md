# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 47 / rows 47
- micro SR_proxy: 0.30434782608695654 (n_scored=46, wilson=[0.1907984080276724, 0.4480564644840765])
- macro SR_proxy: 0.3058862433862434
- near_goal true: 17 (reported separately)
- wrong_stop / no_search / stalled / budget: 16 / 27 / 0 / 15
- blocked/truncated exec sum: 1506 / 84
- mean moved_m / steps / elapsed_s: 4.193659420289856 / 87.34042553191489 / 549.0153891735888
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 47} / {True: 47} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 45}
- missing fields: {'code_git_sha': 47, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 4/7 | 0.5714 | [0.2504583645276572, 0.8417801447485302] | 4 | {'empty_run': 1, 'wrong_stop': 3, 'ok_success_proxy': 4} |
| chair | 5/9 | 0.5556 | [0.2666512934954931, 0.8112214789023354] | 7 | {'no_stop': 1, 'ok_success_proxy': 5, 'explore_budget_exhausted': 3} |
| plant | 1/8 | 0.1250 | [0.02241749145005667, 0.4708881822128535] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 3, 'ok_success_proxy': 1} |
| sofa | 2/8 | 0.2500 | [0.071479212752109, 0.5907245696898311] | 2 | {'wrong_stop': 5, 'explore_budget_exhausted': 1, 'ok_success_proxy': 2} |
| toilet | 0/8 | 0.0000 | [0.0, 0.32440756488388023] | 0 | {'explore_budget_exhausted': 6, 'wrong_stop': 2} |
| tv_monitor | 2/6 | 0.3333 | [0.09677141110578041, 0.700006684861608] | 3 | {'wrong_stop': 2, 'ok_success_proxy': 2, 'explore_budget_exhausted': 2} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
