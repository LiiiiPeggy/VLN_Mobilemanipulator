# 历史 24 例逐类诊断（LabelMap + VIEW_POINTS 重算）

来源：`reports/discovery_label_map_20261108/aggregate_ab24_labelmap_20261108_220204.json` + `reports/stop_near_viewpoint_20261109/recompute_viewpoint_sr.json`。

**免责声明**：历史执行链可能存在穿模 / 足迹与规划不一致；**仅供开发诊断**，不得作为独立测试集基线，也不得称为真实尺寸实机结果（`robot_scale=0.7`）。

成功定义：`SR_proxy` = `planner_stop ∧ dtg(VIEW_POINTS) ≤ 1.0 m`；**不报 SPL**。

| category | n | success | SR_proxy | wrong_stop | no_SEARCH_BEST | other | label0 | SEARCH_BEST |
|----------|---|--------:|---------:|-----------:|---------------:|------:|-------:|------------:|
| bed | 2 | 2 | 1.0 | 0 | 0 | 0 | 2 | 2 |
| chair | 5 | 4 | 0.8 | 1 | 0 | 0 | 5 | 5 |
| plant | 6 | 1 | 0.1667 | 1 | 4 | 0 | 4 | 2 |
| sofa | 4 | 1 | 0.25 | 2 | 1 | 0 | 3 | 3 |
| toilet | 3 | 0 | 0.0 | 1 | 1 | 1 | 1 | 1 |
| tv_monitor | 4 | 0 | 0.0 | 0 | 4 | 0 | 1 | 0 |
| __ALL_micro__ | 24 | 8 | 0.3333 | 5 | 10 | 1 | 16 | 13 |

## 失败桶说明

- `wrong_stop`：已 `planner_stop` 但未到 VIEW_POINTS（含错误物体/实例、近义 EXTREME）。
- `no_search_best`：从未进入 `SEARCH_BEST_OBJECT`（含仅辅助簇 / 探索未确认目标）。
- 分组 `大型家具` / `小物体` 仅用于报告汇总，**不**与子类重复计入总体 micro。

逐例 CSV：`reports/ranger_category_eval_20261116/tables/dev24_per_episode.csv`

