# PROGRESS.md — 当前状态

更新时间：2026-11-04（ApexNav 转向修复后：狭窄验证 + 中档膨胀对照）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Stage 4.10d + 7 FPS Demo 保留；odom 航向 π 已修；开阔/狭窄/中档膨胀对照完成。Habitat 演示默认 `legacy018`（标不安全）；实机安全档 `ranger_safe` 会吃光 free。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| Stage 4.10d 钉扎 | 保持 | `VERSION_stage410d.json` |
| Demo 7 Hz（原开场景） | 保持 | `20261104_114652/.../7fps.mp4` |
| Demo 7 Hz（yaw 修复后） | 已重渲 | `real_yawfix_legacy018_*/.../7fps.mp4` |
| odom 航向 | **已修** `hab_yaw+π` | yaw 误差≈0° |
| 开阔 yaw+0.18 | 多步探索 FWD 1.25 m | `real_yawfix_legacy018_*` |
| 开阔 yaw+0.30 / 0.485 | free≈0–1，早停 | `real_yawfix_open_mid030_*` / `*_footprint_*` |
| 狭窄 yaw+0.18 | 仍 `NO_PASSABLE` STOP×1 | `real_yawfix_narrow_legacy018_*` |
| 膨胀对照报告/面板 | 完成 | `reports/apexnav_rangercr10_frontier_inflation.md` |

## 下一步（最多 5）

1. 非圆足迹或未知区策略，解决安全半径与可达 Frontier 冲突（窄场景优先）。  
2. PPO→Habitat 观测对齐（不阻塞）。  
3. 点云一致性报告完善。  
4. 停用后腾 GPU（注意勿杀他人 Stage4.11 训练）。
