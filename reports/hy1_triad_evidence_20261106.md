# HY1 三次运行并列证据 + 豁免计数修正 + 原生 C++ 回放

基线起点：`63edb4b`。本提交完善证据与观察计数；**三次历史运行互不覆盖**。

## 1. 三次运行并列（同 spawn 力回放）

| 项 | `…181334` | `…181431` | short3 `…182146` |
|----|-----------|-----------|------------------|
| 退出 | `explore_budget_exhausted` | `planner_action_timeout` | `planner_stop` |
| 探索 | 20 | 4 | 1×STOP |
| pipeline 深度帧 | **37** | **160** | **62** |
| plan_diag 条数 | **0**（缺失） | 26 | 1 |
| ≤首规划 stamp 的深度帧 | 37（无 plan 戳） | **128** | **57** |
| 首规划 | （无 diag） | EXPLORATION，raw UNKNOWN，free@0.3=51 | **NO_PASSABLE**，free@0.3=**0** |
| 代码窗（推断） | post-`ef70acd` / 与 181431 并发 | `813827c` 仪器 | `63edb4b` short3 |

共同配置：scene `HY1NcmCgn3n` ep3、force_spawn=`real_wide_hy1_openband_…113724`、0.7×、legacy018、30°、`ground_free_max_agl=0.03`。  
**seed**：仅 episode+force_spawn；`process_meta` 当时未记 RNG/git（缺口，后续复测补齐）。

动作序列与完整字段：`triad_runs.json`、`*_actions.json`。  
**结论**：三次结果不可合并；首规划前观测帧数差异巨大（37/128/57），是重复性差的首要嫌疑。

旧豁免字段 `path_relied_near_start_exemption` 在 181431 上可能因「起点 UNKNOWN」假阳性；**本提交已修正**，历史数不回溯改写。

## 2. 豁免观察计数修正

- 静默安全检查 `checkPointSafetySilent` / `edgeWouldFailSafetySilent`：**不**写入 occupied/inflate/unknown 拒绝计数。  
- `path_relied_*`：仅统计选中路径上 **终点落入 0.25 m 豁免球** 的边，并对边终点+中间采样做反事实；**不**因起点 UNKNOWN 单独置位。  
- 新增 `path_exempted_edges` / `path_exempted_edges_would_fail`。

## 3. 原生 C++ 生产链路回放（≠ Python 模型测）

可执行文件：`rosrun plan_env test_map_pipeline_replay`（`libplan_env.so`）。  
日志：`native_pipeline_replay.txt` → **ALL_PASS**

| 验证 | 含义 |
|------|------|
| 同帧 merge+inflate | 障碍在地面盒外仍 OCC+inflate |
| 低矮障碍保留 | 作为 depth OCC 云注入的 5/10/20 cm 带终点，经 free-ray 后仍 OCCUPIED |

Python：`test_local_update_merge.py` / `test_ground_free_geometry.py` = **模型/判据**；本回放 = **生产库**。
