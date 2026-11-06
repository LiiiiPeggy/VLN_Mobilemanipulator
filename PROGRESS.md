# PROGRESS.md — 当前状态

更新时间：2026-11-06（ground free-ray 单变量修复完成；eF36 通、HY1 残余；VLFM/MSGNav 并行队列）
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Ranger 几何 + 地面 free-ray。并行：**VLFM 全量 / MSGNav luna 队列** 仍可按各自 status 文件盯。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM | `BATCH_OK` → 全量（见 status） | `runs/VLFM/full_val_status.md` |
| ApexNav / MSGNav | `BATCH_OK` | MSGNav luna 见 `runs/MSGNav/luna_20ep_status.md` |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 0.7× + PPO / 深度 NaN / Demo Value+cell-fill | **OK** | 见前轮 |
| optical→ROS / 内参 / 底盘 `/odom` | **已修** | `a5e291b` |
| 运行时几何验收 | **OK** | `geometry_accept_20261106_post_a5e291b` |
| 正式 30° geomreg（修复前） | **已跑** | yr17 OK；eF36/HY1 起点 UNKNOWN→NO_PASSABLE |
| **地面 free-ray 单变量** | **已合入适配** | `map_ros/ground_free_ray_enable`；`inputFreeRayCloud2D` |
| groundfree 回归 yr17/eF36/HY1 | **已跑** | `reports/base_start_unknown_diagnosis.md` |
| eF36 原生规划 | **恢复** | 起点 FREE；20× EXPLORATION；0 NO_PASSABLE；位移≈3.17 m |
| yr17 对照 | **未回归** | 20× EXPLORATION；位移≈1.56 m |
| HY1 | **部分** | 前 3 次 EXPLORATION，起点仍 UNKNOWN，第 4 次 NO_PASSABLE |
| 足迹安全专项 | **未宣称** | blocked=0 仅代理；待 oriented footprint 回放 |
| 15° 正式环视 | **未开** | 先收口 HY1 底盘覆盖 |

## 下一步（最多 5）

1. **单变量跟进 HY1**：LOOK_DOWN 朝底盘侧地面可见性 / 自遮挡与地面带交互（勿叠 15°/膨胀）。  
2. 可选：yr17/eF36 oriented 足迹回放（规划成功 ≠ 足迹安全）。  
3. 盯 VLFM 全量 / MSGNav luna（各自 status）。  
4. yr17 日后另立 15° 候选。  
5. 合并前确认不污染 1.0× 默认路径。
