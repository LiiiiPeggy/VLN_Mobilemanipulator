# 给 Cursor A 的一次性字段需求（请勿让 B 改核心执行文件）

评测侧只读 `summary.json` / `steps.jsonl` / `native_diag` / `camera_mode.json` / `initial_penetration.json`。  
下列字段在 **bb89842** 跑出的 short50 批中仍常缺失或只能从外壳脚本猜测——请 A 在写 summary/meta 时补齐。

## 必须写入 run 产物（summary.json 或 run_config.json）

| 字段 | 说明 |
|------|------|
| `code_git_sha` / `git_sha_vln` | 实际检出 SHA（如 bb89842…），**禁止**只在 batch shell 写死 |
| `max_steps` | 本次进程真实 argparse 值 |
| `max_explore_actions` | 同上 |
| `executor_version` | 已有；请保持与 `execution_collision.EXECUTOR_VERSION` 一致 |
| `camera_mode` | 必须能读到 `fixed_base_gimbal` |
| `simulated_gimbal` | bool |
| `n_init_lookaround_actions` / `n_explore_planner_actions` | 已有则保持 |
| `final_distance_to_goal_eval_only` | 已有 |
| `dtg_min`（新）或保证 steps 含全程 dtg | 评测可自算；若 steps 截断请给 min |
| `sum_moved_m`（新，可选） | 否则评测从 `exec.moved_m` 求和；缺 moved_m 时保持 null |
| `termination` | 真实终止语义 |
| `initial_penetration.initial_penetration` | 已有 |
| `status` | ok/timeout/crash/abort |

## STOP / SEARCH

- STOP：继续在 `steps[].exec.action_name=="STOP"` 或 `raw_action==0` 落盘（评测已按此解析，不使用 step&lt;26 猜测）。  
- SEARCH：继续写 `native_diag/native_plan_diag.jsonl` 的 `result`（如 `SEARCH_BEST_OBJECT`）。

## 不要做的

- 不要让评测脚本改 `kinematic_demo.py` / `apexnav_real_episode.py`。  
- 不要把 missing 字段在外壳 jsonl 里填成 false/0 冒充实测。  
- 不要按 SR 删 episode。

## 预算对齐（建议）

正式独立评测：`MAX_STEPS=150`，`MAX_EXPLORE_ACTIONS=100`；写入上述配置字段后评测侧只读实测值。
