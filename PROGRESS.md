# PROGRESS.md — 当前状态

更新时间：2026-11-07（初始足迹通行先验实现 + HY1 冻结 A/B 通过）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：`startup_prior_mode` 已实现；HY1 冻结地图 A=0/26、B=5/26 可达；默认 **none**。默认部署未改相机/门控/膨胀。

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| 包围不可通行归因 | **OK** | UNKNOWN moat；`hy1_surround_nontraversable_20261106` |
| 初始足迹先验 | **OK（接口）** | `hy1_startup_prior_20261107`：B 可达 5/26；地图未改写 |
| 默认 prior | **none** | launch / `STARTUP_PRIOR_MODE` |
| 安全启动宣称 | **禁止** | 先验≠视觉 FREE；执行安全另验 |

## 下一步（最多 5）

1. 可选：`STARTUP_PRIOR_MODE=initial_footprint` 固定 spawn 短跑（仍不扩 F0）。  
2. 车外环带观测覆盖重做（足迹外 0.3–1.0 m）。  
3. 可选独立：voxel Z-mix 最小复现。  
4. 15° / PPO 训练仍缓开。  
5. 合并前确认不污染 1.0× 默认路径。
