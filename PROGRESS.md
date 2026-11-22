# PROGRESS.md — 当前状态

更新时间：2026-11-22（主会话：scale070 已合 A+B；V2 补丁与重编/四组对照进行中）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：**统一分支整合与最小联合验证**。工作树：`/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate`（`cursor/habitat-rangercr10-scale070-integrate`）。主线 ApexNav 寻物效果与执行优化。

## 整合来源（完整 SHA）

| 来源 | 分支 | SHA |
|------|------|-----|
| main | `main` | `2214550fa5f1b7c98e89b8b31f33fe15150c5415` |
| base | `cursor/habitat-rangercr10-scale070` | `66869af295099bc6ab5d5eef8d627b0a67538221` |
| A | `cursor/nav-inflation-halfwidth-softcost` | `d7926f9cd5710ea14219ce54afaeb6a22e5fcd37` |
| B tip | `cursor/ranger-target-discovery-followup` | `09fadf4890ce3ff8f55d9639ec87269fde3fc064` |
| B V2 | B clone 未提交 | `reports/integration_20261122/b_v2/` |

## Baseline 状态一览

| Baseline | 状态 | 要点 / 证据 |
|----------|------|-------------|
| ApexNav | **BATCH_OK** + HM3D-v2 **1000-ep** | SR 74.4 / SPL 37.65 |
| VLFM | **BATCH_OK** | `runs/VLFM/batch_8ep_status.md` |
| MSGNav | **BATCH_OK**；gpt-4o **BLOCKED** | luna 20ep |
| SG-Nav | **SINGLE_EPISODE_OK** | 官方 navmesh 18/20 中断 |
| UniGoal | **SINGLE_EPISODE_OK（弱）** | — |
| APRR | 环境未齐 | — |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| 碰撞门控 / 相机 / scale | `kinematic_collision_v1.2` / `fixed_base_gimbal` / **0.7** | 既有 |
| A 膨胀/软代价 | **已合入**；开关 `INFLATION_PROFILE` | sofa：plan↑ exec/寻物无收益 |
| B NoFrontierLook / 检测同义词 | **已合入**；`enable_no_frontier_look` 默认 false | `09fadf4` |
| B V2 恢复 | **待打补丁+开关** | Look 交替；opposite→forced_forward；仅平移清零 |
| 桌边 C/D | **scale070 终态** | 12 对 / 可靠 9；别名保留 |

## B 实验要点（已收拢）

- phase0 hy1 OFF 复现错误 STOP；ON@235918 补视后 turn 死锁、0 前进。  
- V2@124800：`sum_moved` 2.46→4.26，`dtg` 2.31→1.10，仍未成功；**未再进 NoFrontierLook**（须保留该条件）。  
- 证据：`reports/integration_20261122/b_v2/RESULTS_post_look_noforward_fix.md`

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| V2 未进统一树 / 未重编验证 | 本文件 | 宣称联合收益 |
| 规划净空≠执行净空 | A sofa/narrow 报告 | 只加大膨胀 |
| toilet_2 init 异常 | A narrow abort | 当有效失败 |

## 下一步（最多 5）

1. 打入 B V2（带 `BLOCKED_RECOVERY_MODE` 开关）并拷贝关键未提交证据。  
2. 统一入口 `run_apexnav_real_episode.sh`；重编 plan_env+path_searching+exploration_manager。  
3. 四组对照 hy1_plant_0 + Dd4b toilet_0。  
4. 有收益后加一原成功任务回归；toilet_2 独立处理。  
5. 本地交付后列待推送与拟删远端分支（不自动删）。
