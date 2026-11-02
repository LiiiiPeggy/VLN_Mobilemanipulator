# 移动机械臂适配分析（只读）— VLFM / ApexNav / MSGNav

更新：2026-11-01  
范围：分析 only，**不实现**。目标平台：AgileX **RangerBox-CR10**（swerve 底盘 + Dobot CR10 + AG95），EE RGB-D = D455。  
相邻工程仅作接口参考（未修改）：`LocoManip_Lab`、`NBV_Mobilemanipulator`（含 REMANI 桥）、`/home/ubuntu/locomani/agx`。  
权威状态仍以 `PROGRESS.md` / `runs/` 为准；本文只谈适配锚点。

---

## 0. 平台执行面（三栈对照）

| 栈 | 角色 | VLN 应否直连 |
|----|------|--------------|
| **REMANI + AGX Gazebo**（NBV 已联调） | `/ee_goal` → planner → `mm_controller` → bridges | **推荐执行面** |
| **LocoManip_Lab** Isaac WBC | `[vx,wz,j1..6]` + TCP=`cr10_Link6`+offset | 策略/仿真平行面，**非** REMANI topic |
| **agx 实机底层** | Ranger `/cmd_vel`；Dobot FollowJointTrajectory；realsense | 经 REMANI/`mm_controller`，勿在 baseline 写死关节 |

### REMANI 最小 adapter 面（NBV 已验证契约）

```text
get_rgbd()     → /realsense/{rgb,depth}/image_raw + K；frame=d455_depth_optical_frame
get_state()    → /mm/car/odom | TF base；/ee_current_pose；/mm/mani/joint_state
goto_camera()  → T_world_ee = T_world_cam · inv(T_ee_cam) + --align-remani-ee → /ee_goal
goto_base()    → /move_base_simple/goal 或 execute_base_pose_goal（仿真捷径；禁把 base_pose 当 EE）
wait_exec()    → /planning/{start,finish,trajectory} + 超时/容差门禁（无专用 collision bool）
```

关键引用：

- 变换：`NBV_Mobilemanipulator/scripts/nbv_to_remani_ee_goal.py:1-7`，`109-116`，`206-210`
- EE FK vs TF：`NBV_Mobilemanipulator/reports/remani_agx_state_alignment.md:11-15`（`/ee_current_pose` 相对 `cr10_Link6` ≈ **−0.42 m Z**）
- D455 光学系：`NBV_Mobilemanipulator/configs/perception/perception.yaml:10-14`；URDF `agx/.../rangercr10lidar.urdf:559-604`
- 反馈：`remani_replan_fsm.cpp` `/planning/start|finish`（到位才发 `finish=true`）
- LocoManip TCP：`LocoManip_Lab/.../mdp/tcp.py:26-59`（法兰+指尖 offset，**不是** D455）

**共性几何**：`T_world_camera = T_world_base × T_base_ee(q) × T_ee_camera`。三套 baseline 均把相机当**固定在 base 上的刚体**；接 EE-D455 后必须拆开「底盘导航目标」与「相机/EE 观察目标」。

---

## 1. VLFM

### 1.1 关键文件 / 函数

| 角色 | 路径 | 行号 / 符号 |
|------|------|-------------|
| 评测入口 | `baselines/VLFM/vlfm/run.py` | Hydra → habitat_baselines |
| 主策略环 | `vlfm/policy/base_objectnav_policy.py` | `act` 106–150；`_pointnav` 243–279；`_update_object_map` 281–352 |
| Habitat 观测缓存 | `vlfm/policy/habitat_policies.py` | `HabitatMixin._cache_observations` 173–237；动作 ID 54–58；`_initialize` 150–153 |
| 相机高度注入 | 同上 | `from_config` 99–107：`camera_height = rgb_sensor.position[1]` |
| 几何 | `vlfm/utils/geometry_utils.py` | `rho_theta` 9–34；`xyz_yaw_to_tf_matrix` 162–180；`get_point_cloud` 216+ |
| 障碍/前沿图 | `vlfm/mapping/obstacle_map.py` | `update_map`（depth→点云） |
| 官方成功 | Hydra 实测 | `outputs/.../.hydra/config.yaml` success_distance **0.1**（L275–277） |
| 策略 STOP | `base_objectnav_policy.py` | `pointnav_stop_radius=0.9`（L380）；`rho < radius → STOP`（275–277） |
| 实机钩子（Spot） | `vlfm/policy/reality_policies.py`；`vlfm/reality/pointnav_env.py`；`bdsw_nav_env.py` | 臂 yaw 环视 + 连续线/角速度 |

