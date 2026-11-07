# Object 接近保持（ObjectHold）最小修复（2026-11-07）

仿真 ObjectNav 效果验证（非实机安全）。冻结配置：`initial_footprint` + `expand_m=0.3` + `obstacle_denoise=none`。

## yr17 首次接近中断根因

详见 `object_approach_hold_20261107/yr17_first_approach_break.md`。

**第一次失败转移**（基线 `ab24_A_none`）：

1. `plan_seq=61` / step 86 进入 `SEARCH_BEST_OBJECT`（`object_path_ok`），接近点 ≈`[8.19,10.47]`，底盘 ≈`[6.45,10.19]`。
2. seq 61–66 持续接近，距接近点约 1.22 m；`ndet` 在 step 90 起变 0。
3. **`plan_seq=67`：无 `[Navigation Mode] Get object_cloud` → `getTopConfidenceObjectCloud()` 为空**，`planNextBestPoint` 直接返回 `EXPLORATION`。
4. FSM 在 `SEARCH_OBJECT` 时 `replan_flag_==true`，探索稳定性启发式不保留旧路径 → **立刻改走 frontier**。
5. 未调用停止成功分支（`REACH_DISTANCE=0.20` 对接近点，当时仍 ≫0.20）。

真实失败环节 = **接近中因瞬时丢目标云而放弃**；终局标签 `explore_no_goal` 是后续探索预算耗尽。

## 最小修复（单点）

| 文件 | 改动 |
|------|------|
| `exploration_fsm.cpp` / `exploration_data.h` / `exploration_fsm.h` | `ObjectHold`：若 `final_result_==SEARCH_OBJECT` 且本拍返回 `EXPLORATION`，复用上一拍 `next_pos_`/`path`，最多 12 次且距旧目标 ≤3.0 m |

**条件 → 行为**：丢云本会切 frontier；现有界保持接近点直至再次看见或到达 / 超时。

独立提交：`87a233e`。

## 验证

### yr17（`yr17_hold_20261107_215803`）

| 项 | 结果 |
|----|------|
| SR_proxy | **成功**（STOP ∧ dtg≈0.48） |
| ObjectHold | 6× keep（0.97→0.27 m） |
| Reach | 有 `Reach the object successfully!!!` |
| 视频 | `.../e2e_sp_yr17_hold_20261107_215803_.../demo/apexnav_ranger_paper_demo.mp4` |

### 同清单 24-ep（对照基线 A none）

| 指标 | 基线 A none | Hold |
|------|-------------|------|
| SR_proxy | **3/24** | **4/24** |
| start_blocked | 0 | 0 |
| explore_no_goal | 18 | 16 |
| stop_not_near | 3 | 4 |
| 曾选中目标（SEARCH） | 8 | 8 |
| 曾选中但未完成 | 5 | 4 |
| 首次选中→结束 平均步数 | 34.8 | 23.0 |
| 成功集 | ef36_bed_4, hy1_chair_3, lt9_chair_1 | **+ yr17_chair_0**（同上三者保留） |

证据：`ab24_compare.json`；批次 `ab24_hold_20261107_231416` vs `ab24_A_none_20261107_172219`。

## 结论

- **局部**：yr17「曾选中未闭合」→ 任务成功；机制与日志一致。
- **整批**：SR_proxy +1/24；原成功无回归；主失败仍多为从未进入 SEARCH 的 `explore_no_goal`（16/24）。
- **不继续叠加补丁**：Hold 已覆盖证据支持的丢弃分支；其余需另立「从未选中目标 / 停止近失」诊断。

SPL：N/A（无 geodesic）。成功代理仅 `planner_stop ∧ dtg≤1.0`，记为 **SR_proxy**。
