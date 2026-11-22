# B 结果：补视后无前进 — 诊断 + 最小修复 + hy1 配对

锁：`/home/ubuntu/locomani/_sim_host_run.lock`（批次结束后已 **LOCK_FREE**）  
分支：`cursor/ranger-target-discovery-followup`（B clone）  
开关：`enable_no_frontier_look` 默认仍 **false**；本批 ON 显式 true。

## 三问（结论）

1. **新 frontier 回来后链路断在哪？**  
   离线 235918 ON：补视 15/24 因 `EXPLORATION` 返回退出 → `decideNextAction` 持续 `TURN_*` → exec `robot_env_collision`（`d455_link`/`gripper`）→ gimbal recovery 不改航向 → **0× MOVE_FORWARD**。最早异常 **step98 / plan_seq57**。

2. **修复能否恢复前进？**  
   **部分可以。** V2（opposite_turn → forced_forward，且仅平移清零 escalate）在同 spawn hy1 ON：`forced_forward`×5（其中 3 次真前进 0.25m），`sum_moved_m` 2.46→**4.26**，`final_dtg` 2.31→**1.10**。仍预算耗尽、未 ObjectNav 成功。本两次 ON 复跑轨迹未再进入 NoFrontierLook（无 `expl=4`），故「补视后」同路径未复现，但 turn 死锁→前进的机制已验证。

3. **与 A 净空是否有验证关联？**  
   **有（来自 235918）。** seq42：`n_active=18` 且 `start_inflate=1`→`n_reach=0`；seq57 path_ok 后执行仍转不动（3D 臂/相机碰撞）。交接：`HANDOFF_TO_A_clearance.md`。

## 修复内容（B）

| 改动 | 文件 |
|------|------|
| NoFrontierLook `TURN_LEFT`/`RIGHT` 交替 | `exploration_fsm.cpp` |
| turn 挡死：opposite → forced MOVE；gimbal 不再优先处理 turn | `apexnav_real_episode.py` |
| 仅 `moved_m>0` 清零 escalate（防 yaw 振荡永不前进） | 同上 |

## 同 spawn 对比

| | BEFORE 235918 ON | V1 042800 | V2 124800 |
|--|------------------|-----------|-----------|
| sum_moved_m | 2.46 | 1.42 | **4.26** |
| final_dtg | 2.31 | 3.10 | **1.10** |
| NoFrontierLook 步 | 15 | 0 | 0 |
| forced_forward | 0 | 0 | **5** |
| MOVE 事件数 | 18（NF 后 0） | 7 | **28** |
| 终止 | budget | budget | budget |

证据目录：  
- BEFORE：`.../agentB_phase0_hy1_20261121_235918_hy1_plant_0_ON`  
- V2：`.../agentB_phase0b_fix_20261122_124800_hy1_plant_0_ON`  
- 数值：`COMPARE_post_look_fix.json`
