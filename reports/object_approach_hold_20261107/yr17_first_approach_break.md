# yr17_chair_0 首次接近中断根因（基线 expand0.3 / denoise=none）

证据 run：`e2e_sp_ab24_A_none_20261107_172219_initial_footprint_yr17_chair_0`

## 第一次失败转移（不是终局标签）

| 项 | 值 |
|----|-----|
| 首次 SEARCH | `plan_seq=61` / habitat `step=86`，`result=SEARCH_BEST_OBJECT`，`stop_reason=object_path_ok` |
| 接近点 `selected_goal` | `[8.1909, 10.4706]`（ROS 地图 XY；`searchObjectPath` 在物体点外 0.5 m 可达格） |
| 底盘 `chassis_start` | `[6.4498, 10.1871]`；路径长 1.817 m |
| 参考系 | 规划与 REACH 用**底盘 odom** (`fd_->start_pt_`) 对 `ed_->next_pos_`；dtg 评估另用 Habitat 真值（仅评测） |
| 接近过程 | seq 61–66 共 6 次 SEARCH；底盘推进到 `[7.145, 10.400]`，距接近点 ≈1.22 m；`ndet` 在 step 90 起变 0 |
| **失败转移** | **`plan_seq=67`：无 `[Navigation Mode] Get object_cloud` 日志 → `getTopConfidenceObjectCloud()` 为空，直接落入 EXPLORATION**，frontier goal `[6.86, 13.11]` |
| 停止判断 | 全程无 `Reach the object`；`REACH_DISTANCE=0.20` 对接近点，当时仍 >1.2 m，**未进入停止分支** |
| 为何立刻丢弃 | `exploration_fsm.cpp`：上一拍 SEARCH 时 `replan_flag_=true`；探索稳定性启发式**只**在 `final_result_==EXPLORE && !replan_flag_` 时保留旧路径。SEARCH 丢云后无 hold → 改走 frontier |

## 触发条件 → 错误行为

`final_result_==SEARCH_OBJECT` 且本拍高置信 `object_clouds.empty()` → `planNextBestPoint` 返回 `EXPLORATION` → FSM **立即**采用新 frontier，放弃未完成接近。

## 最小修复

有界 ObjectHold：在上述条件下复用上一拍 `next_pos_`/`next_best_path_`，最多 `MAX_OBJECT_HOLD_MISS=12` 次，且距旧目标 ≤ `OBJECT_HOLD_MAX_DIST=3.0` m；重新 SEARCH 成功则清零计数。

## 修复后验证（`yr17_hold_20261107_215803`）

| 项 | 结果 |
|----|------|
| SR_proxy | **成功**（`planner_stop` ∧ dtg≈0.48 m） |
| ObjectHold | 6 次 keep（miss 1…6，距接近点 0.97→0.27 m） |
| Reach | 出现 `Reach the object successfully!!!` |
| SEARCH 步 | habitat expl_result=1 共 **13** 步（基线 6） |
| 仍无 SEARCH→探索→再 SEARCH 空转环 | 接近保持后直接闭合停止 |

视频：`.../e2e_sp_yr17_hold_20261107_215803_initial_footprint_yr17_chair_0/demo/apexnav_ranger_paper_demo.mp4`
