# Habitat ↔ RangerBox-CR10 集成报告

更新：2026-11-03（相机视角 / LOOK / free-space 诊断）  
范围：`adapters/habitat_rangercr10/`；**不修改**六套 baseline 默认配置、**不修改** LocoManip 训练、**不替换** stage45j 权重。  
基线保留：`44a326a` 姿态+Demo 成果；本轮叠加 LocoManip 4.10 默认臂构型只读验证与 LOOK 修正。

---

## 总表（本轮真实状态）

| 项 | 状态 | 证据 |
|----|------|------|
| URDF Z-up→Hab Y-up 直立 | **已修复** | `Ry(-90)*Rx(-90)`；`up_dot_hab_y=1.0` |
| 初始臂构型 | **采用 LocoManip 4.10 默认** | `(0.511,0.494,-2.449,-1.186,-1.060,0)`；只读自 HEAD `b0a536f` |
| D455 光学水平朝前 | **通过** | pitch/yaw/roll ≈0°；光学 AGL≈**0.783 m**（TCP/Link6≈0.86 m；0.88 为 TCP 目标） |
| 初始自遮挡 | **低** | `near_lt_0.35m ≈1.9%` |
| LOOK 遮挡 | **TURN_DOWN 诱发** | DOWN：near≈56%；UP：near≈1.9%（非初始姿态错误） |
| LOOK 关节 | **joint3**（非 joint5） | L410 下 j5 俯仰增益≈0；j3≈50°/rad |
| ApexNav free 过少 | **已定位主因** | 见 §8；先验 episode free≈6 / NO_COVERABLE_FRONTIER |
| PPO | **未接入新权重** | 仍钉 `stage45j_ppo/model_5999.pt` @ `1973cb4` |
| 控制模式 | `kinematic_state_set` | 非全身动力学 |

证据目录：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/camera_view_diag_20261103_132939/`

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

## 6. 相机视角诊断（本轮）

| 构型 | 光学 AGL | pitch/yaw/roll | near&lt;0.35m | 结论 |
|------|---------|----------------|-------------|------|
| LocoManip 4.10 默认 | 0.783 m | ≈0/0/0 | 1.9% | **选用**；臂在底盘上方，水平朝前 |
| 旧搜索 `ARM_APEXNAV_INIT_SEARCH` | 0.951 m | ≈0/−3.4/−4.4 | 1.9% | 高度更近 0.88，但腕姿极端；不再作默认 |
| Legacy teleop home | 0.964 m | **−76°** /… | 6.6% | 不可作 ApexNav 初始 |

LOOK（joint3 ±0.6 rad ≈ ±30°）：

| 状态 | pitch | near&lt;0.35m | 说明 |
|------|-------|-------------|------|
| INIT 水平 | ≈0° | 1.9% | 门/墙清晰，底缘轻微自遮挡 |
| TURN_DOWN | ≈−20° | **56%** | **执行后**臂/夹爪进入视野 |
| TURN_UP | ≈+30° | 1.9% | 基本无新增遮挡 |

复现：`bash adapters/habitat_rangercr10/scripts/run_camera_view_diag.sh`

---

## 7. ApexNav free≈0 / NO_COVERABLE_FRONTIER

实测（`real_20261103_124521`）：occ≈556，**free≈6**，unknown≈7138；exploration.log：`No coverable frontier!!`

主因（叠加，非单一）：

1. **先验 episode 用搜索臂姿**，深度 `near≈34%`（自遮挡/近场），有效中距射线少。  
2. **狭窄卧室适配出生点** + 26 步环视，占据膨胀后几乎无 coverable frontier。  
3. ApexNav `filter_min/max_height`（launch 0.28–1.18）与虚拟地面滤除后，近场噪声易挤占 FREE。  
4. 深度管线本身（归一化 32FC1→C++）在有中距观测时可工作；本轮问题更偏**观测内容/场景几何**，非编码全坏。

后续：用 4.10 默认臂 + 更开阔 Episode 再跑闭环（仍 kinematic）；新 PPO 训练完成后再单独钉权重。

---

## 8. 尚未实现 / 明确非本轮

1. 新 PPO 权重钉扎与控制性能验证（训练进行中，本轮不接）。  
2. Gazebo / 双仿真 / 全身动力学。  
3. 原版 ObjectNav benchmark 分数。  
4. 连续时间无碰撞。

---

## 9. 历史模块（仍有效）

- EGL ICD：`ensure_egl_icd.sh`；原生 URDF：`run_kinematic_demo.sh`  
- 真实闭环：`run_apexnav_real_episode.sh`（`real_20261103_124521`）  
- 相机诊断：`run_camera_view_diag.sh`