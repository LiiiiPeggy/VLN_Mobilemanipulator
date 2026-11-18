# PROGRESS.md — 当前状态

更新时间：2026-11-18（桌边视点 C 采集 12 对交付 D；formal 仍排队）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Ranger 执行收口 **`kinematic_collision_v1.2` + `fixed_base_gimbal`**；**桌边小物体配对采集（Cursor C）已交付**；协议预算 150/100 仍排队。

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

## 桌边视点 pilot（Cursor C 采集）

| 项 | 状态 | 证据 |
|----|------|------|
| 实例锁定 | **12**（cup/bowl/remote/bottle ×≤3） | `reports/tabletop_views_pilot/capture/locked_instances.md` |
| 配对采集 | **12/12**；可靠 GT **9/12** | `CAPTURE_REPORT.md`；D 盘 `.../tabletop_views_pilot/captures/` |
| 接口 | `fixed_base_gimbal` + `arm_ee`≡`arm_view`；3 视点含共用 init | `CAPTURE_LAYOUT.md`；`handoff_to_D_first_pair.json` |
| 首对 | `CrMo8WxCyVb_cup_423` | init MAE≈0；base 未动 |
| 不可靠 3 对 | q5 bottle/remote、wcoj bottle | `reliable_gt=false`（spawn 后全程无目标像素） |
| 脚本 | `adapters/.../experiments/tabletop_views/` | catalog→verify→capture→finalize |

## 下一步（最多 5）

1. Cursor D 按 `pairing_index.json` 跑检测汇总（C 采集已齐）。  
2. 等 B formal 结束后跑 budget150 diag → smoke → **dev24@150/100**。  
3. 可选：对 3 个 `reliable_gt=false` 对加密 spawn 短名单再采。  
4. 合并前确认不污染 1.0× 默认与 `legacy_arm_look`。  
5. SG-Nav/UniGoal 旁路按原计划收尾。
