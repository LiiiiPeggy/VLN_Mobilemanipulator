# PROGRESS.md — 当前状态

更新时间：2026-11-22（主会话整合中：scale070 ← A navinf；B followup+V2 待合）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：**统一分支整合**（`cursor/habitat-rangercr10-scale070-integrate`）。主线 ApexNav Ranger 寻物效果与执行优化；桌边 C/D 采集识别已在 scale070。

## 整合来源（完整 SHA）

| 来源 | 分支 | SHA |
|------|------|-----|
| main | `main` | `2214550fa5f1b7c98e89b8b31f33fe15150c5415` |
| base | `cursor/habitat-rangercr10-scale070` | `66869af295099bc6ab5d5eef8d627b0a67538221` |
| A | `cursor/nav-inflation-halfwidth-softcost` | `d7926f9cd5710ea14219ce54afaeb6a22e5fcd37` |
| B tip | `cursor/ranger-target-discovery-followup` | `09fadf4890ce3ff8f55d9639ec87269fde3fc064` |
| B V2 | B clone 未提交 + `B_followup_safe/patches_v2_20261122` | 保全于 `reports/integration_20261122/b_v2/` |

细节：`reports/integration_20261122/SOURCE_SHAS.md`。

## Baseline 状态一览

| Baseline | 状态 | 要点 / 证据 |
|----------|------|-------------|
| ApexNav | **BATCH_OK** + HM3D-v2 **1000-ep 完成** | SR 74.4 / SPL 37.65；`reports/apexnav_hm3dv2_full_repro.md` |
| VLFM | **BATCH_OK** | `runs/VLFM/batch_8ep_status.md` |
| MSGNav | **BATCH_OK**；gpt-4o **BLOCKED** | luna：`runs/MSGNav/luna_20ep_status.md` |
| SG-Nav | **SINGLE_EPISODE_OK** | `runs/SG-Nav/smoke_status.md` |
| UniGoal | **SINGLE_EPISODE_OK（弱）** | `runs/UniGoal/smoke_1ep_status.md` |
| APRR | 环境/子模块未齐 | — |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| 执行碰撞门控 | **`kinematic_collision_v1.2`** | `9399dee` |
| 相机模式 | **`fixed_base_gimbal`** | `camera_modes.py` |
| robot_scale | **0.7** | 组会主对照 |
| A 规划膨胀/软代价 | **已合入（候选开关）** | `INFLATION_PROFILE=legacy018\|inf020_soft010`；在线 sofa：plan 净空↑但 exec/寻物无收益 |
| B NoFrontierLook / 目标发现 | **待合入** | 远端 `09fadf4`；V2 恢复策略待打补丁 |
| 桌边 C/D | **保留 scale070 终态** | 12 对 / 可靠 GT 9；`pairing_index.json` + `category_map` 别名 |

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| 整合未完成：B+V2、重编、四组对照 | 本文件 | 宣称 BATCH 改善 |
| A 规划净空未转执行净空 | `reports/nav_inf020_soft010_online_20261119/pair_sofa/` | 盲目加大膨胀 |
| B V2 hy1：dtg≈1.10 仍未成功；复跑未再进补视 | `RESULTS_post_look_noforward_fix.md` | 丢掉「未再进补视」条件 |
| toilet_2 初始化异常 | A narrow abort | 当有效失败计分 |

## 下一步（最多 5）

1. 合入 B followup + 打 V2 补丁（恢复策略开关）。  
2. 收敛统一入口；重编 plan_env / path_searching / exploration_manager。  
3. 四组对照：hy1_plant_0 + Dd4b toilet_0 × {legacy018,inf020} × {V2 off,on}。  
4. 有收益后再回归一原成功任务；toilet_2 单独处理。  
5. 本地验证后列出待推送提交与拟删除远端分支清单（不自动删远端）。
