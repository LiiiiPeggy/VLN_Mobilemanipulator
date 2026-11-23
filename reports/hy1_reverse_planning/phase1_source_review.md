# 阶段一：源码审查与 HY1 原始故障分析

**Git HEAD**：`0ef0f8f3d94d5386254bc0f4f45e53e93e45a99d`（与任务参考一致）  
**原始 run（方案 A 不可变记录）**：  
`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/ppo_chassis_hy1_20261123_220210_hy1_plant_0`

## 1. 规划/执行链路（与 HEAD 一致）

| 组件 | 结论 |
|------|------|
| `Astar2D::getPath()` | 返回 `std::vector<Eigen::Vector2d>` 平面路径 |
| `ed_->next_best_path_` | 同上二维点列；无朝向/档位 |
| `ExplorationFSM::planNextBestAction` | `selectLocalTarget` → `atan2` 得 `target_yaw` → `decideNextAction` |
| `decideNextAction` | 仅 `MOVE_FORWARD` / `TURN_LEFT` / `TURN_RIGHT`；无倒车 |
| `KinoAstar` | analytic shot 初始化为 **DubinsStateSpace**（0.2/0.1/0.05）；搜索 `arc` 采样 **≥0**；头文件虽 include `ReedsSheppStateSpace.h` 但未接入；注释写明 start 仅向前搜。**不能**认定已支持 Reeds–Shepp 双向规划 |
| Kino 车辆模型 | `wheel_base`/`max_cur`/`max_steer` 的自行车模型；与 Ranger 可近似原地转向 + PPO 基元能力 **不匹配** |

执行层：`EXEC_BACKEND=ppo_chassis` 回放宿主 MuJoCo `vel_cmd` 预计算片段（`move_forward`/`turn_*`），Habitat `probe_base_motion` 做碰撞门控。

## 2. 固定实验条件（原始 run）

| 项 | 值 |
|----|-----|
| scene | `HY1NcmCgn3n` |
| episode_id | `0` / plant |
| FORCE_SPAWN | `reports/.../frozen_spawns/hy1_plant_0_start_pose.json` |
| spawn xz/yaw | `(23.717, -1.433)`, yaw≈0.810（运行中经 init 后 explore 起始 yaw≈5.29） |
| robot_scale | 0.7 |
| LOOK / EXEC | `ppo_ee_rpy` / `ppo_chassis` |
| PPO raise | z040 |
| PPO chassis dir | `.../ppo_chassis_bundle_model9999` |
| checkpoint SHA256 | `94ffb7af2f9d0d8864920fb2a38f799938f2b7afffe8c7a75a1050057a5d7ce5` (`model_9999.pt`) |
| max_steps / max_explore | 50 / 20 |
| termination | `explore_budget_exhausted` |
| sum_moved_m | ≈0.85 |
| n_steps | 46 |

## 3. 故障时间线（explore step 26–45）

1. **step 27–28**：连续 `MOVE_FORWARD`，每次 PPO Δ≈**0.27 m**，位姿从 ~(23.49,-1.20) → ~(23.26,-1.05)。
2. **step 28 后**：局部 look-ahead 相对机体 **偏左 ~90°**（`look_df≈-0.01`, `look_dl≈+0.25`）；goal 相对前进方向开始变负。
3. **step 29+**：规划器反复请求 `TURN_RIGHT`；执行层因 **`base_link`/`box_link` 环境碰撞** 截断或整段拒绝（`min_robot_env_distance`≈0）。
4. **legacy recovery**：满 3 次同动作 blocked 后注入 `TURN_LEFT`，仍靠近墙体，随后再次被截断；形成左右摆动无净进展。
5. **step 43–44**：路径点 **behind 比例**升至 17/18、5/6；局部目标已主要在侧后，但仍只能转向/前进离散动作。
6. 预算耗尽，未 STOP / 未发现 plant。

**为何原地转向不可行**：机器人贴墙后，±30° 量级 PPO 转向足迹扫过障碍；碰撞门控拒绝/截断。二维 A* 不建模朝向与倒车，无法发出“先退后转”的可执行序列。

## 4. 方案 A 定位

本原始 run 即方案 A（二维 A* + 离散前进/转向 + 无路径引导倒车）的基线证据；后续对照须钉死同一 `FORCE_SPAWN_JSON` 与同等预算档。
