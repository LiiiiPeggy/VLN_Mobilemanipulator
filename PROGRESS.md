# PROGRESS.md — 当前状态

更新时间：2026-11-05（分支 `cursor/habitat-rangercr10-scale070`：Demo Occ+Value Map 叠加）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：0.7× + PPO 抬臂 + 深度 NaN 修复保留。本轮仅改 Demo：右下角叠加 ApexNav 原生 value_map 热力。标记 `scaled_robot_proxy_070`。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 0.7× + PPO 抬臂 / NO_PASSABLE / 深度 NaN | **OK** | 见前轮报告 |
| Demo Occ + Value Map | **OK** | `/grid_map/value_map` 叠加；`..._valuemap_20261105_210015` |
| 7fps Demo 1280×720 | **OK** | `apexnav_ranger_paper_demo_7fps.mp4`（346 帧，7/1） |

## 下一步（最多 5）

1. 合并/评审前确认不污染 1.0× 默认路径。  
2. 视需要收紧自遮挡 AABB pad。  
3. eF36 进一步拉长探索。  
4. TCP 0.88 若需达标：训练侧扩 teleop 箱（禁 IK）。  
5. 停用后腾 GPU。
