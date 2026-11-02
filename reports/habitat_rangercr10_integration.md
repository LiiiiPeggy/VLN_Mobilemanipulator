# Habitat ↔ RangerBox-CR10 集成报告

更新：2026-11-02  
范围：独立适配层 `adapters/habitat_rangercr10/`；**不修改**六套 baseline 默认配置与已通过评测容器。  
最低验收优先：**机器人入场 / 运动 / 动态相机**。PPO 与 ApexNav **独立验收**。

---

## 0. 版本钉扎

| 项 | 值 | 证据 |
|----|----|------|
| LocoManip 分支 | `rangercr10-teleop` | `git -C LocoManip_Lab rev-parse --abbrev-ref HEAD` |
| LocoManip commit | `1973cb4f0d418af6bbf9c92156d55423b98a4963` | 同上 `rev-parse HEAD` |
| Teleop PPO 权重 | `.../2026-10-29_19-12-08_stage45j_ppo/model_5999.pt` | MuJoCo smoke |
| URDF | `rangerboxcr10lidar_description/urdf/rangercr10lidar.urdf`（Habitat 版改写 mesh 绝对路径） | `.../robots/rangercr10/rangercr10lidar_habitat.urdf` |
| Habitat-Sim（baseline ApexNav） | **0.3.1 nobullet**（EGL 正常） | `vln-apexnav` |
| Habitat-Sim（专用适配容器） | **0.3.1 headless_bullet**（`built_with_bullet=True`） | `vln-rangercr10:bullet` |
| 观测 / 动作 | **117-D / 8-D**，历史 **3**，**10 Hz** | `ranger_policy.py`；smoke `summary.json` |

---

## 1. Habitat 机器人接入 — 状态

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 现有三族镜像 Bullet | **无** | `vln-{vlfm,msgnav,apexnav}` 均为 `built_with_bullet=False` |
| 专用容器 Bullet | **有** | 自 `vln-apexnav:single-ep-deps` 克隆 → conda 换 `*headless_bullet*` → tag `vln-rangercr10:bullet` |
| URDF 加载 API | 可用（需 Bullet+物理） | `ArticulatedObjectManager.add_articulated_object_from_urdf` |
| Bullet 容器 EGL | **失败** | `unable to find CUDA device 0 among 1 EGL devices`；同机 `vln-apexnav` nobullet 正常 |
| 结论 | **混合路径交付** | 机器人网格：MuJoCo；HM3D EE RGB-D：ApexNav Habitat + MuJoCo FK |

**控制模式（强制区分）**

| 模式 | 本轮是否使用 |
|------|----------------|
| `kinematic_state_set` | **是**（底盘 SE(2)+臂关节直接写入 / FK） |
| `bullet_physics_step` / 四轮动力学 | **否** — 不得报告为全身动力学控制 |
| `contact_query_only` | 未在 Habitat 内对 URDF 完成（EGL 阻塞） |

---

## 2. 运动与相机 Demo（最低验收）— **通过（混合）**

入口：`bash adapters/habitat_rangercr10/scripts/run_hybrid_kinematic_demo.sh`  
输出：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/hybrid_kinematic_demo/`

| 验收项 | 结果 |
|--------|------|
| Ranger+CR10 完整模型显示 | **是**（MuJoCo offscreen，`robot_mujoco/frame_*.png`） |
| 底盘按预设路径运动 | **是**（方环 SE(2) 轨迹，`fk_poses.json`） |
| 机械臂关节目标 | **是**（默认 ↔ 抬升插值） |
| 末端 RGB-D 随位姿变化 | **是**（Habitat `rgb_ee/` + `depth_ee/`；相机=`d455_depth_optical_frame` FK） |
| 外参 / 高度 | base `z_up=0.4071`（MuJoCo home）；cam0 Habitat y≈**0.497 m** |
| 深度非空 | frame0 可能贴墙全 0；frame12 `max≈11.0 m mean≈1.79 m` |
| 拼图 | `collage/frame_*.png`（EE RGB \| Depth \| Robot）×24 |
| 关节限位 / 碰撞 | MuJoCo 侧默认臂在 URDF 限位内；Habitat-URDF 接触查询本轮未跑 |

`summary.json` 明确：`control_mode=kinematic_state_set`，`robot_mesh_in_habitat=false`。

---

## 3. Teleop PPO — **短测通过（MuJoCo）**

入口：`bash adapters/habitat_rangercr10/scripts/run_mujoco_teleop_smoke.sh`  
Python：`env_isaaclab5`；输出：`.../mujoco_teleop_smoke/summary.json`

| 项 | 结果 |
|----|------|
| 权重加载 | `model_5999.pt` ok |
| obs 维 | **117**（3 帧历史） |
| action 维 | **8** = `[vx,wz,j1..j6]` |
| 底盘短测 | `act_vx≈0.25`（cmd 0.2） |
| 臂短测 | EE 误差 `ee_pos≈0.037 m` |
| 联合 | `act_vx≈0.18 act_wz≈0.19` |
| Habitat 内 PPO | **未接入**（等 URDF-in-Habitat EGL 修复后再接；不为此重训） |

---

## 4. ApexNav 最小闭环 — **本轮延期**

| 项 | 状态 |
|----|------|
| 动作 ID→运动学映射代码 | 已写 `adapters/.../src/apexnav_bridge.py` |
| 语言目标→planner→地图 | **未接**（不改 baseline compose/配置） |
| 阻塞 | Bullet 容器无法创建 Windowless EGL；nobullet 无法加载 URDF |
| 记录 | `.../apexnav_stub/summary.json` → `status=deferred` |

---

## 5. 目录与复现

```
adapters/habitat_rangercr10/
  README.md
  docker-compose.yml          # 专用 vln-rangercr10:bullet
  assets/rangercr10lidar_habitat.urdf
  src/{constants,traj_utils,kinematic_demo,hybrid_kinematic_demo,apexnav_bridge,fk_camera_demo}.py
  scripts/{run_hybrid_kinematic_demo,run_mujoco_teleop_smoke,run_kinematic_demo,habitat_ee_render}.sh/.py
runs/habitat_rangercr10/INDEX.md
```

大文件仅在 D 盘 `runs/habitat_rangercr10/`。

---

## 6. 下一步（有证据再宣称）

1. 修复 `headless_bullet` EGL（或改用非 headless `py3.9_bullet_linux` 且验证 GPU），再跑 **URDF 在 Habitat 内** 的 `kinematic_demo`。  
2. 通过后接 `apexnav_bridge` → 有界多步寻物（保留高层策略，不计零成本环视）。  
3. Habitat 侧 PPO：保持 117/8/10Hz/关节映射；失败则保留 Demo+差异记录，不重训。