### 1.2 Pipeline

```
obs{rgb, depth, gps(2D), compass, objectgoal, heading}
  → HabitatMixin._cache_observations
       camera_position = [x, -y, camera_height=0.88]
       tf_camera_to_episodic = xyz_yaw_to_tf_matrix(...)   # 仅 yaw，无 pitch
  → detect(GD/YOLO)+SAM → ObjectPointCloudMap / ObstacleMap / ValueMap
  → mode: initialize | explore | navigate
  → PointNav ResNet → discrete action ∈ {STOP=0, FWD=1, LEFT=2, RIGHT=3}
  → Habitat Success(dist_to_viewpoint ≤ 0.1) 或策略自 STOP(ρ<0.9)
```

核心环：`base_objectnav_policy.py:120-150`。

### 1.3 相机 / 坐标系假设

| 项 | 值 | 出处 |
|----|-----|------|
| 相机高度 | **0.88 m**（相对 agent） | Hydra `rgb/depth_sensor.position[1]=0.88`；`habitat_policies.py:101,187` |
| 倾角 | **0°**（orientation 全 0） | Hydra config L184–187, 200–203 |
| HFOV / 分辨率 | **79° / 640×480** | 同上 L179–204 |
| depth 范围 | min **0.5** / max **5.0**，normalize | L208–210 |
| camera↔base | XY 与 GPS 重合，Z=固定高度；`tf` 仅 yaw | `xyz_yaw_to_tf_matrix`；无 `T_base_ee` |
| 点云相机系 | `(x,y,z)` 光学：`x=(u-cx)z/fx, y=(v-cy)z/fy, z=depth` | `geometry_utils.get_point_cloud` |

### 1.4 环视是否计入指标

- Habitat：`_initialize` = **12× TURN_LEFT**（注释 360°；`_num_steps < 11` → 共 12 步）`habitat_policies.py:150-153`。
- **计入** episode steps / SPL 路径（每个 `TURN_LEFT` 是正式 `env.step`）。
- 实机 Reality：`INITIAL_ARM_YAWS` 8 个臂角 `reality_policies.py:16`；底盘静止、`arm_yaw` 输出；**不走** Habitat 计步，但消耗真实时间。

### 1.5 最小改动清单（适配层，勿改评测协议）

1. **Obs adapter**：用 EE-D455 RGB-D 填 `observations["rgb"|"depth"]`；深度单位归一到 `[0,1]` 与 min/max 对齐；分辨率可 resize（已有 `image_resize`）。
2. **外参**：替换硬编码 `camera_height`/`xyz_yaw_only`：  
   `tf_camera_to_episodic ← T_episodic_base · T_base_ee(q) · T_ee_optical`（光学系，参考 NBV D455 教训）。
3. **状态**：`gps/compass` ← `/mm/car/odom`（或 TF `base_link`）；地图仍用 base XY；物体点云用完整相机位姿。
4. **动作**：离散 `{FWD,LEFT,RIGHT,STOP}` → swerve 封装（0.25 m / 30°）或 Reality 风格 `{linear,angular}`；**STOP 仍留给 Habitat/评测**。
5. **环视**：复用 Reality `arm_yaw` 语义 → CR10 关节或 `/ee_goal` 固定半径扫描；仿真侧保持 12 步计费以对齐 SPL。
6. **成功**：保留 Habitat `success_distance=0.1`；策略侧 `pointnav_stop_radius=0.9` 勿与官方成功半径混淆。

