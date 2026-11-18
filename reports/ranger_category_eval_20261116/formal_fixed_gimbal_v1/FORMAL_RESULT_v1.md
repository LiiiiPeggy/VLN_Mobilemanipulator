# Formal independent eval result — fixed_base_gimbal @ 150/100

**Primary batch:** `formal150_full_20261117_190344`  
**Recovery:** `formal150_recovery_empty_20261118c`（`svBbv1Pavdk_bed_0`，`recovery_of` 关联）  
**Scored merge:** `batch_formal150_full_plus_recovery.jsonl`  
**Freeze:** `evaluation/protocols/freeze_protocol_v1.md`  
**List:** 120 → **109 valid / 11 invalid**（不按成绩筛，不强凑）

## Headline（含 recovery 合并后）

| 项 | 值 |
|----|-----|
| 原始清单 | 120 |
| 无效 spawn | 11 |
| 正式+recovery 计分 | **109/109** |
| **micro SR_proxy** | **0.3028**（33/109） |
| Wilson 95% | [0.224, 0.395] |
| **macro SR_proxy** | **0.3161** |
| near_goal（分列，≠SR） | 40/109 |
| SPL | N/A |
| camera_mode | `fixed_base_gimbal` ×109；`simulated_gimbal=true` |

主批 alone（recovery 前）：micro **0.3056**（33/108）；1×empty_run 曾不计分。

## Per category（合并后）

| category | success/n | SR_proxy | Wilson95 | near_goal |
|---|---:|---:|---|---:|
| bed | 9/19 | 0.474 | [0.273, 0.683] | 10 |
| chair | 7/13 | 0.538 | [0.291, 0.768] | 10 |
| sofa | 7/19 | 0.368 | [0.191, 0.590] | 7 |
| toilet | 4/19 | 0.211 | [0.085, 0.433] | 5 |
| tv_monitor | 4/20 | 0.200 | [0.081, 0.416] | 5 |
| plant | 2/19 | 0.105 | [0.029, 0.314] | 3 |

## 失败 / 运行记账

| 桶 | 计数 |
|----|-----:|
| wrong_stop | 34 |
| explore_budget_exhausted | 41 |
| no_stop | 1 |
| empty_run（合并后） | 0（原条目保留在主批 jsonl；计分用 recovery） |
| exec_stalled | 0 |
| blocked_exec sum | 3703 |
| truncated_exec sum | 160 |
| mean moved_m | 4.35 |
| mean n_steps | 92.7 |
| mean elapsed_s | 534 |

观测高度 / 遮挡 / 实例歧义：无证据 → **unknown**。未含杯子、未跑主动臂。

## 执行器 / 配置（实测）

- executor：主批跨 v1.1→v1.2；合并后约 `v1.1`×1 + `v1.2`×108  
- 预算：`process_meta` 实测 150/100  
- `code_git_sha`：本批仍 null（启动早于 A 写入）

## 产物

- 主批逐例：`batch_formal150_full_20261117_190344.jsonl`（含原始 empty_run）
- 计分合并：`batch_formal150_full_plus_recovery.jsonl`
- 账本：`accounting_formal150_full_plus_recovery.{json,md}`
- 有效性：`../lists/independent_list_validity_v1_post.json`
- merge 日志：`merge_recovery_log.json`
