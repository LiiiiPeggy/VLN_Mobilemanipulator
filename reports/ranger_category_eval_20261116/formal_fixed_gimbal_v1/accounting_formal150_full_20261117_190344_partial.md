# Formal independent eval — accounting

- list original: 120
- validity: {'valid': 109, 'invalid': 11}
- ingested unique: 80 / rows 80
- micro SR_proxy: 0.2911392405063291 (n_scored=79, wilson=[0.20251993313819472, 0.39912880084382363])
- macro SR_proxy: 0.2925824175824176
- near_goal true: 29 (reported separately)
- wrong_stop / no_search / stalled / budget: 26 / 50 / 0 / 29
- blocked/truncated exec sum: 2417 / 101
- mean moved_m / steps / elapsed_s: 4.538818565400844 / 90.25 / 537.7522684395313
- camera_mode / simulated_gimbal / executor: {'fixed_base_gimbal': 80} / {True: 80} / {'kinematic_collision_v1.1': 2, 'kinematic_collision_v1.2': 78}
- missing fields: {'code_git_sha': 80, 'sum_moved_m': 1, 'entered_search_best': 1, 'has_stop_action': 1, 'dtg_min': 1}
- SPL: N/A; height/occlusion/ambiguity: unknown

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal | fail buckets |
|---|---:|---:|---|---:|---|
| bed | 7/14 | 0.5000 | [0.26799202452413634, 0.7320079754758637] | 8 | {'empty_run': 1, 'wrong_stop': 4, 'ok_success_proxy': 7, 'explore_budget_exhausted': 3} |
| chair | 7/12 | 0.5833 | [0.31951131254954973, 0.8067396863412435] | 10 | {'no_stop': 1, 'ok_success_proxy': 7, 'explore_budget_exhausted': 4} |
| plant | 1/13 | 0.0769 | [0.013710421242556559, 0.3331395092109959] | 1 | {'wrong_stop': 4, 'explore_budget_exhausted': 8, 'ok_success_proxy': 1} |
| sofa | 5/14 | 0.3571 | [0.1634473175355414, 0.612355768960926] | 5 | {'wrong_stop': 8, 'explore_budget_exhausted': 1, 'ok_success_proxy': 5} |
| toilet | 1/14 | 0.0714 | [0.012722215247890939, 0.31468704424151117] | 2 | {'explore_budget_exhausted': 9, 'wrong_stop': 4, 'ok_success_proxy': 1} |
| tv_monitor | 2/12 | 0.1667 | [0.04696514218385378, 0.4480308622529734] | 3 | {'wrong_stop': 6, 'ok_success_proxy': 2, 'explore_budget_exhausted': 4} |

## Notes
- SR_proxy ≠ near_goal; moved_m=0 near_goal is NOT successful approach.
- Invalid spawn counted from validity table, not from SR filter.
- SPL=N/A without footprint-matched geodesic.
- Observation height / occlusion / instance ambiguity = unknown without evidence.
- Cup / active-arm strategy not in this freeze.
