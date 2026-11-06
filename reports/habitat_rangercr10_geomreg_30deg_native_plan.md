# a5e291b 后正式 30° 闭环回归与原生规划归因

更新：2026-11-06  
分支：`cursor/habitat-rangercr10-scale070`  
基准：`a5e291b`  
配置不变：PPO 抬臂、0.7×、相机安装、初始关节、膨胀 `legacy018`、unknown 通行、free/occupied 更新逻辑、环视 30°。  
本轮**未**改 free 更新策略，**未**开 15° 正式环视。

---

## 分层结论（勿混用）

| 层级 | 结果 |
|------|------|
| 解析检查（离线，a5e291b） | 已通过 |
| **运行时几何验收**（独立诊断） | **通过** |
| 探索成功（可持续 callActionPlanner） | **yr17 通过；eF36/HY1 首规划即 NO_PASSABLE** |
| 任务成功（ObjectNav） | **均未宣称**（`success_claimed=false`） |

---

## 1. 收尾

- 调用方：`object_clouds_from_masks` / ROS publish 已用 **optical**；探针脚本去掉 `Rx(π)` render。
- `pointcloud_consistency_check.py`：改为**同一世界点**多视角重投影（不再把不同视角中心块当成同一物体）。
- 文档：「重叠 49%」→ **重叠 49°，约占 79° HFOV 的 62%**；「未 TURN_DOWN 光轴朝上」→ **待实际光轴测量验证**；VFOV 59.25° 维持降级。

---

## 2. 运行时几何验收

目录：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/geometry_accept_20261106_post_a5e291b`  
摘要副本：`reports/geomreg_30deg_20261106/geometry_acceptance_summary.json`

| 项 | 结果 |
|----|------|
| Habitat 方像素 K vs ROS `fx/fy/cx/cy` | 一致（\|Δ\|≪0.5） |
| 中心/四角/边缘：sensor_pose 射线 vs map_ros 反投影 | 最大角误差 ≪0.5° |
| 原地转向 / 只动臂 → 底盘 odom XY | 不变 |
| MOVE_FORWARD 0.25 m → odom 位移 | 通过 |
| 几何自遮挡掩码 | `ok_geometric`（无 fallback） |

诊断与正式探索指标隔离。

---

## 3. 原生 C++ / 建图诊断（可关）

Launch 参数：`plan_diag_enable` / `pipeline_diag_enable` →  
`native_diag/native_plan_diag.jsonl`、`map_pipeline_diag.jsonl`。

- **原始搜索返回码** `REACH_END` / `NO_PATH` 与 **reject_counts_inferred**（邻域安全检查累计）分开记录。
- 大量 `unknown` 推断计数 **≠** 唯一失败原因；须结合 `start_raw_occ` 与可达候选数。

---

## 4. 三场景有界回归（30° 环视 + ≤20 探索决策）

| 场景 | run_id | 终止 | 规划结果 | 起点 raw occ | 可达候选 | FWD | 净位移 |
|------|--------|------|----------|--------------|----------|-----|--------|
| yr17 | `…yr17_geomreg_20261106_122201` | step_budget (46) | 20× EXPLORATION | FREE(1) | 27/29（首次） | 4 | ≈0.85 m |
| eF36 | `…ef36_geomreg_20261106_123905` | planner_stop | 1× **NO_PASSABLE** | **UNKNOWN(0)** | 0/11 | 0 | ≈0 |
| HY1 | `…hy1_geomreg_20261106_124125` | planner_stop | 1× **NO_PASSABLE** | **UNKNOWN(0)** | 0/21 | 0 | ≈0 |

证据 JSON：`reports/geomreg_30deg_20261106/compare_summary.json`。

### yr17

- 首次规划：`start_inflate=0`，`start_distance>0`，active frontiers 多且可达。
- **无 NO_PASSABLE**；持续探索（TURN/FWD 混合）。
- 不以 free 格增加或 exit 0 作为任务成功。

### eF36 / HY1（原生归因）

- 结果码：`NO_PASSABLE_FRONTIER`，`stop_reason=all_frontier_searches_failed`。
- 底盘起点 **`start_raw_occ=UNKNOWN`**（非 OCCUPIED / 非 inflate 自撞）。
- 候选 A*：`raw_return=NO_PATH`；`reject_counts_inferred` 以 **unknown** 为主，occupied/inflate≈0。
- 同帧 pipeline：相机邻域常有 `window_free>0` 且相机处 `start_raw_occ=FREE`，与**底盘** UNKNOWN 并存 → 臂载相机覆盖未在底盘足迹处留 free 证据。
- 全程 `height_ground_band=0`（高度带把近地/中间带点计入 `height_other` 丢弃）——**观察项**；本轮不改 free 策略。

---

## 5. 下一步

1. **优先**：单变量任务修复 eF36/HY1 的 **底盘起点 free 缺口**（观测覆盖 / 掩码 / 地面高度带），用失败帧+格子证据；勿与 15° 捆绑。  
2. **暂缓**正式 15° 环视（2/3 场景仍 NO_PASSABLE）。  
3. yr17 几何稳定且可探索，仅作 15° 对照的**候选场景**，须另立项。

---

## 6. 最终五问

1. **渲染 / ROS / map_ros 是否一致？** 运行时验收：**是**。  
2. **底盘 odom 与动态自遮挡是否实测通过？** **是**。  
3. **修复后是否仍出现 NO_PASSABLE？** **视场景**：yr17 否；eF36/HY1 是。  
4. **原生证据支持哪类原因？** eF36/HY1：**底盘起点 UNKNOWN + 路径 unknown 阻断**（非投影/odom，非 inflate 主导）。  
5. **下一步？** **修 free 更新 / 底盘覆盖**；**不要**先开 15°。
