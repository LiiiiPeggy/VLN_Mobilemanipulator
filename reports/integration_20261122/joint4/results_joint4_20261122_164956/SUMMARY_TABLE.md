# Joint4 八组结果表

Batch `joint4_20261122_164956` · 源码冻结 `a77f7d9` · 容器 `vln-rangercr10-integrate` · **PPO 未调用**（fixed_base_gimbal + ARM_DEFAULT）· 补视 OFF

## 主表

| 组 | 案例 | 规划 | 恢复 | valid | success | near_goal | termination | steps | sum_moved | dtg | blocked | trunc | recov | FF_try/exec/moved | 主导碰撞原因 |
|----|------|------|------|-------|---------|-----------|-------------|-------|-----------|-----|---------|-------|-------|-------------------|--------------|
| g1_hy1_legacy_off | hy1_plant_0 | legacy018 | legacy | True | False | False | planner_stop | 84 | 2.458 | 2.313 | 30 | 8 | 3 | 0/0/0 | robot_env_collision:22,truncated_at_robot_env_collision:8 |
| g2_hy1_inf020_off | hy1_plant_0 | inf020_soft010 | legacy | True | False | False | explore_budget_exhausted | 126 | 3.85 | 1.628 | 36 | 5 | 6 | 0/0/0 | robot_env_collision:28,truncated_at_robot_env_collision:5 |
| g3_hy1_legacy_on | hy1_plant_0 | legacy018 | v2 | True | False | True | explore_budget_exhausted | 126 | 5.708 | 0.485 | 56 | 14 | 11 | 5/3/3 | robot_env_collision:42,truncated_at_robot_env_collision:14 |
| g4_hy1_inf020_on | hy1_plant_0 | inf020_soft010 | v2 | True | False | False | planner_stop | 43 | 2.4 | 1.836 | 15 | 3 | 2 | 1/0/0 | robot_env_collision:12,truncated_at_robot_env_collision:3 |
| g1_dd4b_legacy_off | Dd4b_toilet_0 | legacy018 | legacy | True | False | False | explore_budget_exhausted | 126 | 2.375 | 2.716 | 42 | 7 | 5 | 0/0/0 | robot_env_collision:33,truncated_at_robot_env_collision:7 |
| g2_dd4b_inf020_off | Dd4b_toilet_0 | inf020_soft010 | legacy | True | False | False | explore_budget_exhausted | 126 | 4.55 | 2.107 | 49 | 13 | 5 | 0/0/0 | robot_env_collision:34,truncated_at_robot_env_collision:13 |
| g3_dd4b_legacy_on | Dd4b_toilet_0 | legacy018 | v2 | True | False | False | explore_budget_exhausted | 126 | 2.133 | 3.011 | 69 | 13 | 12 | 5/4/5 | robot_env_collision:56,truncated_at_robot_env_collision:13 |
| g4_dd4b_inf020_on | Dd4b_toilet_0 | inf020_soft010 | v2 | True | False | False | explore_budget_exhausted | 126 | 2.633 | 2.991 | 60 | 12 | 12 | 6/6/6 | robot_env_collision:48,truncated_at_robot_env_collision:12 |

## 恢复动作细分（v2 组）

| 组 | opposite_try | FF_try | FF_exec | FF_moved | recovery_executed_ok | recovery_blocked |
|----|--------------|--------|---------|----------|----------------------|------------------|
| g3_hy1_legacy_on | 6 | 5 | 3 | 3 | 8 | 3 |
| g4_hy1_inf020_on | 1 | 1 | 0 | 0 | 1 | 1 |
| g3_dd4b_legacy_on | 5 | 5 | 4 | 5 | 9 | 3 |
| g4_dd4b_inf020_on | 6 | 6 | 6 | 6 | 10 | 2 |
