# Sofa pair: legacy018 vs inf020_soft010

**锁已释放，B 可开始**（绘图在释放后完成）。

## 协议

- 复用已完成 126 步 `sofa_inf020`：episode/spawn/朝向/预算 150·100/`fixed_base_gimbal`/0.7/`kinematic_collision_v1.2`/F0+0.3 匹配（base_y 仅浮点噪声）。
- **两组硬膨胀均为 inf_step=4**（resolution=0.05 m）。legacy=0.18 lock=false soft off；inf020=0.20 lock=true soft R=0.10/w=2.0。

## 小表（重叠宽通道前 ~8 m 执行净空）

| | legacy018 | inf020_soft010 |
|--|--|--|
| termination | explore_budget_exhausted | explore_budget_exhausted |
| n_steps | 126 | 126 |
| success / near_goal | False/False | False/False |
| blocked / truncated | 102 / 9 | 106 / 7 |
| overlap edge_p10 (m) | 0.1464 | 0.0988 |
| overlap edge_mean (m) | 0.2556 | 0.2195 |
| full exec edge_min (m) | 0.09336053880496603 | 0.059398769020155895 |
| plan edge_min (m) | 0.004705954666076317 | 0.0988228874149274 |

## 三问

1. **车身更居中？** 否/不明显（重叠段 edge_mean 0.256→0.220；edge_p10 0.146→0.099）。
2. **拒/截断减少？** blocked 102→106（否）；truncated 9→7。
3. **任务结果？** 两侧均为 `explore_budget_exhausted`，success=False。

- 图：`/home/ubuntu/locomani/VLN_Mobilemanipulator_agentA_navinf/reports/nav_inf020_soft010_online_20261119/pair_sofa/sofa_pair_topdown.png`
- legacy：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentA_navinf/sofa_legacy_A_20261121_153625_sofa_legacy018`
- inf020：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/navinf020_20261119_210100_sofa_inf020`
