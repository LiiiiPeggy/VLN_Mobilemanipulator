# PROGRESS.md — 当前状态

更新时间：2026-11-04（Demo 7 Hz 同步 + 白底占据图；Stage 4.10d 成果保留）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Stage 4.10d + ApexNav 多步探索保留；论文风 Demo 已出 **7 FPS / 1280×720** 同步版（白底地图），原 2 FPS 保留。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂适配（Stage 4.10d）

| 项 | 状态 | 证据 |
|----|------|------|
| 钉扎 | `ec5fd65` + `stage410d_ppo/model_5999.pt` | `VERSION_stage410d.json` |
| MuJoCo PPO | **通过** | `ppo_stage410d_mujoco_20261104_113929/` |
| Habitat 直立/相机 | Hab AGL≈0.857；角≈0；near=0 | `camera_view_diag_stage410d_20261104_114102/` |
| ApexNav 探索 | **24 explore / FWD×4** | `apexnav_real/20261104_114652/` |
| 狭窄 ep | free↑ 但仍可能 NO_PASSABLE | `20261104_114357/` |
| PPO→Habitat | 探针 only | `ppo_habitat_probe_stage410d/` |
| 控制（ApexNav） | `kinematic_state_set` | 与 PPO MuJoCo 分列 |
| Demo 7 Hz | **通过** | `apexnav_ranger_paper_demo_7fps.mp4`；`demo_7fps_rates.json` |

报告：`reports/habitat_rangercr10_integration.md`

## 下一步（最多 5）

1. 记录/可视化 NO_PASSABLE 时的 frontier 候选与膨胀（仍不改规划算法）。  
2. 可选：更多开阔 ObjectNav ep 有界复现。  
3. PPO→Habitat：仅在能装配真实 117-D 观测时再推进（禁止零观测冒充）。  
4. 点云一致性报告完善。  
5. 停用后腾 GPU。