### 1.6 Camera-goal → EE-goal / 可行性 / 闭环缺口

| 问题 | 结论 |
|------|------|
| 需 camera→EE？ | **是**（一旦观察目标含 6D 相机位姿或 EE 环视）。导航目标多为 **2D base**（frontier/object XY）；环视/近距确认需 `nbv_to_remani_ee_goal` 同类变换 + `--align-remani-ee`。 |
| 运动可行性 | PointNav/frontier 假设差速圆足迹 `radius=0.18`；Ranger swerve + 臂伸出 footprint 更大；障碍高度窗 `min/max_obstacle_height`（默认 0.61–0.88）对矮/高障碍可能漏检。 |
| 闭环缺口 | Habitat 每步即时到位；实机无 `wait_exec`。Spot 路径用 `get_cmd_feedback`（`pointnav_env.py:56-64`）；CR10 应对齐 `/planning/finish`。无碰撞 bool；深度失效时 Reality 用 ZoeDepth 补（不可默认搬到 EE-D455）。 |

---

## 2. ApexNav

### 2.1 关键文件 / 函数

| 角色 | 路径 | 行号 / 符号 |
|------|------|-------------|
| 评测主循环 | `baselines/ApexNav/habitat_evaluation.py` | ROS sub `/habitat/plan_action` ~265；ACTION→Sim ~361–374；`env.step` ~388+；success ~445–454 |
| 动作枚举 | `baselines/ApexNav/params.py` | `ACTION` STOP..TURN_UP = 0..5（L17–23） |
| habitat2ros | `habitat2ros/habitat_publisher.py` | publishers 42–48；odom 73–86；**camera z+0.88** 88–107 |
| 点云外参 | `basic_utils/object_point_cloud_utils/object_point_cloud.py` | gps/compass → `camera_position` ~32–50 |
| 相机内参 launch | `src/planner/.../exploration.launch` | fx/fy/cx/cy ~32–36 |
| Planner FSM | `exploration_fsm.cpp` / `.h` | 26 步 init；`REACH_DISTANCE=0.20`；`ACTION_DISTANCE=0.25` |
| 配置 | `config/habitat_eval_hm3dv2.yaml` | success_distance **0.2**；forward 0.25；turn 30° |
| 实机常量 | `real_world_test_example/config/real_world_test.yaml` | camera_height **0.88**；hfov 79；640×480 |
| 连续控制 | `habitat_vel_control.py`；`exploration_traj.launch` | `/cmd_vel` |

### 2.2 Pipeline

```
env.reset/step → obs{rgb,depth,gps(3D),compass} + camera_pitch
  → habitat2ros: /habitat/camera_{rgb,depth}, /habitat/odom, /habitat/sensor_pose
  → MapROS(depth+pose) + VLM detect + object point cloud
  → ExplorationFSM: INIT → [26 init scans] → plan → /habitat/plan_action (Int32)
  → habitat_evaluation: ACTION → HabitatSimActions → env.step → /habitat/state
  → REACH_OBJECT | NO_FRONTIER | STUCK | max_steps
       → STOP；Habitat success(dist≤0.2)
```

### 2.3 相机 / 坐标系假设

| 项 | 值 | 出处 |
|----|-----|------|
| 相机高度 | **0.88 m**（硬编码多处） | `habitat_publisher.py:100`；`real_world_test.yaml:20-28`；inverse 变换 `pos.z-0.88` |
| 倾角 | 可变：`look_up/down` ±**π/6** → `camera_pitch` | `habitat_evaluation.py:367-372` |
| HFOV / 分辨率 | **79° / 640×480** | real_world yaml；fog-of-war fov=79 |
| depth | 0–5 m，normalize | `habitat_eval_hm3dv2.yaml` |
| camera↔base | base odom 与 camera 同 XY；camera z = gps_z + **0.88**；姿态含 pitch/π 翻转 | `habitat_publisher.py:73-107` |
| 点云相机系 | `[z, -x, -y]` | `geometry_utils.py:18-24` |

