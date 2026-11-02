# Habitat ↔ RangerBox-CR10 集成报告

更新：2026-11-03  
范围：`adapters/habitat_rangercr10/`；**不修改**六套 baseline 默认配置与验证镜像。  
HEAD 基线：`3733ca8`（混合 Demo）→ 本轮叠加 EGL 修复与原生 URDF。

---

## 总表（本轮真实状态）

| 项 | 状态 | 证据 |
|----|------|------|
| EGL（Bullet 容器） | **已修复** | 根因：`/usr/share/glvnd/egl_vendor.d/10_nvidia.json` 被清空；恢复后最小 RGB-D OK |
| Habitat 原生 URDF | **通过** | `.../kinematic_demo/summary.json`：`robot_mesh_in_habitat=true`，52 links |
| 动态 RGB-D | **通过** | `rgb_ee/` `depth_ee/`；depth0 mean≈0.79 |
| 关节限位 | **通过** | `arm_within_limits_final=true` |
| 碰撞查询 | **有诊断** | `contact_count`（运动学传送下仅作诊断，非动力学接触） |
| ApexNav 最小闭环 | **有界脚本闭环通过** | `.../apexnav_loop/`：ApexNav 动作 ID + EE 反馈；**非** ROS 全 planner |
| PPO→Habitat | **未集成** | `.../ppo_habitat_probe/`：`probe_only_not_integrated`；钉扎仍 `model_5999.pt` |
| 控制模式 | `kinematic_state_set` | **不是**全身动力学 / PPO 执行 |

钉扎：LocoManip `rangercr10-teleop` @ `1973cb4`；权重 `stage45j_ppo/model_5999.pt`（未改 4.8）。

---

## 1. EGL 修复

### 对比

| | `vln-apexnav` | `vln-rangercr10`（修复前） |
|--|---------------|---------------------------|
| `habitat_sim.built_with_bullet` | False | True |
| `10_nvidia.json` | 107 B，指向 `libEGL_nvidia.so.0` | **0 B（空文件）** |
| Windowless EGL | OK | `unable to find CUDA device 0 among 1 EGL devices` |

其它：`NVIDIA_DRIVER_CAPABILITIES`、`NVIDIA_VISIBLE_DEVICES`、GPU 设备节点两边一致；bindings `.so` 体积差来自 bullet 构建本身。

### 修复

- 恢复 ICD JSON（与 apexnav 相同内容）。
- 脚本：`adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh`（跑 Demo 前自动检查）。
- 镜像：`docker commit` → `vln-rangercr10:bullet`（**不覆盖** `vln-apexnav:*`）。

### 验收

Bullet 容器内 `enable_physics=False` 最小 RGB-D：`EGL_OK` shape `(120,160)`。

---

## 2. 原生 Habitat 机器人 Demo

```bash
bash adapters/habitat_rangercr10/scripts/run_kinematic_demo.sh
```

输出：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/kinematic_demo/`

| 检查 | 结果 |
|------|------|
| URDF 加载 | 51 links + base；`d455_depth_optical_frame` 存在 |
| 底盘 / 臂运动 | 预设方环 SE(2) + 臂插值（状态写入） |
| EE RGB-D | 随 FK 位姿更新；`frame_*.png` ×24 |
| 外参高度 | `base_y=0.4071`（对齐 MuJoCo home） |
| 限位 | 最终全部 `within` |
| 接触点数 | 有记录（诊断）；运动学传送下不可当作真实碰撞仿真 |
| 退出码 | 容器 `close()` 常 134；**以 `summary.status=ok` 为准**（脚本已区分） |

---

## 3. ApexNav 最小闭环

```bash
bash adapters/habitat_rangercr10/scripts/run_apexnav_loop.sh
```

- 动作空间对齐 `baselines/ApexNav/params.py`：STOP/FWD/TURN/LOOK。
- 本轮 planner=`scripted_actions`（深度近障比驱动转向）；**未**挂 ROS `/habitat/plan_action`。
- 每步：运动 → 新 EE RGB-D → 日志（位姿/接触/限位/深度统计）。
- 证据：`.../apexnav_loop/summary.json`，`n_steps=16`，`status=ok`。

---

## 4. PPO

| 路径 | 状态 |
|------|------|
| MuJoCo smoke（上轮） | 仍有效：117/8/3hist @10Hz |
| Habitat 迁移 | **probe_only**：观测向量无法从运动学 Habitat 对齐 Isaac 117-D；动作需 ChassisAction 轮组映射 |
| 权重 | **保持** `model_5999.pt`；未换 4.8 |

```bash
bash adapters/habitat_rangercr10/scripts/run_ppo_habitat_probe.sh
```

---

## 5. 复现命令（仓库内）

```bash
# EGL ICD 检查/修复
bash adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh

# 原生 URDF 运动学 Demo（优先）
bash adapters/habitat_rangercr10/scripts/run_kinematic_demo.sh

# ApexNav 动作闭环（运动学）
bash adapters/habitat_rangercr10/scripts/run_apexnav_loop.sh

# PPO 接口探针（预期 summary=probe_only，脚本 exit 0）
bash adapters/habitat_rangercr10/scripts/run_ppo_habitat_probe.sh

# 上轮混合 Demo（后备）
bash adapters/habitat_rangercr10/scripts/run_hybrid_kinematic_demo.sh
```

索引：`runs/habitat_rangercr10/INDEX.md`

---

## 6. 已知问题

1. `Simulator.close()` 在 0.3.1 bullet 上偶发 `corrupted size` / rc=134 — 不否决已写完的 summary。  
2. conda 安装 `headless_bullet` 可能再次清空 `10_nvidia.json` — 务必跑 `ensure_egl_icd.sh`。  
3. ApexNav **全量** ROS planner 闭环仍待接线；本轮是动作 ID + 传感器闭环。  
4. 不得把运动学 Demo 报告为 PPO 全身动力学。
