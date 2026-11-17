# 冻结协议 v1 — ApexNav / fixed_base_gimbal 独立评测

日期：2026-11-17  
评测体系起点：`ff00dd5`；本轮评测代码在 `evaluation/`。

## 冻结项（本轮正式批）

| 项 | 值 |
|----|-----|
| 正式批 ID | `formal150_full_20261117_190344` |
| 清单 | `independent_test_list_v1.json`（120） |
| 有效性 | `lists/independent_list_validity_v1*.json`：**109 valid / 11 invalid**（不强凑 120） |
| `camera_mode` | `fixed_base_gimbal`（`simulated_gimbal=true`） |
| `robot_scale` | `0.7` / `scaled_robot_proxy_070`（非真实尺寸实机） |
| 预算 | `MAX_STEPS=150`，`MAX_EXPLORE_ACTIONS=100`（以 **process_meta / summary 实测**为准） |
| 成功 | `SR_proxy` = **任意 phase** 存在 STOP 且该刻 VIEW_POINTS ≤ 1.0 m |
| `near_goal` | 仅诊断；**不是**成功；`moved_m=0` 不得称「成功接近」 |
| SPL | **N/A** |
| 杯子 / 主动臂 | **不纳入** |

### 执行版本说明

- 有效性检查与正式批启动时对齐 **`bb89842` / `kinematic_collision_v1.1`**。
- Cursor A 随后交付 **`65af40c` / `kinematic_collision_v1.2`**（阻挡证据 + 受阻反馈）。工作区挂载会导致 formal **中后段** episode 可能读到 v1.2。
- **逐例**以该 run 的 `summary.executor_version` 与 `process_meta.git_sha_vln` 记账；禁止只用外壳常量。
- 若需「纯 v1.2」对照，另开实验版本（不回头改本冻结批结论）。

## 动作计数

- 初始化环视：FSM ≈26 步，计入 `n_steps`，与 explore 分列。  
- 失败/阻挡：`exec.blocked` / `truncated` 分列；A v1.2 另有 `n_blocked_recovery`。  
- LOOK（gimbal）：观测动作，不移动光学中心。  
- STOP 判定 **不**依赖 `step<26` / `phase==explore_planner`。

## 批次归档（不得混算）

1. `hist_labelmap_vp_8of24` — 旧诊断；**不可**作新协议失败主因（含 tv/plant）。  
2. `short50_fixed_base_gimbal` — MAX_STEPS≈50；含 recovery 合并。  
3. `formal_independent_v1 @150/100` — 本冻结正式档。

## 运行规则

- 无效 spawn / 超时 / 崩溃 / `empty_run` 分账，不静默丢弃。  
- recovery 关联 `episode_list_id`，禁止挑成功覆盖。  
- 正式结果不回头调参；改策略 → 开发集 + 升实验版本。  
- 与 A 共享 GPU/ROS：排队；**禁止跨任务杀进程**。
