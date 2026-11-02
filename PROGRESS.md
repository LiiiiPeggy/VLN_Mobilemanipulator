# PROGRESS.md — 当前状态

更新时间：2026-11-03（EGL 修复 + 原生 Habitat URDF）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：三套主线 `BATCH_OK` 保持；**Bullet EGL 已修**；**原生 Habitat URDF 运动学 Demo 通过**；ApexNav 动作闭环（脚本策略）通过；PPO→Habitat 未集成（探针已记差异）。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改；apexnav 仍 nobullet |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂适配

| 项 | 状态 | 证据 |
|----|------|------|
| EGL ICD | **已修复** | 空 `10_nvidia.json` → 恢复；`ensure_egl_icd.sh` |
| 原生 URDF Demo | **通过** | `.../kinematic_demo/summary.json` |
| 动态 RGB-D / 限位 | **通过** | traj + frames |
| ApexNav 闭环 | **脚本闭环通过** | `.../apexnav_loop/`（非 ROS 全 planner） |
| PPO Habitat | **未集成** | `.../ppo_habitat_probe/` |
| 控制模式 | `kinematic_state_set` | 非全身动力学 |

专用镜像：`vln-rangercr10:bullet`（不覆盖 baseline tags）。

## 下一步（最多 5）

1. 可选：把 ApexNav ROS `/habitat/plan_action` 接到 `apexnav_bridge`（仍不改 baseline 默认）。  
2. 若要坚持 PPO-in-Habitat：补齐 117-D 观测装配与 ChassisAction（失败则继续 MuJoCo）。  
3. 缓解 `Simulator.close()` 134（次要）。  
4. SG-Nav/UniGoal 版本对齐（可选）。  
5. 停用后腾 GPU。
