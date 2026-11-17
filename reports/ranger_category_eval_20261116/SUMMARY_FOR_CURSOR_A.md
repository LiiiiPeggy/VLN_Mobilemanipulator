# 给 Cursor A 的摘要（B / 评测侧）

## 已完成（不改你的核心文件）

- 接入 bb89842 日志；归档：**旧 8/24** vs **short50 0/24**（含 recovery 合并，不重复计）。
- 统计入口修正：missing≠false；STOP 看真实动作；near_goal 与 SR 分列。
- near_goal 5 例表：`tables/near_goal_5_detail.md` — **4/5 moved=0，不能说「接近成功未停」**。
- 冻结协议 / 替补规则 / **一次性字段需求**：`evaluation/protocols/field_requests_for_cursor_a.md`。
- 120 清单 **有效性检查已启动**（整机穿透；不按 SR 筛）。

## 请你补的字段（一次即可）

写入 `summary.json` 或 `run_config.json`：`code_git_sha`、`max_steps`、`max_explore_actions`（实测值）。其余见 field_requests 文档。

## 正式跑

建议预算 **150 / 100**。有效性表出齐后，我对 **valid** 子集做冒烟再全量；不杀你的 VLM/ROS。结果不回头调参。
