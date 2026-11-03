# Habitat ↔ RangerBox-CR10 集成报告

更新：2026-11-03  
范围：`adapters/habitat_rangercr10/`；**不修改**六套 baseline 默认配置与已验证 BATCH_OK 镜像。  
基线保留：`322f527` / 先前 `0969cd3` 已验证成果；本轮叠加姿态修复、论文风 Demo、初始化环视后正式规划验证。

---

## 总表（本轮真实状态）

| 项 | 状态 | 证据 |
|----|------|------|
| URDF Z-up→Hab Y-up 直立 | **已修复** | 根姿态 `Ry(-90)*Rx(-90)`；`up_dot_hab_y=1.0`，轮高差≈1.6 mm |
| 车轮贴地 | **通过（几何）** | `wheel_mean_agl≈0.125 m`（半径）；`pose_diag/` + `upright.json` |
| 适配 Episode 出生点 | **已偏移** | 原始起点家具重叠；偏移 ≈1.8 m；`adapted_episode=true`（非原版 benchmark） |
| 真实 ApexNav 感知 | **已运行** | ITM + `detections/`；非 scripted |
| 在线 `/grid_map/*` | **有数据** | occ/free/unknown 消息计数见 summary；Demo 右下角 |
| 导航动作来自 planner | **是** | `action_source=apexnav_/habitat/plan_action` |
| 初始化环视 vs 正式规划 | **已区分** | 26 步 `init_lookaround` + ≥1 步 `explore_planner`（本轮为 STOP / NO_COVERABLE_FRONTIER） |
| 16:9 论文风 Demo | **已产出** | 主视角 + EE 语义 + 在线占据图；`demo/apexnav_ranger_paper_demo.mp4` |
| 控制模式 | `kinematic_state_set` | **不是** PPO / Bullet 全身动力学 |

钉扎：LocoManip `1973cb4`；Teleop 权重仍 `stage45j_ppo/model_5999.pt`。

---

## 1. 本轮验收运行

运行 ID：`real_20261103_124521`  
目录：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_20261103_124521/`

| 字段 | 值 |
|------|-----|
| status | ok |
| termination | planner_stop |
| n_steps | 27（26 init + 1 explore） |
| entered_callActionPlanner | **true** |
| explore 动作 | STOP（`EXPL_RESULT::NO_COVERABLE_FRONTIER`） |
| online_grid_map.has_data | true（occ≈556, free≈6, unknown≈7138） |
| adapted_episode | true（offset≈1.8 m） |
| scripted_policy_used | false |
| success_claimed | false |
| Demo | `demo/apexnav_ranger_paper_demo.mp4`（1280×720） |
| 姿态诊断 | `pose_diag/{third,side,top,upright.json}` |

**诚实说明**：正式规划阶段已进入 `callActionPlanner()`，但因在线地图几乎无 coverable frontier，planner 立即 STOP；**不能**把初始化 26 步环视当作自适应探索成功。寻物未成功（eval-only dtg≈3.89 m）。

姿态截图备份：`.../pose_fix_20261103/episode_real_124521/`。

---

## 2. 姿态 / 穿模根因与修复

| 问题 | 根因 | 修复 |
|------|------|------|
| 机器人“倒下” | URDF ROS Z-up 直接放入 Habitat Y-up，缺根旋转 | `_urdf_to_habitat = Ry(-π/2)*Rx(-π/2)` |
| 轮子悬空/穿地 | 需按轮半径相对 `floor_y` 贴地 | `snap_wheels_to_floor`；`DEFAULT_BASE_Y≈0.4419` |
| 出生点穿模 | ObjectNav 起点为小足迹 agent，完整 Ranger+CR10 与床/柜重叠 | `spawn_utils.find_adapted_start`（接触探测+环形搜索）；**标记 adapted_episode** |
| 第三人称被挡 | 固定身后距离易进墙 | `compute_third_person_T` 多距离/高度 + pathfinder 拒绝 |

保持 `kinematic_state_set`；接触数为诊断，非连续时间无碰保证。

相机：`ARM_APEXNAV_INIT` 在轴修正后重标定；本轮 FK AGL≈0.881 m，角误差 &lt;5°。

---

## 3. Demo 布局（16:9）

- **主画面**：Habitat 第三人称跟随（后上方斜俯，机器人居中）  
- **左下**：末端 D455 RGB + ApexNav `detections/`（复用本步 VLM，不重跑）  
- **右下**：ApexNav `/grid_map/{occupied,free,unknown}` 栅格化（**非** Habitat 真值图）  
- **顶栏**：Object Goal / Step / Action / Phase / control_mode / status  

合成：`demo_compose.py`；地图订阅：`map_listener.py`。

---

## 4. ApexNav FSM 阶段

`exploration_fsm.cpp`：`init_action_count_ < 26` 时预设 TURN_DOWN×1 + TURN_LEFT×12 + TURN_UP×1 + TURN_LEFT×12；其后 `callActionPlanner()`。

本轮动作序列与之一致；第 27 步（step=26）phase=`explore_planner`，动作为 STOP。

---

## 5. 复现命令

```bash
# 孤立 ROS master :11312（勿占 NBV :11311）
MAX_STEPS=36 RUN_ID=real_$(date +%Y%m%d_%H%M%S) \
  bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
```

依赖：容器内 `/workspace/ApexNav` → `baselines/ApexNav`；HF/TORCH offline 缓存；GroundingDINO 权重在 D 盘。

---

## 6. 尚未实现 / 明确非本轮

1. PPO → Habitat 全身动力学。  
2. 自主调臂（仅 LOOK 关节适配）。  
3. Gazebo / 双仿真。  
4. 原版 ObjectNav benchmark 分数（本轮为适配 Episode）。  
5. 连续时间无碰撞与轮式动力学。  
6. 在更开阔场景上验证多步 frontier 运动（本轮 planner 因 NO_COVERABLE_FRONTIER 早停）。

---

## 7. 历史模块（仍有效）

- EGL ICD：`ensure_egl_icd.sh`  
- 原生 URDF kinematic：`run_kinematic_demo.sh`  
- PPO probe_only：`run_ppo_habitat_probe.sh`  
- 先前闭环：`real_20261103_120649`（仅 12 步 init，未进正式规划）
