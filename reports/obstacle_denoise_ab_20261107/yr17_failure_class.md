# yr17_chair_0 失败归类（基线 A：expand0.3 / denoise=none）

证据：`e2e_sp_smoke_exp03_20261107_164251_initial_footprint_yr17_chair_0`

| 问题 | 结论 |
|------|------|
| 是否看见/识别到目标？ | **部分是**：native_diag 出现 **6× `SEARCH_BEST_OBJECT`**（`stop_reason=object_path_ok`），说明进入目标搜索并规划到物体路径 |
| 是否选中目标导航点？ | **是**（上述 SEARCH_BEST_OBJECT）；底盘从 ≈(6.45,10.19) 移到 ≈(7.15,10.40) |
| 是否打转/反复？ | **有转圈迹象**：最长连续转向 13 步；探索 100 步中 TURN 59 / FORWARD 41 |
| 失败环节 | **接近未完成 → 退回探索 → 预算耗尽**。无 STOP；最终 dtg≈3.58 m（接近阶段曾≈3.07）。**不是**纯“从未找到”，也**不是**停止判据单独失败 |

median3 冒烟同题仍 `explore_no_goal` 且 dtg 更差（≈7.02）→ 去噪**未改善**该类失败。
