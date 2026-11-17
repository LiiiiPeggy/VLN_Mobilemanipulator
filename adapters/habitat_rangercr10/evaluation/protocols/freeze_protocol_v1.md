# 冻结协议 v1 — ApexNav / fixed_base_gimbal 独立评测

日期：2026-11-17  
执行基线 commit：**bb89842**（`kinematic_collision_v1.1` + `fixed_base_gimbal`）  
评测体系起点：ff00dd5；本轮评测代码接在 evaluation/ 下。

## 冻结项

| 项 | 值 |
|----|-----|
| `camera_mode` | `fixed_base_gimbal`（记录 `simulated_gimbal=true`） |
| `robot_scale` | `0.7` / `scaled_robot_proxy_070`（非真实尺寸实机） |
| `executor_version` | 以 **summary.json 实测**为准（期望 `kinematic_collision_v1.1`） |
| `code_git_sha` | 以 run 产物为准（见字段需求；禁止仅用脚本常量冒充） |
| 清单 | `independent_test_list_v1.json` + 有效性表（valid 子集跑正式） |
| 开发回归 | `dev24` 仅回归，不并入正式 micro |
| 建议预算 | `MAX_STEPS=150`，`MAX_EXPLORE_ACTIONS=100`（与开发协议对齐；**以实际写入 run 的配置为准**） |
| 成功 | `SR_proxy` = 存在真实 STOP 动作且该刻 VIEW_POINTS 距 ≤ 1.0 m |
| SPL | N/A |
| 杯子 / 主动臂策略 | **不纳入本轮** |

## 动作计数

- 初始化环视：FSM 约 26 步（`n_init_lookaround`），计入 `n_steps`，与 explore 分列。  
- 失败/阻挡：`exec.blocked` / `truncated` 分列累计。  
- LOOK：在 `fixed_base_gimbal` 下为模拟俯仰，不移动光学中心；记入观测动作。  
- 不得用 `step<26` 猜测阶段；以 `phase` / 动作名为准。

## 批次归档（不得混算）

1. `hist_labelmap_vp_8of24` — 旧诊断；不可作新协议失败主因。  
2. `short50_fixed_base_gimbal` — MAX_STEPS≈50 短预算；含 recovery 合并。  
3. 正式 `independent_v1 @150/100` — 冻结后另档。

## 运行规则

- 无效 spawn / 超时 / 崩溃分账，不静默丢弃。  
- recovery 必须关联原 `episode_list_id`，禁止挑成功覆盖。  
- 正式结果不回头调参；要改策略则回开发集并升实验版本。  
- 与 A 共享 GPU/ROS：排队；禁止跨任务杀进程。
