# PROGRESS.md — 当前状态

更新时间：2026-11-06（分支 `cursor/habitat-rangercr10-scale070`：相机/内参/底盘 odom 几何修复）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：在 `9fb8ea4` 上完成 **optical 投影 / 方像素内参 / 真实底盘 odom** 一致性修复与离线验证；正式 C++ episode 重测 NO_PASSABLE **待跑**。标记 `scaled_robot_proxy_070`。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 0.7× + PPO / 深度 NaN / Demo Value+cell-fill | **OK** | 见前轮；本轮未覆盖旧 Demo |
| optical→ROS / map_ros 位姿 | **已修** | `hab_optical_rot_to_ros`；发 optical 非 render |
| 内参 fx=fy≈388.19，VFOV≈63.45° | **已修** | `camera_model`；launch fy |
| `/odom` 真实底盘 XY | **已修** | 默认 `chassis`；legacy 可开关 |
| 离线坐标/内参验证 | **OK** | `reports/camera_coord_fix_20261106` all_pass |
| 正式 30° episode 几何回归 | **待跑** | 需同 spawn 短跑 |
| NO_PASSABLE 真实 C++ 拒绝原因 | **待验证** | Python diag 仅近似 |
| 15° 正式环视 | **未开** | 须几何回归后再独立实验 |

## 下一步（最多 5）

1. 同 yr17 spawn 跑正式 30° episode（chassis odom + 新投影），对照旧 mapfill。  
2. 记录真实底盘起点地图状态与 C++ 探索返回码（勿用 Python A* 冒充）。  
3. 若证实地面高度滤波导致 free 空洞，再单独开关 free 更新修复。  
4. 几何验收通过后再开 15° 环视（同步改每圈次数）。  
5. 合并前确认不污染 1.0× 默认路径。
