# 独立评测交付索引（Cursor B）

冻结批：`formal150_full_20261117_190344` · 相机 `fixed_base_gimbal` · 预算 150/100

## 1. 日志适配与校验

| 产物 | 路径 |
|------|------|
| ingest（null-safe，任意 phase STOP） | `adapters/habitat_rangercr10/evaluation/scripts/ingest_episode_run.py` |
| 分档归档脚本 | `evaluation/scripts/archive_and_aggregate_batches.py` |
| 字段需求（一次性） | `evaluation/protocols/field_requests_for_cursor_a.md` |
| 历史档 | `archives/00_hist_labelmap_vp_8of24.json` |
| 短预算档 | `archives/01_short50_exec_gimbal.json` |
| short50 记账 | `tables/short50_accounting.json` / `short50_by_category.md` |
| near_goal 5 例 | `tables/near_goal_5_detail.md`（4/5 moved=0） |

## 2. 120 清单有效性

| 产物 | 路径 |
|------|------|
| 原始清单 | `evaluation/lists/independent_test_list_v1.json` |
| 有效性表 | `lists/independent_list_validity_v1.json` + `.md` |
| 计数 | **109 valid / 11 invalid / 0 pending**（不强凑） |
| 替补策略 | `evaluation/protocols/replacement_policy_v1.md`（本轮未替补） |

## 3. 冻结协议

`evaluation/protocols/freeze_protocol_v1.md`

## 4. 正式运行与结账

| 产物 | 路径 |
|------|------|
| 启动器 | `evaluation/scripts/run_formal_independent_eval.sh` |
| 进度 | `formal_fixed_gimbal_v1/progress_*.md` |
| 逐例 JSONL | `formal_fixed_gimbal_v1/batch_formal150_full_20261117_190344.jsonl` |
| 结账（完成后） | `formal_fixed_gimbal_v1/accounting_*.json/.md` |
| 自动结账 | `formal_fixed_gimbal_v1/finalize_when_done.sh` |

## 5. 已知异常

- `svBbv1Pavdk_bed_0`：`empty_run`（n_steps=0，曾与 A 开发批争用 ROS）— 入账，可事后 recovery。
- formal 启动于 A 的 v1.2 交付前；逐例记录 `executor_version`（可能混有 v1.1/v1.2）。
