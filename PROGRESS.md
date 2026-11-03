# PROGRESS.md — 当前状态

更新时间：2026-11-03（真实 ApexNav→Ranger+CR10 多步寻物尝试）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：三套主线 `BATCH_OK` 保持；原生 URDF + **真实 ApexNav ROS planner 多步闭环**已有可复现证据；控制仍为 `kinematic_state_set`。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改；apexnav 仍 nobullet |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂适配

| 项 | 状态 | 证据 |
|----|------|------|
| EGL ICD | 已修复 | `ensure_egl_icd.sh` |
| 原生 URDF Demo | 通过 | `.../kinematic_demo/` |
| 初始相机 ≈0.88 m FK | **通过** | `ARM_APEXNAV_INIT`；AGL≈0.870 m |
| 真实 ApexNav 闭环 | **多步尝试 OK** | `.../apexnav_real/real_20261103_120649/`（非 scripted） |
| PPO Habitat | 未集成 | probe_only；权重仍 `model_5999.pt` |
| 控制模式 | `kinematic_state_set` | 非全身动力学 |

专用镜像：`vln-rangercr10:bullet`（不覆盖 baseline tags）。

## 下一步（最多 5）

1. 拉长步数/选同层可见目标，观察 planner 出 STOP 或视觉确认。  
2. 点云一致性报告完善（中心 patch 诊断已有脚本）。  
3. 若要坚持 PPO-in-Habitat：117-D 观测装配（可选）。  
4. 缓解 `Simulator.close()` 134（次要）。  
5. 停用后腾 GPU（VLM/roscore:11312）。
