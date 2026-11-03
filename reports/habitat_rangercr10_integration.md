# Habitat ↔ RangerBox-CR10 集成报告

更新：2026-11-03  
范围：`adapters/habitat_rangercr10/`；**不修改**六套 baseline 默认配置与已验证 BATCH_OK 镜像。  
基线保留：`0969cd3` 已验证成果；本轮叠加真实 ApexNav ROS 闭环与初始相机 FK 构型。

---

## 总表（本轮真实状态）

| 项 | 状态 | 证据 |
|----|------|------|
| 真实 ApexNav 视觉感知 | **已运行** | ITM cosine 每步有值；`detections/frame_*.png`×12 |
| 语义/占据地图更新 | **已触发** | `exploration.log`：Grid/ESDF Map process；FSM PLAN→PUB→WAIT_FINISH |
| 导航动作来自原始 planner | **是** | `actions.jsonl` / `steps.jsonl`：`action_source=apexnav_/habitat/plan_action`；`scripted_policy_used=false` |
| Ranger 执行与反馈 | **是（运动学）** | 每步 exec + 新 RGB-D；LOOK=臂关节适配 |
| 动态相机投影 | **适配层 SE3** | `/habitat/sensor_pose`=EE FK；`/habitat/odom`=base；非固定 +0.88 m 伪造 |
| 初始相机 ≈0.88 m 水平 | **通过（容差内）** | `camera_init/`：AGL≈0.870 m，\|pitch/yaw/roll\|&lt;5° |
| 寻物 Episode | **多步尝试完成** | `real_20261103_120649`：12 步；`termination=step_budget_exhausted`；**未宣称成功** |
| 控制模式 | `kinematic_state_set` | **不是** PPO / 全身动力学 |

钉扎：LocoManip `1973cb4`；Teleop 权重仍 `stage45j_ppo/model_5999.pt`。

---

## 1. 验收闭环证据（最低验收）

运行 ID：`real_20261103_120649`  
目录：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_20261103_120649/`

链路（日志可对应）：

1. 目标：`target_label.json` → chair（LLM 辅助类 couch/toilet/plant）  
2. 初始 FK 相机：`camera_init/initial_camera_pose.json`（ARM_APEXNAV_INIT）  
3. RGB-D 发布 → exploration FSM Triggered → `/habitat/plan_action`  
4. 动作序列：TURN_DOWN → 多次 TURN_LEFT（planner 初始化环视）  
5. 每步 ITM + detector → `steps.jsonl`（含 `itm_cosine`、exec、pose）  
6. 终止：`step_budget_exhausted`（非 planner STOP 伪装）

| 字段 | 值 |
|------|-----|
| status | ok |
| n_steps / seen_plan_actions | 12 / 12 |
| scripted_policy_used | false |
| success_claimed | false |
| final_dtg (eval-only) | ≈2.10 m |
| Demo | `demo/apexnav_ranger_real_loop.mp4` |

进程：`Simulator.close()` 仍可能 SIGABRT/134；任务结果以 `summary.json` 为准（见 `process_meta.json`）。

---

## 2. 初始 D455 位姿（本轮补充）

| 要求 | 结果 |
|------|------|
| 光学中心高度 0.88 m AGL | FK AGL≈**0.870 m**（\|Δ\|≈1.0 cm ≤2 cm） |
| 光轴水平、朝底盘前方 | pitch≈−4.6°，yaw_err≈2.4°，roll≈−1.9°（均 ≤5°） |
| 由 URDF 关节+FK 产生 | **是**；禁用伪造 Agent 相机 |
| `ARM_DEFAULT` | **不满足**（高度≈0.42 m，光轴近后方）→ 未用于 Episode |

构型常量：`ARM_APEXNAV_INIT`（`constants.py`）；验证模块：`initial_camera_pose.py`。

---

## 3. 动态相机与坐标系

- `ros_dynamic_publisher.py`：分开发布 base odom 与 EE `sensor_pose`（child_frame=`d455_depth_optical_frame`）。  
- `pointcloud_dynamic.py`：全 SE(3) 投影（适配层，不改 ApexNav 默认 `object_point_cloud.py`）。  
- 第三人称渲染在 planner 发布**之后**拍摄，避免污染 EE 观测。  
- 深度：米制 → ApexNav 期望的 [0,1] 归一化。

---

## 4. 动作与约束

| 动作 | 执行 | 等价性 |
|------|------|--------|
| FWD/TURN | 底盘 SE(2) 运动学 | 离散步长对齐 ApexNav 0.25 m / 30° |
| LOOK_UP/DOWN | CR10 joint5 ±，FK 验俯仰 | **机械臂适配**，≠ Habitat agent ±30° look |
| STOP | 标记终止 | — |

碰撞：完整 URDF 接触查询作诊断/阻挡启发；**非**连续时间无碰撞保证。未向 planner 泄露目标真值（dtg 仅评估）。

---

## 5. 复现命令

```bash
# 孤立 ROS master :11312，避免占用主机 NBV :11311 / 改动 vln-apexnav 容器网
bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
# 或手动：ensure_egl_icd → roscore:11312 → exploration.launch → VLM(HF/TORCH offline) →
# python -m src.apexnav_real_episode --run_id <id> --max_steps 12 --category_filter chair
```

依赖提示：

- 容器内需 `ln -sfn .../baselines/ApexNav /workspace/ApexNav`（catkin 构建前缀）。  
- `HF_HOME`/`TORCH_HOME` 指向 `/media/ubuntu/D/VLN_shared/cache/...`；`bert-base-uncased` 本地目录软链到 `/workspace/ApexNav/`。  
- `data/groundingdino_swint_ogc.pth` → D 盘实文件（避免指向未挂载的 NBV 路径）。

脚本闭环（非 planner）仍可用：`run_apexnav_loop.sh`。

---

## 6. 尚未实现 / 明确非本轮

1. PPO → Habitat 全身动力学。  
2. 自主调臂策略（仅 LOOK 关节适配）。  
3. Gazebo / 双仿真同步。  
4. 批量 ObjectNav benchmark（本轮单次有界尝试）。  
5. 连续时间无碰撞与轮式动力学。

---

## 7. 历史模块（仍有效）

- EGL ICD 修复：`ensure_egl_icd.sh`  
- 原生 URDF kinematic demo：`run_kinematic_demo.sh`  
- PPO probe_only：`run_ppo_habitat_probe.sh`（权重未改 4.8）
