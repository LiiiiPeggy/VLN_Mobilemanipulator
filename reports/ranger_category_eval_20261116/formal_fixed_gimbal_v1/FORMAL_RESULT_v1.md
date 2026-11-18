# Formal independent eval result — fixed_base_gimbal @ 150/100

**Batch:** `formal150_full_20261117_190344`  
**Freeze:** `evaluation/protocols/freeze_protocol_v1.md`  
**List:** `independent_test_list_v1` → validity `109 valid / 11 invalid`（不按成绩筛）

## Headline

| 项 | 值 |
|----|-----|
| 原始清单 | 120 |
| 无效 spawn | 11（整机初始穿透等；见 validity 表） |
| 正式跑 | 109 |
| 可计分 | 108（1× `empty_run` 不计 SR，另排 recovery） |
| **micro SR_proxy** | **0.3056**（33/108） |
| Wilson 95% | [0.227, 0.398] |
| **macro SR_proxy** | **0.3204** |
| near_goal（分列） | 40/109 |
| SPL | N/A |
| camera_mode | `fixed_base_gimbal` ×109；`simulated_gimbal=true` ×109 |

## Per category

| category | success/n | SR_proxy | Wilson95 | near_goal |
|---|---:|---:|---|---:|
| bed | 9/18 | 0.500 | [0.290, 0.710] | 10 |
| chair | 7/13 | 0.538 | [0.291, 0.768] | 10 |
| sofa | 7/19 | 0.368 | [0.191, 0.590] | 7 |
| toilet | 4/19 | 0.211 | [0.085, 0.433] | 5 |
| tv_monitor | 4/20 | 0.200 | [0.081, 0.416] | 5 |
| plant | 2/19 | 0.105 | [0.029, 0.314] | 3 |

## 失败 / 运行记账

| 桶 | 计数 |
|----|-----:|
| wrong_stop | 34 |
| explore_budget_exhausted | 40 |
| no_stop | 1 |
| empty_run | 1（`svBbv1Pavdk_bed_0`；主批争用期） |
| exec_stalled | 0 |
| blocked_exec sum | 3597 |
| truncated_exec sum | 156 |
| mean moved_m | 4.39 |
| mean n_steps | 91.5 |
| mean elapsed_s | 527 |

观测高度 / 遮挡 / 实例歧义：无证据 → **unknown**。未含杯子、未跑主动臂策略。

## 执行器版本（实测，非脚本常量）

本批跨 A 的 v1.1→v1.2 窗口：`kinematic_collision_v1.1`×2 + `v1.2`×107。  
`code_git_sha` / `git_sha_vln` 本批仍为 null（批启动早于字段写入）。预算实测 `process_meta`：150/100。

## 产物路径

- 逐例 JSONL：`batch_formal150_full_20261117_190344.jsonl`
- 类汇总：`summary_formal150_full_20261117_190344.json`
- 完整账本：`accounting_formal150_full_20261117_190344.{json,md}`
- 有效性：`../lists/independent_list_validity_v1_post.json`
- empty_run recovery：`batch_formal150_recovery_empty_20261118c.jsonl`（完成后合并，带 `recovery_of`）
