# PROGRESS.md — 当前状态

更新时间：2026-11-03（姿态修复 + 论文风 Demo + 正式规划阶段验证）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：三套主线 `BATCH_OK` 保持；原生 URDF + **真实 ApexNav ROS** 闭环已验证至 **初始化环视结束并进入 `callActionPlanner()`**；控制仍为 `kinematic_state_set`；Demo 为 16:9 主视角+语义+在线占据图。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改；apexnav 仍 nobullet |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂适配

| 项 | 状态 | 证据 |
|----|------|------|
| EGL ICD | 已修复 | `ensure_egl_icd.sh` |
| URDF 直立 / 贴地 | **通过** | `Ry(-90)*Rx(-90)`；`pose_diag/upright.json` |
| 适配出生点 | **已用** | offset≈1.8 m；`adapted_episode=true` |
| 初始相机 ≈0.88 m FK | **通过** | AGL≈0.881 m |
| 真实 ApexNav 闭环 | **27 步** | `.../real_20261103_124521/`：26 init + 1 explore(STOP) |
| 在线 `/grid_map` Demo | **有数据** | `demo/apexnav_ranger_paper_demo.mp4` |
| PPO Habitat | 未集成 | probe_only |
| 控制模式 | `kinematic_state_set` | 非全身动力学 |

专用镜像：`vln-rangercr10:bullet`（不覆盖 baseline tags）。

## 下一步（最多 5）

1. 选更开阔 / 同层可见目标 Episode，验证 `callActionPlanner` 产出多步 FWD/TURN（非仅 NO_COVERABLE_FRONTIER→STOP）。  
2. 继续压低贴柜接触；必要时扩大 spawn 半径或换场景。  
3. 点云一致性报告完善。  
4. 缓解 `Simulator.close()` 134（次要）。  
5. 停用后腾 GPU（VLM/roscore:11312）。
