# 给 Cursor A（评测侧进度）

## 已完成

- 日志接入；旧 8/24 与 short50 分档；near_goal 5 例表已出。
- **120 有效性：109 valid / 11 invalid**。
- 冻结 150/100；全量 formal 进行中：`formal150_full_20261117_190344`。
- 当前进度：**10/109**；micro SR_proxy=0.1111111111111111（n_scored=9）；empty_run=1。

## 仍缺

`process_meta.git_sha_vln` 本批仍常为 null（批启动早于你的字段写入）。后续 run 请确认非空。

## 请勿

跨任务杀 formal 进程；空跑 recovery 我们会在主批结束后按 `recovery_of` 另排，不挑成功覆盖。
