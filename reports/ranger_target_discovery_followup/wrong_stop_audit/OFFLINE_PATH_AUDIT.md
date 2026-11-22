# 离线路径审计：12 次错误 STOP

批次：`execgimbal_dev24_after_dinofix_20261119_011332`  
B commit：见 `/home/ubuntu/locomani/B_followup_safe/B_COMMIT.txt`  
证据：`OFFLINE_PATH_DETAIL.json`、各 run `steps.jsonl` / `actions.jsonl` / `launch_logs/exploration.log`

## 结论数字（当前可答）

| 问题 | 数字 |
|------|------|
| 12 次错误 STOP 中，可由 `NO_*_FRONTIER → FINAL NO_FRONTIER → ROS FINISH → ACTION STOP` 解释 | **12 / 12** |
| 配对失败例中因补视变成真正成功（STOP∧VIEW≤1m 且非 invalid spawn） | **待在线**（A 占锁；见下） |

elog 支持（含 `No (passable) frontier` + `PLAN_ACTION to FINISH`）：**12 / 12**。例外：**无**。

## 每例路径表

| id | spawn | moved_m | 最后原生规划 | FSM | 发出动作 | dtg@STOP |
|---|---|---:|---|---|---|---:|
| yr17_plant_0 | ok | 0.75 | NO_PASSABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 5.174 |
| yr17_chair_0 | ok | 0.75 | NO_PASSABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 3.949 |
| yr17_sofa_0 | ok | 0.75 | NO_PASSABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 10.640 |
| yr17_tv_0 | ok | 0.75 | NO_PASSABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 2.622 |
| ef36_plant_4 | ok | 0.525 | NO_COVERABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 8.331 |
| ef36_tv_3 | ok | 0.525 | NO_COVERABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 7.730 |
| ef36_toilet_3 | ok | 0.667 | NO_COVERABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 16.575 |
| hy1_plant_0 | ok | 2.458 | NO_PASSABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 2.313 |
| hy1_chair_3 | ok | 2.458 | NO_PASSABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 6.258 |
| hy1_plant_1 | ok | 2.458 | NO_PASSABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 2.313 |
| lt9_chair_1 | invalid_initial_penetration | 0.0 | NO_COVERABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 5.049 |
| lt9_toilet_2 | invalid_initial_penetration | 0.0 | NO_COVERABLE_FRONTIER | NO_FRONTIER→FINISH | STOP | 2.628 |

共性：`label_hist={}`、`n_search_best=0`、非 SEARCH 选错。  
`plan_results` 中 `NO_*_FRONTIER` 计数均为 **1**（首次空 frontier 即 FINISH→STOP）。

## 代表例环视机会（正常起点）

**hy1_plant_0**（ok spawn，moved≈2.46 m，dtg≈2.31 m）

- 停时 yaw 15° bin **13/24**，末 10 步 yaw 变化≈0.07 rad → 未做全景补视。  
- 全程无检测进入 SEARCH。  
- 离线结论：补视**可能**带来新观测，**不能**证明必有新 frontier → `plausible_unproven`（`LOOKAROUND_OPPORTUNITY_hy1_plant_0.json`）。

## NoFrontierLook 假设（离线 FSM 测试）

`NOFRONTIER_LOOK_FSM_TEST.json`：**PASS**

- OFF：立即 STOP  
- ON：最多 24 次 TURN_*（计入预算）后 FINISH→STOP，**不**死循环  
- frontier 恢复可回到 EXPLORE；REACH_OBJECT 仍立即结束  
- ROS 参数：`enable_no_frontier_look`（默认 **false**=关闭组；true=开启组）

## 在线配对（未跑）

A 占用 `vln-rangercr10-agentA-navinf` 编译/仿真锁。释放后 B 用独立 clone 源码挂载、私有 devel、独立输出目录跑 2–4 fail + 1 success。  
配对成功数字届时填入本表第二行。
