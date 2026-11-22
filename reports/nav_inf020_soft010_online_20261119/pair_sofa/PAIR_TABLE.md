# Sofa pair: legacy018 vs inf020_soft010

Pair match (spawn/yaw/budget/camera/executor/scale): **True**

| arm | infl_m | inf_step | soft | lock | n_steps | blocked | trunc | term | exec_edge_min | exec_edge_p10 (mid) | plan_edge_min |
|-----|--------|----------|------|------|---------|---------|-------|------|---------------|---------------------|---------------|
| legacy018 | 0.18 | 4 | off | False | 126 | 102 | 9 | explore_budget_exhausted | 0.09336053880496603 | 0.14639370877246138 | 0.004705954666076317 |
| inf020_soft010 | 0.2 | 4 | R=0.1/w=2.0 | True | 126 | 106 | 7 | explore_budget_exhausted | 0.059398769020155895 | 0.09882281383603564 | 0.0988228874149274 |

## 三问
- 车身更居中？ mid 段 exec edge_p10：legacy=0.14639370877246138 → inf020=0.09882281383603564（Δ=-0.047570894936425745；正值=inf 更离墙）
- 被拒/截断减少？ blocked 102→106；trunc 9→7
- 任务结果？ legacy=explore_budget_exhausted success=False；inf020=explore_budget_exhausted success=False

硬膨胀格数：两侧 **inf_step=4**（res=0.05）。差异在连续圆盘格数与 soft band。
图：`/home/ubuntu/locomani/VLN_Mobilemanipulator_agentA_navinf/reports/nav_inf020_soft010_online_20261119/pair_sofa/sofa_pair_topdown.png`
