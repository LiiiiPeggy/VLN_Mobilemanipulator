# Narrow corridor pair results (Agent A)

**主机锁已释放** — `/home/ubuntu/locomani/_sim_host_run.lock`

## Batch `navinf_narrow_A_20261122_130624`

| tag | actual | n_steps | term | blocked/trunc | infl/step | soft | usable |
|-----|--------|---------|------|---------------|-----------|------|--------|
| toilet_legacy018 | 0.18 / 4 | 0 | exception | 0/0 | 0.18/4 | off | False |
| toilet_legacy018_retry | 0.18 / 4 | 0 | exception | 0/0 | 0.18/4 | off | False |
| toilet_inf020 | 0.2 / 4 | 66 | planner_stop | 54/0 | 0.2/4 | R=0.1/w=2.0 | True |
| dd4b_legacy018 | 0.18 / 4 | 126 | explore_budget_exhausted | 42/7 | 0.18/4 | off | True |
| dd4b_inf020 | 0.2 / 4 | 126 | explore_budget_exhausted | 49/13 | 0.2/4 | R=0.1/w=2.0 | True |

## Dd4b toilet_0 配对（双方有效，inf_step 均为 4）

| | legacy018 | inf020_soft010 |
|--|--|--|
| termination | explore_budget_exhausted | explore_budget_exhausted |
| n_steps | 126 | 126 |
| blocked / truncated | 42 / 7 | 49 / 13 |
| plan edge_min | -0.10864938560718013 | -0.04453530803082678 |
| exec edge_min | 0.3367870884054629 | 0.33709530483793637 |
| exec edge_p10 | 0.34714557557807 | 0.35078379923553904 |
| plan−exec note | diverge={'i': 0, 'xy': [1.2264126539230347, -0.35986998677253723], 'yaw': -1.8978694770178564, 'dist': 0.7144197441615906} | diverge={'i': 0, 'xy': [1.2264126539230347, -0.35986998677253723], 'yaw': -1.8978694770178564, 'dist': 0.7144197441615906} |

## TEEsav toilet_2
- legacy：握手超时 ×2（tsp_solver process has died）；诊断见 `narrow_abort_diag/`
- inf020：可用 n=66 term=planner_stop blocked=54 plan_edge_min=0.09923983780632634 exec_edge_min=0.5442314606391304

## 与 B 交接对齐
- B `HANDOFF_TO_A_clearance.md`：seq42 start_inflate→n_reach=0；seq57 path_ok 但执行 3D 碰撞（d455/gripper）转不动。
- A 窄通道：dd4b 上可直接比 plan/exec edge；toilet 缺 legacy 对照。

- dd4b 图：`/home/ubuntu/locomani/VLN_Mobilemanipulator_agentA_navinf/reports/nav_inf020_soft010_online_20261119/narrow_pair/dd4b_pair_topdown.png`
- toilet inf 图：`/home/ubuntu/locomani/VLN_Mobilemanipulator_agentA_navinf/reports/nav_inf020_soft010_online_20261119/narrow_pair/toilet_inf020_only_topdown.png`