### 2.4 环视是否计入指标

- FSM 初始化 **26** 个离散动作：1×DOWN + 12×LEFT + 1×UP + 12×LEFT（`exploration_fsm.cpp:83-98`）。
- **全部计入** `count_steps`（`habitat_evaluation.py:381-388`）；预算常见 **500** steps → 初始化吃掉 **26/500**。
- `habitat_vel_control` 另有约 4 s 角速度转圈（连续模式，非评测主线）。

### 2.5 最小改动清单

1. **Topic 替换**（最省）：launch 中 `odom_topic` / `sensor_pose_topic` / `depth_topic` / `rgb` → 实机或 Remani 桥接同契约；可不跑 Habitat Env（见 `real_world_test_habitat.py`）。
2. **去掉 0.88 硬编码**：`habitat_publisher.py:100`、inverse、`real_world_test.yaml`、点云 `cfg_depth_sensor.position[1]` → 改为 live `T_base_camera` 或 EE 链。
3. **sensor_pose**：发 **光学系** `d455_depth_optical_frame` 在 `world` 下的位姿（与 MapROS 消费一致）；禁止把 Gazebo depth +X 与 optical +Z 弄反（NBV MEMORY 已证）。
4. **动作出口二选一**：  
   - 离散：保留 `/habitat/plan_action` → Ranger 离散执行器；  
   - 连续：`is_real_world` + `ExplorationFSMReal` + `/cmd_vel`（更贴 swerve）。
5. **LOOK_UP/DOWN**：无云台时映射为 CR10 俯仰（`/ee_goal` 或关节）并 **wait_exec**；计入或不计入时间预算需在适配层显式定义（官方评测仍计步）。
6. **成功半径**：Planner `REACH_DISTANCE=0.20` 与 Habitat `success_distance=0.2` 已对齐；换平台勿静默改。

### 2.6 Camera-goal → EE-goal / 可行性 / 闭环缺口

| 问题 | 结论 |
|------|------|
| 需 camera→EE？ | **强需要**。Planner 的 `sensor_pose` 与 look_up/down 都是相机 6D；接 EE-D455 后 look 动作 = EE 运动，必须 `T_world_ee = T_world_cam · inv(T_ee_cam)` + align。 |
| 运动可行性 | 离散步 0.25 m / 30° / 半径 0.18 同 ObjectNav；臂展开后 planner 的 2D 地图**看不到臂碰撞**（REMANI 有 car/mani collision 日志，ApexNav MapROS 无）。Pitch 扫描可能超出 CR10 工作空间 → 需可达性裁剪（NBV `nbv_remani_interface.md`）。 |
| 闭环缺口 | 仿真：`/habitat/state` ACTION_EXEC/FINISH 即时。实机：需订 `/planning/finish` + car/joint_cmd；`REACH_OBJECT` 基于 odom 距离，**无**视觉确认闭环。Stuck/fail 分类在 `failure_check.py`，不感知物理碰撞。 |

---

## 3. MSGNav

### 3.1 关键文件 / 函数

| 角色 | 路径 | 行号 / 符号 |
|------|------|-------------|
| 评测主循环 | `baselines/MSGNav/run_hm3d_evaluation.py` | 环视+积分 ~267–339；`agent_step` 后更新 ~452+；VLM end ~486–505；成功距离 ~511–521 |
| Sim/相机 | `src/habitat.py` | sensor specs 63–77；pose 变换 29–43 |
| Scene 观测 | `src/multimodal_3d_scene_graph.py` | `get_observation` 188–213；sim_settings 107–116 |
| 连续规划 | `src/tsdf_planner.py` | `agent_step` ~475–754 |
| 配置 | `cfg/eval_hm3d.yaml` | 相机 74–79；success 81–82；extra_view 96–99；步长 108–109 |
| 位姿解析 | `src/utils.py` | `get_pts_angle_goatbench` 141–148；`calc_agent_subtask_distance` 150–161 |
| 日志/SPL | `src/logger_hm3d.py` | `log_step` 路径长度 |

