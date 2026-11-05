# PROGRESS.md — 当前状态

更新时间：2026-11-05（分支 `cursor/habitat-rangercr10-scale070`：抬臂后 NO_PASSABLE 修复）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：保留 PPO 抬臂交接（`f19f076`）。已定位抬臂后 `NO_PASSABLE_FRONTIER` 根因（AGL Z 错位 + 臂载相机/底盘起点分裂 + 自遮挡），适配层修复后 **yr17/HY1 恢复真实多步 EXPLORATION（含 FWD）**。标记 `scaled_robot_proxy_070`。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 0.7× + PPO 抬臂交接 | **OK** | `f19f076`；D455≈0.881；TCP≈0.811 short |
| 抬臂后 NO_PASSABLE 根因 | **已定位** | `apexnav_rangercr10_nopassable_after_ppo_raise.md` |
| 适配修复（AGL Z / odom=cam XY / self-hit 0.65） | **OK** | `coord_habitat_ros`；`ros_dynamic_publisher` |
| yr17 多步探索 | **恢复** | FWD 0.25 m；EXPLORATION×8；`..._yr17_fix_*` |
| HY1 多步探索 | **恢复** | n_explore=54；FWD 0.25 m；budget |
| eF36 | 弱多步 | EXPLORATION×1 后 STOP |
| yr17 7fps Demo | **OK** | 1280×720 7/1×167 |

## 下一步（最多 5）

1. 合并/评审本分支前确认不污染 1.0× 默认路径。  
2. eF36 进一步拉长探索（建图/Frontier 专项）。  
3. legacy018 vs 0.7× 半宽 0.304 膨胀匹配（勿冒充安全）。  
4. TCP 0.88 若需达标：训练侧扩 teleop 箱（禁 IK 凑数）。  
5. 停用后腾 GPU。
