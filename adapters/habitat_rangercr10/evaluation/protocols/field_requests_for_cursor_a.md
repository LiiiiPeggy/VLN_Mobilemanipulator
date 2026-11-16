# 给 Cursor A 的日志 / 接口字段需求（短清单）

评测侧 **不**改 `kinematic_demo.py` / `apexnav_real_episode.py` / 传感器发布。缺字段时由 A 接入。

## 必须（ApexNav 基线 A 可汇总）

| 字段 | 类型 | 说明 |
|------|------|------|
| `episode_list_id` | str | 与清单 `id` 一致 |
| `scene` / `category` / `episode_id` | str | |
| `robot_scale` / `scale_tag` | float/str | 须含 `0.7` / `scaled_robot_proxy_070` |
| `camera_mode` | str | 建议枚举：`fixed_gimbal`（A）/ `rule_arm_obs`（B）/ `active_arm_obs`（C） |
| `code_git_sha` / `config_id` | str | 冻结版本 |
| `spawn_status` | str | `ok` / `invalid` / `skipped` |
| `run_status` | str | `ok` / `timeout` / `crash` / `abort` |
| `termination` | str | 含 `planner_stop` 等 |
| `dtg_viewpoint` | float | VIEW_POINTS 水平距 |
| `sr_proxy` | bool | `planner_stop ∧ dtg_viewpoint≤1.0` |
| `fail_bucket` 或可推导字段 | str | 至少能区分 wrong_stop / no_search_best / other |
| `n_steps` / `elapsed_sec` / `forward_m` | num | |
| `n_init_lookaround` / `n_effective_observations` | int | 有效观测次数需有明确定义 |
| `entered_search_best` | bool | |
| `n_arm_motions` / `arm_motion_time_sec` | num | A 可为 0 |
| `exec_collision_or_fault` | bool/str | 碰撞/异常 |

## 可选（观测条件分层；可后标）

`goal_height_bin`, `apparent_scale_bin`, `occlusion_bin`, `multi_instance_ambiguity`, `control_unoccluded`

## 输出约定

每 episode 一份 JSON 或 JSONL 一行，字段稳定即可；评测脚本：`scripts/summarize_category_metrics.py`。