**注意**：MSGNav **不使用** Habitat-Lab 离散 ObjectNav 动作；`habitat-lab/` 为 vendored 依赖，评测主路径是 **habitat-sim `agent.set_state` 传送**。

### 3.2 Pipeline

```
episode start_position/rotation → (pts, angle)
  loop:
    7× get_observation(pts, ang_i)   # 同位置多 yaw；set_state 传送
      rgb=color_sensor, depth=depth_sensor, cam_pose
      → scene graph + TSDF.integrate
    VLM → frontier / object 目标
    tsdf_planner.agent_step → 连续 (pts', yaw')，最大 1.8 m / 1.0 m
    if object arrived: VLM "yes"/"no" → 可 break
  geodesic(pts → viewpoints) < success_distance(1.0) → success / SPL
```

### 3.3 相机 / 坐标系假设

| 项 | 值 | 出处 |
|----|-----|------|
| 相机高度 | **1.5 m** | `cfg/eval_hm3d.yaml:74-79`；`sensor_height` |
| 倾角 | **−30°**（绕 +X） | `camera_tilt_deg: -30`；`habitat.py:68,76` |
| HFOV / 分辨率 | **120° / 1280×1280** | 同上 |
| UUID | `color_sensor` / `depth_sensor`（非 `rgb`/`depth`） | `habitat.py:64-72` |
| camera↔base | 传感器固定在 agent：`position = UP * height`，tilt 在 sensor.orientation；agent 状态仅 yaw | `get_observation` |
| 状态源 | **无 GPS/compass 传感器**；绝对 `(pts,yaw)` | `utils.get_pts_angle_goatbench` |

### 3.4 环视是否计入指标

- 每 planner step：**1+6=7** 视角，间隔 40°（`extra_view_*`）。
- **`cnt_step` 每循环 +1 一次**；环视在同一步内 → **不增加步数**。
- **`subtask_explore_dist` 不因环视增加**（仅 `agent_step` 后 `log_step`）。
- 实现是 `set_state` 传送，**非** `sim.step(action)` → Habitat 意义下「免费」。
- **实机必须显式计时/计电机成本**，否则指标与仿真不可比。

### 3.5 最小改动清单

1. **Obs**：`get_observation` 改为订 EE-D455；保持返回 `(obs_dict, cam_pose_4x4)` 契约；内参改用 `camera_info` 或实测 K（勿沿用 HFOV120/1280 假设）。
2. **外参**：`cam_pose` 必须来自 TF `world→d455_depth_optical_frame`（或 base odom × EE FK × T_ee_cam）；删除固定 1.5 m / −30°。
3. **动作执行器（新建）**：`agent_step` 输出的 `(pts', yaw')` →  
   - base：`goto_base_pose` / REMANI waypoint；  
   - 禁止继续 `set_state` 传送冒充实机。
4. **环视**：7 yaw → CR10/底盘原地转向序列 + `wait_exec`；配置开关 `charge_extra_views_in_metrics`。
5. **成功**：保留 `success_distance=1.0`（HM3D 配置）与 VLM end gate；**勿**改成 Habitat 0.1/0.2 除非单独协议实验。
6. **场景图/TSDF**：`pose_habitat_to_tsdf` 链保持；只替换上游 `cam_pose` 来源。

### 3.6 Camera-goal → EE-goal / 可行性 / 闭环缺口

