# PROGRESS.md — 当前状态

更新时间：2026-11-17（Ranger 穿模修复 + fixed_base_gimbal 部署基线）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Ranger 部署基线升级为 **`kinematic_collision_v1.1` + `camera_mode=fixed_base_gimbal`**（0.7× proxy）；F0/Hold/LabelMap 算法变量仍冻结。原生 ApexNav 1000-ep 已完成。

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
| SG-Nav 20ep 未收尾（18/20 停；容器 not running） | `smoke_status.md`；`vln-sgnav` | 用自算 navmesh 冒充官方 SPL |
| UniGoal 仅弱 smoke，无 IIN 论文规模 | `smoke_1ep_status.md` | 跳级宣称 BATCH_OK |
| MSGNav 论文对照需 gpt-4o；当前无密钥 | `gpt4o_20ep_status.md` | 用 luna 数字直接对标论文 |
| Ranger 真 stop_not_near / synonym-only | `stop_near_viewpoint_20261109` | 扩成功半径 / 改 F0 掩盖 |
| SPL **N/A**（Ranger） | 无 geodesic | 欧氏冒充 SPL |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| F0+expand0.3 / denoise=none / ObjectHold / LabelMap | **冻结** | 既有报告 |
| 执行碰撞门控 | **`kinematic_collision_v1.1`** | `execution_collision.py`；单测 all_ok |
| 相机模式 | **`fixed_base_gimbal`（simulated_gimbal）** | `camera_modes.py`；LOOK 不移光心 |
| robot_scale | **0.7** `scaled_robot_proxy_070` | 组会主对照 |
| SR_proxy dtg 参考 | **VIEW_POINTS**（阈值仍 1.0 m） | `apexnav_real_episode.goal_distance` |
| 新协议 24-ep | **SR_proxy 0/24**；near_goal 5；不可与旧 8/24 归因对比 | `reports/exec_collision_gimbal_20261116` |

## ApexNav 论文复现（HM3D-v2）

| 项 | 状态 | 证据 |
|----|------|------|
| 全量 1000-ep | **完成** | `.../hm3dv2_full_20261109_231528`；~13.1 h |
| SR / SPL | **74.4% / 37.65%**（论文 76.2 / 38.0） | log + `summary.json` |
| 失败主因 | **false positive 144（占失败 56%）** | `live_failures.md` |
| 报告 | 已写 | `reports/apexnav_hm3dv2_full_repro.md` |

## SG-Nav / UniGoal（旁路）

| 项 | 状态 | 证据 |
|----|------|------|
| 官方 `mp3d_habitat` 资产 + `.navmesh` | **已装** val 11 景 | `scene_datasets/mp3d/`；自算 navmesh **已删** |
| SG-Nav 20ep（官方 navmesh） | **18/20 中断**；18ep 均值 SR=0.50 / SPL≈0.131 | `runs/SG-Nav/smoke_status.md` |
| VLM/LLM | model8 `gpt-5.6-luna`；`image_url={"url":data:…}`；soft-fail | `scenegraph.py`；超时仍多 |
| UniGoal | 1ep 弱 smoke；未继续批量 | `runs/UniGoal/smoke_1ep_status.md` |

## 下一步（最多 5）

1. Cursor B：用冻结提交跑评测清单；对照 `exec` 字段（requested/actual/blocked/collision）。  
2. 诊断高 blocked 转向（lt9/k1cup/yr17）：真障碍 vs 分类过严；**禁止**关碰撞凑 SR。  
3. Ranger：真 stop_not_near / synonym-only；勿改 F0/Hold/映射/评估半径。  
4. 合并前确认不污染 1.0× 默认路径与 `legacy_arm_look` 复核入口。  
5. SG-Nav/UniGoal 旁路按原计划收尾。
