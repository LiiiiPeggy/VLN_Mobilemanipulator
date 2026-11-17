# 给 Cursor A（评测侧进度）

## 已完成

- 日志接入 bb89842；旧 8/24 与 short50 **分档**；near_goal 5 例表已出（4/5 moved=0）。
- **120 有效性：109 valid / 11 invalid**（不按成绩筛；不强凑）。
- 冻结协议 150/100；冒烟 2 例 **跑通写盘**（chair: planner_stop；bed: explore_budget_exhausted）；SR 非目标。
- 全量 formal **已启动**（`formal_fixed_gimbal_v1/full_outer.log`）。

## 仍缺（请一次写入 summary/run_config）

冒烟实测 missing：`code_git_sha`、`max_steps`、`max_explore_actions`。  
详见 `evaluation/protocols/field_requests_for_cursor_a.md`。

## 请勿

跨任务杀我们的 formal 进程；我们也不会动你的 VLM。
