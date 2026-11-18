# PROGRESS.md — 当前状态

更新时间：2026-11-18（导航 P0/P1/P2 离线对照完成；短跑/dev24 待 GPU）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Ranger 执行收口 **`kinematic_collision_v1.2` + `fixed_base_gimbal`**；短预算 50 已归档；协议预算 150/100 的 diag→smoke→dev24 **排队**等 Cursor B formal 释放共享 ROS/GPU。

## Baseline 状态一览

| Baseline | 状态 | 要点 / 证据 |
|----------|------|-------------|
| ApexNav | **BATCH_OK** + HM3D-v2 **1000-ep 完成** | SR 74.4 / SPL 37.65；`reports/apexnav_hm3dv2_full_repro.md` |
| VLFM | **BATCH_OK**（另有 full-val 脚本/状态） | `runs/VLFM/batch_8ep_status.md`；`full_val_status.md` |
| MSGNav | **BATCH_OK**；luna **20ep 完成**；gpt-4o **BLOCKED** | luna：`runs/MSGNav/luna_20ep_status.md`；gpt-4o 无密钥暂停 |
| SG-Nav | **SINGLE_EPISODE_OK**；官方 navmesh **18/20 中断**（非论文复现） | `runs/SG-Nav/smoke_status.md`；STAMP `20261109_230909`；容器曾 exit |
| UniGoal | **SINGLE_EPISODE_OK（弱）**；未开批量 | `runs/UniGoal/smoke_1ep_status.md`；`luna_smoke120/` |
| APRR | 环境/子模块未齐 | — |

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| 协议预算 150/100 diag/dev24 未跑完（共享容器被 B formal 占用） | `budget_ab150/queue_*`；formal pid | 对 formal 进程 pkill |
| short50：4 invalid spawn + 10 zero-trans stall | `short50_corrected_stop_accounting.json` | 关碰撞 / 扩容忍放行穿透 spawn |
| SG-Nav 20ep 未收尾；UniGoal 弱 smoke；MSGNav 无 gpt-4o | 各 status | 跳级宣称 |
| Ranger SPL **N/A** | 无 geodesic | 欧氏冒充 SPL |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| F0+expand0.3 / denoise=none / ObjectHold / LabelMap | **冻结** | 既有报告 |
| 执行碰撞门控 | **`kinematic_collision_v1.2`**（first_blocking 证据；upright 轮地） | `9399dee` |
| 受阻反馈 | 连续 3× 同动作全拒 → LOOK/反向转（计预算） | `6745243` |
| 批入口 | any-phase STOP；短/协议预算标签；formal lock | `cef07d7` |
| 相机模式 | **`fixed_base_gimbal`（simulated_gimbal）** | `camera_modes.py` |
| robot_scale | **0.7** `scaled_robot_proxy_070` | 组会主对照 |
| short50 24-ep | SR_proxy **0/24**；near_goal 5；blocked 681 | `SHORT_BUDGET_50.md` |
| 部分 150 对照 | `ef36_bed_4`：25 步 init 内 STOP，dtg≈0.04，batch 曾漏计 STOP | `batch_budget150_diag_20261117_190941.jsonl` |
| B 字段样例 | 已写 | `CURSOR_B_HANDOFF_FIELDS_v12.json` |

## ApexNav 论文复现（HM3D-v2）

| 项 | 状态 | 证据 |
|----|------|------|
| 全量 1000-ep | **完成** | `.../hm3dv2_full_20261109_231528`；~13.1 h |
| SR / SPL | **74.4% / 37.65%**（论文 76.2 / 38.0） | log + `summary.json` |

## 桌边视点 pilot（固定云台 vs 臂载）

| 项 | 状态 | 证据 |
|----|------|------|
| 离线 `get_object` + IoU≥0.5 实例匹配 | **入口就绪** | `adapters/.../tabletop_views/`；`cab7213` |
| 合成夹具冒烟 | 管线 OK（非真实结论） | `reports/tabletop_views_pilot/evaluation/` |
| A 实例目录 | 134 候选（cup15/bowl40/remote14/bottle65） | `capture/instance_catalog.json` |
| 真实 RGB+GT 配对 | **等待 A → `captures/`** | watcher 轮询中 |

正式 fixed_gimbal formal150 结果见 `reports/ranger_category_eval_20261116/formal_fixed_gimbal_v1/`（勿与桌边 pilot 混写）。

## 导航规划膨胀 A/B（本轮）

| 项 | 状态 | 证据 |
|----|------|------|
| 分支 | `cursor/nav-inflation-halfwidth-softcost`（自 492f53f） | — |
| lock inflation / soft cost C++ | **已实现并编入** `vln-rangercr10` | `sdf_map2d` + `astar2d` |
| 同图离线 P0/P1/P2 | **完成** | `reports/nav_inflation_softcost_20261118/` |
| 推荐（离线半宽） | P1/P2 半宽有效但易堵窄通道 | `RECOMMENDATION.md` |
| 当前短跑候选 | **`inf020_soft010`：硬 0.20 m + 软 R=0.10 / w=2.0** | overlay + `run_apexnav_real_episode.sh` |
| 短跑 / 候选 dev24 | **未跑**（GPU≈40GB + queue_after_formal） | 待空闲 |

## 下一步（最多 5）

1. GPU 空闲后：同起点短跑 P0 vs `inf020_soft010`（硬0.20+软R=0.10）→ 候选跑一次匹配 formal 的 dev24。  
2. 若规划已离障而 traj 仍贴边：查跟踪/执行，不继续加大膨胀。  
3. formal150 独立列表后续 ObjectNav 以 formal 报告为准。  
4. 合并前确认不污染 1.0× 默认与 `legacy_arm_look`。  
5. 桌边 pilot / SG-Nav 旁路按原计划。