| 问题 | 结论 |
|------|------|
| 需 camera→EE？ | 导航目标是 **agent 基座位姿**（pts+yaw），不是相机光学目标；但观测来自倾斜相机，实机 EE 高度/倾角变化会破坏 TSDF 与「1.5 m/−30°」训练假设 → 近距观察/确认阶段**需要** EE 目标变换。Frontier 探索可先只动底盘、臂锁定标称倾角。 |
| 运动可行性 | `max_dist_from_cur` 1.8/1.0 m 单步跳跃在实机不可直接执行，需跟踪/分割轨迹；navmesh 连通 ≠ Ranger+臂可通行；无足迹膨胀对接 swerve。 |
| 闭环缺口 | **最大**：传送式执行零跟踪误差；无 `/planning/finish`、无碰撞、无里程计漂移。VLM end 是开环语义确认。SPL 用体素路径长，与真实里程不一致。 |

---

## 4. 三套横向对比

| 维度 | VLFM | ApexNav | MSGNav |
|------|------|---------|--------|
| 观测键 | `rgb`,`depth` | 同左 + ROS Image | `color_sensor`,`depth_sensor` |
| 状态 | gps(2)+compass | gps(3)+compass+pitch | 绝对 pts+yaw |
| 动作 | 离散 0–3 | 离散 0–5（含 look）+ 可选 cmd_vel | 连续位姿传送 |
| 官方成功距 | **0.1 m** | **0.2 m** | **1.0 m**（HM3D cfg） |
| 策略自停 | ρ&lt;0.9 | REACH 0.20 + STOP | VLM yes + 距离 |
| 相机高度/倾角 | 0.88 / 0° | 0.88 / 可变±30° | **1.5 / −30°** |
| 环视计费 | **是**（12 steps） | **是**（26 steps） | **否**（7 views 免费） |
| 最近实机钩子 | Spot RealityMixin | habitat2ros + real_world_test | 无；需新建执行器 |
| 接 REMANI 成本 | 中（加 obs/action 适配） | **低**（topic 替换） | 高（动作语义重建） |

---

## 5. 推荐适配顺序（分析结论，非实施）

1. **ApexNav**：ROS 契约已在；先换 RGB-D/odom topic + 去 0.88 + EE look 映射 + `wait_exec`。  
2. **VLFM**：抽 `HabitatMixin._cache_observations` / RealityMixin 为 Ranger adapter；离散执行器复用 ApexNav/REMANI base。  
3. **MSGNav**：先做「连续目标 → REMANI base/EE」执行器与环视计费，再谈公平对比。

统一约束（与 `MEMORY.md` §6 一致）：

- 不静默改上游成功半径 / SPL 定义；平台差异放适配层开关。  
- EE 目标一律 `T_world_ee = T_world_cam · inv(T_ee_cam)` + `--align-remani-ee`。  
- 碰撞无 bool topic → 超时 + finish 缺失 + 日志关键字。  
- 4070 8GB：多 VLM 需顺序加载（本报告不展开实测）。

---

## 6. 可粘贴至 `baseline_validation.md` §7 的定稿草案

见同目录对该节的更新；正文摘要：

> 三套均把 RGB-D 当作固定于 base 的相机。VLFM/ApexNav：0.88 m、HFOV79°、离散 Habitat 动作；环视 12/26 步计入。MSGNav：1.5 m、−30°、HFOV120°、连续 `set_state`；7 视角环视不计步。实机执行面优先 REMANI `/ee_goal` + `/ee_current_pose` + `/planning/finish`；ApexNav 的 habitat2ros topic 为最低成本替换点。Camera→EE 变换与 FK/TF Z 偏置（≈0.42 m）必须显式处理。

---

## 7. 证据索引（本仓库 + 相邻）

| 证据 | 路径 |
|------|------|
| VLFM 单 ep | `runs/VLFM/single_episode_status.md` |
| ApexNav 单 ep | `runs/ApexNav/single_episode_status.md` |
| MSGNav 单 ep | `runs/MSGNav/single_episode_status.md` |
| NBV↔REMANI | `NBV_Mobilemanipulator/reports/nbv_remani_interface.md` |
| EE 对齐 | `NBV_Mobilemanipulator/reports/remani_agx_state_alignment.md` |
| D455 坑 | `NBV_Mobilemanipulator/MEMORY.md`（传感器 pose） |
