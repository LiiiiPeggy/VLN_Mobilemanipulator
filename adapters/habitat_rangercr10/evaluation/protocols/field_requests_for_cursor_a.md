# 给 Cursor A 的一次性字段需求（请勿让 B 改核心执行文件）

评测侧只读 `summary.json` / `steps.jsonl` / `native_diag` / `camera_mode.json` /
`initial_penetration.json` / **`process_meta.json`**。

## 已从产物读到（冒烟 + formal）

| 字段 | 来源 | 状态 |
|------|------|------|
| `max_steps` / `max_explore_actions` | `process_meta.json` | ✅ 150/100 |
| `executor_version` | `summary.json` | ✅（formal 前段 `v1.1`；你已推 `v1.2`） |
| `camera_mode` / `simulated_gimbal` | summary + camera_mode.json | ✅ `fixed_base_gimbal` |
| `termination` / init·explore 计数 | summary | ✅ |
| STOP / SEARCH | steps + native_plan_diag（任意 phase） | ✅ |

## 仍缺 / 已知缺口

| 字段 | 说明 |
|------|------|
| `git_sha_vln` / `code_git_sha` | **本 formal 批** `process_meta` 仍为 null（批启动早于你的写入）。你在 `65af40c` 已加字段 — 请确认后续 run 非空。评测**不会**用 batch shell SHA 冒充实测。 |
| `empty_run` | formal `svBbv1Pavdk_bed_0` 出现 `n_steps=0` + cleanup abort（曾与开发批争用 ROS）。评测记 `run_status=empty_run`，需在账本保留；可另排 recovery，勿挑成功覆盖。 |

可选增强（非阻塞）：`dtg_min`、`sum_moved_m`、`n_blocked_recovery`（v1.2）— 评测可从 steps 推导或读 summary。

## 不要做的

- 不要让评测脚本改 `kinematic_demo.py` / `apexnav_real_episode.py`。
- 不要把 missing 字段在外壳 jsonl 填成 false/0。
- 不要按 SR 删 episode；不要跨任务杀 formal。
