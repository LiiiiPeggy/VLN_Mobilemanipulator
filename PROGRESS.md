# PROGRESS.md — 当前状态

更新时间：2026-11-07（obstacle_denoise A/B **终表**；冻结 `initial_footprint`+`expand_m=0.3`）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Ranger ObjectNav 适配 — **启动已解封**；地图侧轻改（足迹先验 / F0 外扩 / median3）收益见顶。下一主线转 **目标搜索→接近→停止**。

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| **`explore_no_goal` 为主失败**（expand0.3：A 18/24，B 16/24） | denoise A/B 终表 | 再扩 F0、再加形态学/DBSCAN 去噪 |
| 部分 ep **看见/选中目标但接近未闭合**（如 yr17：6×SEARCH_BEST_OBJECT→退回探索→预算尽） | `yr17_failure_class.md` | 当成「从未找到」或纯停止门控问题 |
| SR_proxy 仍低（~3–4/24）；SPL / 净位移本路径 **N/A** | 无 geodesic / 无位姿轨迹 | 用 SPL 或安全启动作宣称 |
| SG-Nav / UniGoal 仅弱冒烟（SR/SPL=0），非论文复现 | `runs/SG-Nav`、`runs/UniGoal` | 与 Ranger 主线混谈进度 |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| 包围不可通行归因 | **OK** | UNKNOWN moat；`hy1_surround_nontraversable_20261106` |
| 初始足迹先验 | **OK（接口 + e2e）** | 消除 start_blocked；HY1 地图可达 5/26 |
| F0 外扩 expand=0.3 | **OK（冻结）** | 半轴 0.756×0.604 m，729 cells；e2e start_blocked=0 |
| 障碍去噪 median3 | **OK（A/B 终表）；默认关** | A 3/24 vs B 4/24；`reports/obstacle_denoise_ab_20261107.md` |
| 默认 launch | prior **none** / expand **0** / denoise **none** | 实验入口：`initial_footprint`+expand **0.3** |
| ObjectNav e2e b100（expand=0） | **BATCH 终表** | A 2/24，B 3/24；`startup_prior_e2e_20261107` |
| ObjectNav e2e expand0.3 ±denoise | **BATCH 终表** | none 3/24；med3 4/24 |
| 安全启动宣称 | **禁止** | 先验≠视觉 FREE |

## Baseline 冒烟（SG-Nav / UniGoal，2026-11-07）

| Baseline | 状态 | 证据 |
|----------|------|------|
| SG-Nav | **SINGLE_EPISODE_OK**（1ep MP3D；success=0） | `runs/SG-Nav/smoke_status.md` |
| UniGoal | **SINGLE_EPISODE_OK**（弱；SR/SPL=0） | `runs/UniGoal/smoke_1ep_status.md` |

## 下一步（最多 5）

1. **攻目标搜索 / 接近 / 停止链路**（主卡点；yr17 类「曾 SEARCH 未闭合」优先拆）。  
2. UniGoal 更长步数；SG-Nav 小批量 MP3D（自算 navmesh）。  
3. 车外环带观测覆盖（足迹外 0.3–1.0 m）— 与上项择一。  
4. 合并前确认不污染 1.0× 默认路径；15° / PPO 训练仍缓开。  
5. （可选）median3 仅噪声敏感场景个案复测，不默认开。
