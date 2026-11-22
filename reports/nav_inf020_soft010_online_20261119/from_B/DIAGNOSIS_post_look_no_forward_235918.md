# B 诊断：补视恢复探索后无 MOVE_FORWARD

**证据批**：`agentB_phase0_hy1_20261121_235918_hy1_plant_0_ON`  
**对照 OFF**：同批 `..._OFF`（84 步 `NO_PASSABLE`→FINISH→STOP，与审计一致）  
**时间线表**：`ON_POST_NF_TIMELINE.md` / `.json`

## 补视退出（15/24）

- 首次 `expl_result=4`：habitat **step 83** ↔ native `plan_seq=42`
- 连续 15 步 NoFrontierLook（83–97），**未**打满 24
- 退出原因：`plan_seq=57` 起 `result=EXPLORATION` / `frontier_path_ok`，FSM 将 `no_frontier_look_count_` 清零并回到 PUB_ACTION（非 max 耗尽）

## 链路断点（最早异常）

| 节点 | 证据 |
|------|------|
| NF 触发 | seq42：`n_active_frontiers=18` 但 `n_reachable=0`，`start_inflate=1`，`inf_within_0p3=56`，`stop_reason=all_frontier_searches_failed` |
| 补视中 | 几乎全是 `TURN_LEFT`→`robot_env_collision`；recovery 仅 `LOOK_*`；yaw 钉死 `3.6025` |
| 恢复探索 | step98 / seq57：`path_ok`，`start_inflate=0`，goal=`[2.0,-23.4188]`，`path_len≈1.65` |
| **最早断点** | step98：`decideNextAction`→`TURN_RIGHT`，exec=`TURN_RIGHT_TRUNCATED`，`block_reason=truncated_at_robot_env_collision`；blocking links=`d455_link`,`gripper_finger1_finger_tip_link` |
| 之后 | 反复 `TURN_RIGHT_BLOCKED`；recovery 每 3 次发 `TURN_DOWN`（gimbal），常 `gimbal_pitch_limit`；**0 次 MOVE_FORWARD**；`moved_m_after_first_nf=0`；预算耗尽 |

根因（B 侧可修部分）：`fixed_base_gimbal` 下 `blocked_recovery` 对 turn 只做云台 LOOK，**不能改底盘航向**，与规划器持续要 `TURN_*` 死锁。NoFrontierLook 旧逻辑也只发 `TURN_LEFT`。

## B 最小修复（已改，待复跑）

1. `apexnav_real_episode.py`：turn 连续全挡 → `opposite_turn` → 再挡则 `forced_forward_after_turn_block`（不再对 turn 优先 gimbal look）
2. `exploration_fsm.cpp` NoFrontierLook：`TURN_LEFT`/`TURN_RIGHT` 交替 + 偶发 look up/down

`enable_no_frontier_look` 默认仍为 **false**。

## 与 A 净空的交接（见 `HANDOFF_TO_A_clearance.md`）

规划 `start_inflate` / 路径净空 vs 执行器 3D `robot_env_collision`（臂/相机）不一致；B 修复不替代 A 的膨胀/软代价工作。
