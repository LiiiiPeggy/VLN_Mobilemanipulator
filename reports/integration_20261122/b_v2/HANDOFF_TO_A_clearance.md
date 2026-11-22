# A 交接：规划净空 vs 执行净空（hy1_plant_0 / 235918 ON）

**运行目录**：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentB_nofrontier/agentB_phase0_hy1_20261121_235918_hy1_plant_0_ON`  
**B 分支**：`cursor/ranger-target-discovery-followup` @ `09fadf4`+（本批后含 recovery 修复，待新 batch）  
**场景**：`HY1NcmCgn3n` / plant / episode_id=0 / frozen spawn `hy1_plant_0_start_pose.json`

## 交接点 1 — 有前沿但 start_inflate 堵死搜索

| 字段 | step82 / seq41 | step83 / seq42 (首次 NF) |
|------|----------------|--------------------------|
| result | EXPLORATION | NO_PASSABLE_FRONTIER |
| stop_reason | frontier_path_ok | all_frontier_searches_failed |
| n_active_frontiers | 18 | 18 |
| n_reachable_candidates | 22 | **0** |
| start_inflate | **0** | **1** |
| start_raw_occ | 2 | 2 |
| inf_within_0p3 | 0 | **56** |
| chassis_start (ROS) | `[3.4431, -22.6179]` | （同 pose 钉死） |
| selected_goal | `[1.25, -23.5725]` | — |

**代码位置（规划侧）**：`exploration_fsm` / frontier search 在 start 落入 inflate 时记 `start_inflate` 并导致候选全失败 → `FINAL_RESULT::NO_FRONTIER`。  
**与 A 任务对齐**：膨胀半径 / 软代价 / 窄通道配对；此处是「前沿仍在、起点 inflate 使 n_reach=0」的实测样本。

## 交接点 2 — 规划 path_ok 后执行转不动

| 字段 | step98 / seq57 |
|------|----------------|
| result | EXPLORATION / frontier_path_ok |
| start_inflate | 0 |
| n_reachable | 22 |
| selected_goal | `[2.0, -23.4188]` |
| selected_path_len | 1.6527 |
| Habitat base | x=22.618, z=-3.443, yaw≈3.515 |
| planner_action | TURN_RIGHT |
| exec | TURN_RIGHT_TRUNCATED → 随后多次 TURN_RIGHT_BLOCKED |
| block_reason | truncated_at_robot_env_collision / robot_env_collision |
| blocking links | **d455_link**, **gripper_finger1_finger_tip_link**（非仅轮足迹） |
| min_robot_env_distance | ≈ -0.018 m |

路径在 2D inflate 图上可搜，底盘/臂/相机在 Habitat 碰撞检测中无法完成 yaw。这是 **规划净空 ≠ 执行净空** 的直接证据。

## B 不改动的范围

- 不改 shared nav-inflation / 软代价参数（A 线）
- B 仅修：NoFrontierLook 左右交替 + gimbal 模式下 turn 挡死后的底盘 recovery 升级
- 联合实验等双方各自结果明确后再排
