# PROGRESS.md — 当前状态

更新时间：2026-11-05（分支 `cursor/habitat-rangercr10-scale070`：深度有效性 / 环视放射伪影修复）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：保留 PPO 抬臂交接与 NO_PASSABLE 适配修复。本轮确认近距→5 m 改写会造成虚假射线终点；改为 **NaN + C++ skip + 几何自遮挡**。标记 `scaled_robot_proxy_070`。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 0.7× + PPO 抬臂交接 | **OK** | D455≈0.881；TCP≈0.811 short |
| 抬臂后 NO_PASSABLE | **已修** | AGL Z / odom=cam XY |
| 无效深度处理 | **OK** | NaN skip；禁止改写 5 m |
| 几何自遮挡 | **OK** | 球+胶囊+AABB；`depth_validity.py` |
| yr17 环视+短程规划 | **OK** | `..._depthfix4_*`：FWD 0.50 m；occ/free 727/932 |
| map_ros NaN 补丁 | **OK** | 需 `libplan_env.so` 已重建 |

## 下一步（最多 5）

1. 合并/评审前确认不污染 1.0× 默认路径。  
2. 视需要收紧 AABB pad，减少近距真家具误掩。  
3. eF36 进一步拉长探索（建图/Frontier 专项）。  
4. TCP 0.88 若需达标：训练侧扩 teleop 箱（禁 IK）。  
5. 停用后腾 GPU。
