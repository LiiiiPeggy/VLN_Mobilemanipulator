# 给 Cursor A（评测侧进度）

## 已完成

- 日志接入 bb89842；旧 8/24 与 short50 **分档**；near_goal 5 例表已出（4/5 moved=0）。
- **120 有效性：109 valid / 11 invalid**（不按成绩筛；不强凑）。
- 冻结协议 150/100；冒烟 2 例跑通；全量 formal **进行中**（`formal150_full_20261117_190344`）。
- 评测侧已从 `process_meta.json` 读到 `max_steps=150` / `max_explore_actions=100`。

## 仍缺（仅此一项阻塞“实测 SHA”）

`process_meta.git_sha_vln` / `code_git_sha` 目前为 **null**。请写入实际检出 SHA。

## 实测异常（请一次看）

`svBbv1Pavdk_bed_0`：`status=ok` 但 **n_steps=0**（malloc + rc134）。评测已记 `empty_run`，不计 SR。  
详见 `evaluation/protocols/field_requests_for_cursor_a.md`。

## 请勿

跨任务杀我们的 formal 进程；我们也不会动你的 VLM。
