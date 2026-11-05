# PROGRESS.md — 当前状态

更新时间：2026-11-05（场景筛选 + yr17 多步 ApexNav + 四轮可视化）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Stage 4.10d / yaw 修 / 7 FPS 保留；完成 HM3D×ObjectNav 场景通行性筛选；在 **yr17PDCnDDW** 上验证真实 ApexNav 多步探索（开放带 spawn）；四轮运动学可视化烟雾通过。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| Stage 4.10d / yaw+π / legacy018 | 保持 | 既有报告 |
| 场景清单 + Top-5 通行性 | 完成 | `scene_clearance/ranking.md` |
| yr17 多步探索 | **OK** FWD×6 / 1.5 m | `real_wide_yr17_openband_*` |
| HY1 同策略 | 仍早停 | `real_wide_hy1_openband_*` |
| 开放带 spawn | 适配层 | `spawn_utils.prefer_open_clearance` |
| 四轮滚动/转向可视化 | 烟雾 pass | `wheel_kinematics_smoke/` |
| 场景筛选报告 | 完成 | `reports/apexnav_rangercr10_scene_screening.md` |

## 下一步（最多 5）

1. 对 Top-5 其余场景做开放带 spawn 短验证；必要时扩展出生点邻域观测/环视。  
2. yr17（及成功 ep）7 FPS Demo 落盘确认。  
3. 非圆足迹规划仍为中长期（本轮未改 ApexNav）。  
4. PPO→Habitat 观测对齐（不阻塞）。  
5. 停用后腾 GPU（勿杀他人训练）。
