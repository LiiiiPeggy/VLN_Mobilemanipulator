# PROGRESS.md — 当前状态

更新时间：2026-11-04（ApexNav 转向/膨胀诊断；odom 航向 π 修复）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Stage 4.10d + 7 FPS Demo 保留；已定位并修复 Habitat→ROS **odom 航向差 π**（频繁左转主因）；足迹/膨胀对照完成，适配层提供 `legacy018` / `ranger_safe` 两档。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| Stage 4.10d 钉扎 | 保持 | `VERSION_stage410d.json` |
| Demo 7 Hz | 保持 | `apexnav_ranger_paper_demo_7fps.mp4` |
| odom 航向 | **已修** `hab_yaw+π` | `real_yawfix_legacy018_*` 误差≈0° |
| 膨胀 0.18 vs 足迹 | 对照完成 | `reports/apexnav_rangercr10_frontier_inflation.md` |
| 默认 Habitat profile | `legacy018`（标不安全） | `INFLATION_PROFILE` |
| 安全足迹 profile | `ranger_safe` 0.485 m | overlay yaml |

## 下一步（最多 5）

1. 稀疏 free 下安全足迹与可达 Frontier 的折中（或臂/足迹非圆模型）。  
2. 可选：yaw 修复后重渲 7 FPS 对比 Demo。  
3. PPO→Habitat 观测对齐（不阻塞）。  
4. 点云一致性报告完善。  
5. 停用后腾 GPU。
