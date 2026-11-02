# PROGRESS.md — 当前状态

更新时间：2026-11-02（Habitat Ranger+CR10 运动学 Demo）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10 移动机械臂。

**当前阶段**：三套主线 `BATCH_OK` 保持；本轮交付 **Habitat 混合运动学 Demo**（MuJoCo 机器人网格 + Habitat EE RGB-D）与 **MuJoCo Teleop PPO 短测**。ApexNav 闭环因 Bullet EGL 延期。

## Baseline 状态

状态枚举：`NOT_STARTED / CLONED / CONTAINER_READY / DEPENDENCIES_READY / MODEL_LOADED / SINGLE_EPISODE_OK / BATCH_OK / BLOCKED`

| Baseline | 状态 | 证据摘要 |
|----------|------|----------|
| VLFM | `BATCH_OK` | 未改；`vln-habitat024` 仍 Up |
| ApexNav | `BATCH_OK` | 未改默认配置；借其容器 EGL 渲 EE RGB-D |
| MSGNav | `BATCH_OK` | 未改 |
| APRR | `CONTAINER_READY` | 未改 |
| SG-Nav | `CONTAINER_READY` | 数据齐；版本映射待对齐 |
| UniGoal | `CONTAINER_READY` | 数据齐；版本映射待对齐 |

## 机械臂适配（本轮）

| 项 | 状态 | 证据 |
|----|------|------|
| 独立适配目录 | 有 | `adapters/habitat_rangercr10/` |
| 混合运动学 Demo | **通过** | `.../runs/habitat_rangercr10/hybrid_kinematic_demo/summary.json`；`reports/habitat_rangercr10_integration.md` |
| 控制模式 | `kinematic_state_set` | **不是**全身动力学 |
| Teleop PPO MuJoCo 短测 | **通过** | 117/8/3hist；`model_5999.pt`；`.../mujoco_teleop_smoke/` |
| URDF 进 Habitat | 阻塞 | `vln-rangercr10:bullet` EGL 失败 |
| ApexNav 闭环 | 延期 | `.../apexnav_stub/summary.json` |

钉扎：LocoManip `rangercr10-teleop` @ `1973cb4`；权重 `stage45j_ppo/model_5999.pt`。

## 已完成（有证据）

| 项 | 证据 |
|----|------|
| 六套源码 + 三套 BATCH_OK | `reports/source_versions.*`；`runs/*/batch_8ep_status.md` |
| 共享数据齐 | `reports/manual_downloads.md` |
| 混合 Demo + PPO smoke + 报告 | `reports/habitat_rangercr10_integration.md`；`runs/habitat_rangercr10/INDEX.md` |

## 阻塞 / 风险

| 项 | 说明 |
|----|------|
| `headless_bullet` EGL | 无法 Windowless 创建上下文；URDF 可视化卡在 Habitat 内 |
| 磁盘 | 根分区紧张；大输出已落 D 盘 |
| MSGNav API | 间歇 502/timeout（与本轮无关） |

## 下一步（最多 5 项）

1. 修复 Bullet 容器 EGL（或验证非 headless bullet），跑 URDF-in-Habitat 纯运动学 Demo。  
2. 接通 `apexnav_bridge` 有界寻物闭环（不改 baseline 默认）。  
3. Habitat 侧试挂 Teleop PPO（失败则只记差异）。  
4. SG-Nav/UniGoal 版本对齐（可选）。  
5. 停用后确认 VLM/ROS/适配容器腾 GPU。
