# stop_not_near：目标身份 / 接近点 / 停止与评估口径（2026-11-09）

仿真 ObjectNav。冻结：`initial_footprint` + `expand_m=0.3` + `denoise=none` + ObjectHold + LabelMap。  
基线轨迹：`ab24_labelmap_20261108_220204`（相对 Hold `ab24_hold_20261107_231416`）。

## 错误条件 → 错误行为 → 本次修改

| | |
|--|--|
| **错误条件** | 适配层 `goal_distance()` 用物体中心 `goal.position`（POINT）；Habitat ObjectNav `DistanceToGoal` 默认 `distance_to=VIEW_POINTS` |
| **错误行为** | 机器人已 STOP 在合法 viewpoint 附近（沙发/床/椅），却因中心距 >1.0 m 被标成 `stop_not_near` |
| **本次修改** | 评估距离改为最近 `view_points.agent_state.position` 的水平距离；阈值仍 1.0 m；不喂给规划 / 选目标 / STOP |

**这不是策略提升**：轨迹不变，仅修正评估并重算可比基线。SPL 仍 N/A（无 geodesic）。

## 8 个 stop_not_near 逐例对照

STOP 触发：`exploration_fsm.cpp` 中 `SEARCH_OBJECT` 且底盘距 `next_pos_`（接近点）&lt; `REACH_DISTANCE`0.20（或 stuck 时 soft 0.45）→ `REACH_OBJECT` → `ACTION::STOP`。  
`dtg`：eval-only；参考底盘 xz；POINT=物体中心，VIEW_POINTS=最近 viewpoint。

| episode | 目标 | 接近点→中心 | 接近点→VP | dtg POINT | dtg VP | STOP 时 | ObjectHold@REACH | Hold 基线 | 归类 |
|---------|------|-------------|-----------|-----------|--------|---------|----------------|-----------|------|
| yr17_plant_0 | plant | 4.44 | 5.42 | 4.46 | 5.44 | SEARCH_BEST | 否 | explore_no_goal | 错误物体 |
| lt9_sofa_4 | sofa | 5.91 | 3.54 | 5.92 | 3.55 | SEARCH_BEST | 否 | explore_no_goal | 错误物体 |
| **k1cup_sofa_0** | sofa | 1.18 | **0.02** | 1.25 | **0.02** | SEARCH_BEST | 否 | explore_no_goal | **评估口径** |
| **k1cup_chair_0** | chair | 1.66 | **0.17** | 1.74 | **0.24** | SEARCH_BEST | 是 | stop_not_near | **评估口径** |
| k1cup_sofa_1 | sofa | 8.07 | 6.03 | 8.11 | 6.06 | SEARCH_BEST | 是 | explore_no_goal | 错误实例 |
| dd4b_chair_5 | chair | 4.87 | 3.57 | 4.90 | 3.60 | SEARCH_BEST | 否 | stop_not_near | 错误物体 |
| dd4b_toilet_0 | toilet | 4.57 | 3.67 | 4.57 | 3.67 | SEARCH_EXTREME | 否 | stop_not_near | 近义/EXTREME（无 label=0） |
| **dd4b_bed_1** | bed | 1.75 | **0.05** | 1.77 | **0.01** | SEARCH_BEST | 否 | stop_not_near | **评估口径** |

底盘→接近点均 ≈0.02–0.09 m（STOP 相对接近点正确）。坐标转换（hab→ros）与 POINT dtg 自洽；**非**相机/底盘参考系算错。

归类计数（8）：评估口径 **3**；错误物体/实例 **4**；EXTREME 近义 **1**。

## 「24/24 有效候选」澄清

`sum_ndet>0` 只表示 `get_object()` 返回过至少一个 mask（含 **llm similar_answer** 近义类）。  
`label_indices`：`0`=目标短语；`>0`=similar 列表中的辅助类（**不等于**「目标同义词升级」）。

| 口径 | 数量 |
|------|------|
| 任意检测 ndet>0 | 24/24 |
| 出现过目标类簇 label=0 | **16/24** |
| 仅非零簇 / 无 label=0 | **8/24**（多为 tv / 部分 plant/sofa/toilet） |
| SEARCH_BEST（确认目标后接近） | **13/24**（且均有 label=0） |
| 任一类 SEARCH（含 EXTREME/OVER_DEPTH） | 16/24 |

SEARCH 统计口径：成功接近以 **SEARCH_BEST_OBJECT** 为准；勿与 SEARCH_EXTREME 混用。

## 最小修复

`adapters/habitat_rangercr10/src/apexnav_real_episode.py`：`goal_distance(..., distance_to="VIEW_POINTS")`；summary 增加 POINT 诊断字段。

## 同清单结果（离线重算，轨迹不变）

| 指标 | LabelMap 记录(POINT) | LabelMap 重算(VIEW_POINTS) | Hold 重算(VP) |
|------|----------------------|----------------------------|---------------|
| SR_proxy | 5/24 | **8/24** | 6/24 |
| stop_not_near | 8 | **5** | — |
| explore_no_goal | 11 | 11 | — |
| label0 出现 | 16 | 16 | — |
| SEARCH_BEST | 13 | 13 | — |
| 原 POINT 成功 5 | — | **全部保留** | — |

VIEW_POINTS 下 **新增成功**（原 stop_not_near）：`k1cup_sofa_0`、`k1cup_chair_0`、`dd4b_bed_1`。  
无回归。步数/耗时不变（未重跑策略）。

证据：`stop_near_viewpoint_20261109/recompute_viewpoint_sr.json`、`stop_not_near_cases.json`。

## 下一项

仍失败的 5 个 stop_not_near：错误物体/实例（4）与 EXTREME 无 label=0（1）。与「有检不 SEARCH_BEST」的 synonym-only 簇分轨处理；勿再改评估阈值或扩 F0。
