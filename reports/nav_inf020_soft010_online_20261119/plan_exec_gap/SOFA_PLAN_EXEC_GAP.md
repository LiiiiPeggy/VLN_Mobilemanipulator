# Sofa plan vs exec clearance gap (offline)

Waiting for host lock (held by B). Offline only.

| | legacy018 | inf020_soft010 |
|--|--|--|
| plan_edge_min | 0.004705954666076317 | 0.0988228874149274 |
| plan_edge_p10 | 0.05570637609038943 | 0.16525632761652204 |
| overlap8_exec_edge_p10 | 0.15668219033725145 | 0.09882281383603564 |
| overlap8_exec_edge_mean | 0.2614643368066042 | 0.2586711068925271 |
| plan_minus_exec_edge_p10 | -0.10097581424686203 | 0.0664335137804864 |
| exec_edge_min_full | 0.09336053880496603 | 0.059398769020155895 |

## First plan↔exec diverge (>0.35 m to selected path)
- legacy: None
- inf020: {'step_i': 0, 'xy': [2.3178300857543945, 1.7573800086975098], 'yaw': -0.22569824713098008, 'dist_to_plan': 0.4745773281267052, 'edge_clear': 0.5488803452457605}

## Reading
- inf020 **plan** edge_min rises (~0→0.1 m) while **exec** overlap edge_p10 does not; gap `plan_minus_exec_edge_p10` quantifies tracking/commit lag.
- First diverge step_i points to whether gap starts near turn (large yaw_jump) or straight tracking.
