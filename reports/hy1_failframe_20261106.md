# HY1 规划失败帧诊断（只诊断，未改 0.25 m 豁免）

日期：2026-11-06  
代码：`ef70acd` + 本提交观察计数（near-start exemption observe-only）  
环视 30° / 膨胀 / unknown / A* 行为未改。

## A. 经典失败（旧产物，保留）

Run：`real_s070_pporaise_hy1_groundfree_20261106_172428`  
（naive AGL[0,0.28] free-ray，地面几何门控之前）

| plan_seq | result | start_raw | reachable | path_len | 推断 |
|----------|--------|-----------|-----------|----------|------|
| 1–3 | EXPLORATION | **UNKNOWN(0)** | 2 | 0.74 / 0.74 / 0.27 | 起点 unsafe 仍成功 → **依赖 0.25 m near-start 安全跳过** |
| **4** | **NO_PASSABLE_FRONTIER** | **UNKNOWN(0)** | **0** | 0 | 25 次候选全失败；reject 聚合 **unknown=4910**（inflate/occ=0） |

失败帧归因：**底盘起点持续 UNKNOWN + 周围 free 不足**，候选路径被 unknown 阻断；非膨胀主因。  
前 3 次成功路径长度 ≤0.74 m，且起点 UNKNOWN，**必然依赖** A* 对 `||nbr−start||≤0.25` 跳过 `checkPointSafety`（未改该豁免；旧日志无 counterfactual 计数，属逻辑推断）。

## B. 门控后复现（新跑）

Run：`real_s070_pporaise_hy1_failframe_20261106_181431`  
（`ground_free_max_agl=0.03` + 平面门控 + local_update 合并 + exemption 观察计数）

证据：`reports/hy1_failframe_20261106/`（`plan_summaries.json`、`plan_seq_*_local_map.png`）  
完整：`.../apexnav_real/<run>/native_diag/{native_plan_diag.jsonl,plan_seq_*_local_map.json,map_pipeline_diag.jsonl}`

### 每次规划（摘录）

| plan_seq | start_raw | free@0.3 | relied_exemption | result | 备注 |
|----------|-----------|----------|------------------|--------|------|
| 1–6 | UNKNOWN | 51 | **1** | EXPLORATION | counterfactual：路径依赖 0.25 m 豁免 |
| 8+ | 多为 FREE | ~98–111 | 0 | EXPLORATION | 底盘邻域 free 已建立 |
| 23–26 | FREE | ≥109 | 0 | EXPLORATION | 探索阶段仍能出路径 |

探索动作：FWD×2、TURN_LEFT×2 后 **`planner_action_timeout`**（90 s 无 `/habitat/plan_action`）；exploration.log 有 `Escaping stuck...`。  
**未再出现** 第 4 次 `NO_PASSABLE_FRONTIER`。

### 与经典失败的关系

1. 经典第 4 次失败：**地面覆盖不足 → 起点 UNKNOWN → unknown 阻断**（证据充分）。  
2. 几何门控后：起点可变为 FREE，经典 NO_PASSABLE **不再同条件复现**；当前中断是 **FSM stuck / action timeout**，需另归因（疑与低矮障碍 OCCUPIED→膨胀/脱困有关，**待验证**，本阶段不改姿态）。  
3. 明确记录：前若干次（门控后 plan 1–6）成功路径 **`any_success_path_relied_near_start_exemption=1`**；豁免逻辑未改。

## C. 是否进入「朝底盘侧补视」

条件：地图更新正确性已过；HY1 **经典**失败可归因覆盖不足。  
**但**门控后主失败形态已变，补视实验 **暂缓**，避免与 stuck/timeout 混因。

## D. 本提交代码（观察 only）

- `AstarRejectStats`：`near_start_skip_*` / `path_relied_near_start_exemption`（不改变 0.25 m 跳过）  
- `flushPlanDiag`：rings、selected_path、`plan_seq_*_local_map.json`
