# PROGRESS.md — 当前状态

更新时间：2026-11-11（SG-Nav 官方 navmesh 18/20；记忆同步）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：ApexNav HM3D-v2 全量已完成；旁路推进 **SG-Nav**（官方 mp3d_habitat navmesh，20ep 跑到 18 中断）与 **UniGoal**（仅弱 1ep smoke）。Ranger 侧仍冻结 F0/Hold/LabelMap。

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
| SR_proxy dtg 参考 | **VIEW_POINTS**（阈值仍 1.0 m） | `apexnav_real_episode.goal_distance` |
| LabelMap 批重算 | SR 5→**8**/24；原 5 成功保留；+sofa0/chair0/bed1 | `stop_near_viewpoint_20261109` |

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

1. 重启 `vln-sgnav`，收尾 SG-Nav 剩余 ep 或重开完整 20ep（官方 navmesh）。  
2. UniGoal：在 HM3D IIN 上加长步数 / 小批量，再谈论文对照。  
3. MSGNav gpt-4o：有密钥后再开；luna 20ep 仅作替代小批。  
4. Ranger：真 stop_not_near 与 synonym-only 分轨；勿再改 F0/Hold/映射/评估半径。  
5. 合并前确认不污染 1.0× 默认路径。
