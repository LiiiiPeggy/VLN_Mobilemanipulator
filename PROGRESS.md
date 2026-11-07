# PROGRESS.md — 当前状态

更新时间：2026-11-07（startup_prior ObjectNav e2e：短预算 + 探针 + **b100 全量终表**）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：`startup_prior_mode` 已实现；HY1 冻结地图 A=0/26、B=5/26 可达；默认 **none**。ObjectNav e2e（同 24-ep 清单）短预算与 **预算100 全量 A/B 已完成**（`ab24_b100_20261107_123427`，48/48）。默认部署未改相机/门控/膨胀。

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| 包围不可通行归因 | **OK** | UNKNOWN moat；`hy1_surround_nontraversable_20261106` |
| 初始足迹先验 | **OK（接口 + e2e）** | 地图 HY1 B 可达 5/26；e2e B：start_blocked 0/24，SR_proxy 3/24（b100） |
| 默认 prior | **none** | launch / `STARTUP_PRIOR_MODE`；实验入口显式 `initial_footprint` |
| ObjectNav e2e b100 | **BATCH 终表** | `reports/startup_prior_e2e_20261107.md`；A SR 2/24，B 3/24；SPL N/A |
| 安全启动宣称 | **禁止** | 先验≠视觉 FREE；执行安全另验 |

## Baseline 冒烟（SG-Nav / UniGoal，2026-11-07）

| Baseline | 状态 | 证据 |
|----------|------|------|
| SG-Nav | **SINGLE_EPISODE_OK**（1ep MP3D；success=0） | `runs/SG-Nav/smoke_status.md`；`smoke_20261107_143201_host/` |
| UniGoal | **SINGLE_EPISODE_OK**（弱；SR/SPL=0） | `runs/UniGoal/smoke_1ep_status.md`；`luna_smoke120/.../total.json` |

## 下一步（最多 5）

1. **攻目标搜索 / 停止链路**（B 主失败仍 `explore_no_goal` 14/24；不扩 F0）。  
2. UniGoal 更长步数（500–1000）重跑；SG-Nav 小批量对照 MP3D 论文指标（自算 navmesh）。  
3. 车外环带观测覆盖重做（足迹外 0.3–1.0 m）— 与上项择一，勿并行大改。  
4. 可选独立：voxel Z-mix 最小复现。  
5. 合并前确认不污染 1.0× 默认路径；15° / PPO 训练仍缓开。
