# near_goal 明细（短预算 fixed_base_gimbal 合并集）

定义：`near_goal` = 最终 VIEW_POINTS 距 ≤ 1.0 m。**不等于** SR_proxy，**不等于**成功接近。

| ep | dtg_init | dtg_final | dtg_min | moved_m | SEARCH_BEST | STOP | init_pen | term | 解释 |
|----|---------:|----------:|--------:|--------:|:-----------:|:----:|:--------:|------|------|
| dd4b_plant_5 | 0.17124176693556023 | 0.5129686440122485 | 0.037702122100161516 | 1.6 | True | False | False | step_budget_exhausted | translated_while_ending_near_goal |
| ef36_bed_4 | 0.03747628213348876 | 0.03747628213348876 | 0.03747628213348876 | 0.0 | False | False | False | step_budget_exhausted | spawn_or_static_near_goal_not_an_approach |
| k1cup_chair_0 | 0.855555024904601 | 0.855555024904601 | 0.855555024904601 | 0.0 | False | False | False | step_budget_exhausted | spawn_or_static_near_goal_not_an_approach |
| lt9_sofa_4 | 0.23145227668411147 | 0.23145227668411147 | 0.23145227668411147 | 0.0 | False | False | True | step_budget_exhausted | spawn_or_static_near_goal_not_an_approach |
| lt9_tv_0 | 0.32031109266764185 | 0.32031109266764185 | 0.32031109266764185 | 0.0 | False | False | True | step_budget_exhausted | spawn_or_static_near_goal_not_an_approach |

其中 `moved_m==0`：**4** / 5 — **禁止**表述为「成功接近但未停止」。

