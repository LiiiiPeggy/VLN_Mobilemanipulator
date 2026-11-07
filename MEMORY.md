# MEMORY.md — 长期有效知识

只记录经代码/配置/运行验证、可长期复用的信息。  
临时进度见 `PROGRESS.md`；决策与排障过程见 `PROCESS.md`；完整日志在 `runs/` / `reports/`。

## 1. 研究目标与平台约束

| 项 | 内容 |
|----|------|
| 目标 | 复现并对比六套零样本 / goal-oriented 导航 baseline，再适配移动机械臂 VLN |
| 目标平台 | AgileX **RangerBox-CR10**（四轮转向底盘 + Dobot CR10 + AG95）；策略与仿真参考 `LocoManip_Lab`，NBV 感知/规划参考 `NBV_Mobilemanipulator` |
| 仿真主栈 | Habitat（各 baseline 版本不同，见下表）；后期再接 Isaac / 实机，勿提前混用 |
| 硬约束 | 不破坏 NBV/FKIE/SSMI/REMANI；不改上游默认评估协议；大文件落 `/media/ubuntu/D/VLN_shared` |

## 2. 宿主机环境（导入时快照 + 2026-10-29 复核）

证据：`reports/source_versions.md`；本机 `nvidia-smi` / `docker version`。

| 组件 | 值 |
|------|-----|
| 主机名 | `ubun` |
| OS | Ubuntu 22.04.5 LTS |
| GPU | NVIDIA RTX A6000，49140 MiB，Driver **550.163.01** |
| CUDA（驱动侧） | 12.4 |
| Docker | **27.3.1**，Compose **v2.29.7**，nvidia runtime 可用 |
| 磁盘 | `/` 约 245 GiB 可用（~93%，紧张）；`/media/ubuntu/D` 约 1.9 TiB 可用（大数据优先） |
| 项目根 | `/home/ubuntu/locomani/VLN_Mobilemanipulator` |

宿主机已有长期容器（**禁止动**）：`nbv_fkie`、`nbv_ssmi`、以及 `lxy`/`zxg`/`zfy`/`hkp`/`chn`/`cjf`/`gly`/`yly` 等。`scene_graph:latest` **无** habitat_sim，不可当 VLN 基座。

本机 conda 中**无** baseline 专用环境；评测一律走 `vln-*` 容器。

## 3. 仓库布局与共享数据

```
VLN_Mobilemanipulator/
  baselines/{VLFM,ApexNav,MSGNav,APRR,SG-Nav,UniGoal}/
    docker-compose.yml                          # 每套独立 compose
  shared/docker/Dockerfile.{habitat024,habitat025,apexnav,lite}
  shared/{datasets,checkpoints,cache}/          # gitkeep 占位
  shared/{datasets,checkpoints,cache,runs}_large → /media/ubuntu/D/VLN_shared/...
  runs/<Baseline>/                              # 摘要结果
  reports/                                      # 审计报告
  scripts/strip_nested_git.py                   # 导入后剥离嵌套 .git
```

- 大权重/场景/缓存写入 `shared/*_large`（D 盘），不要写满根分区。
- `.gitignore` 已排除 datasets、checkpoints、cache、常见权重后缀与嵌套 `.git/`；`pointnav_weights.pth` 有例外规则（VLFM 自带导航权重）。
- VLFM/ApexNav compose 只读挂载 NBV 仓内 GroundingDINO 权重目录（若存在）：`NBV_Mobilemanipulator/checkpoints/grounding_dino` → `/shared/weights/grounding_dino`。

## 3.1 Docker 镜像规划

| 镜像名 | Dockerfile | 服务 | 说明 |
|--------|------------|------|------|
| `vln-habitat024` | `Dockerfile.habitat024` | `vln-vlfm` | **正式 + VLFM deps commit**（2026-11-01）：`fe6b1ca643fd`，19GB；sim 0.2.4 + lab 0.2.420230405 + torch 1.12.1+cu113；Aliyun apt/pip；LAVIS/spacy/MobileSAM/GD 在容器内装后 `docker commit`；open3d 需 `dash<3`（pydantic v1） |
| `vln-habitat025` | `Dockerfile.habitat025` | `vln-msgnav`（及暂挂的 sgnav/unigoal） | **正式**（2026-10-31）：`ff049f5c4eed`，22.6GB；CUDA 11.8 + torch 2.0.1 + habitat-sim 0.2.5；须 Aliyun apt。MSGNav 运行时 extras：`vln-habitat025:msgnav-deps`=`1b1bdc94f963`（HiPart/pytorch3d/clip/`ollama`；勿 recreate 冲掉未 commit 层） |
| `vln-apexnav` | `Dockerfile.apexnav` | `vln-apexnav` | **正式 + 单 ep 运行时 commit**（2026-11-01）：`50e76a268b26`（`:single-ep-deps`/`:latest`，28.2GB；build 底 `118284656358`）；CUDA 12.1 + torch 2.5.0+cu121 + habitat-sim/lab **0.3.1**；**numpy 钉死 1.23.5**；运行时含 LAVIS/GD/MobileSAM、ROS Noetic（自 `nbv-fkie:noetic` **镜像**拷贝）+ catkin `exploration_node`；compose 挂 `/media/ubuntu/D/VLN_shared` 同路径；证据 `runs/ApexNav/single_episode_status.md` |
| `vln-lite` | `Dockerfile.lite` | `vln-aprr` | 基于 `pytorch/pytorch:2.3.1-cuda12.1` 的轻量审计镜像 |

容器名固定为 `vln-{vlfm,apexnav,msgnav,aprr,sgnav,unigoal}`，与 `nbv_*` / 他人容器隔离。  
证据：`runs/_build/habitat024_status.md`、`runs/_build/habitat024_retry.log`。

## 4. 六个 baseline：架构与依赖差异

上游 SHA 权威表：`reports/source_versions.md`。下表为文档宣称栈；**VLFM / MSGNav / ApexNav 已在本机容器验证到 `BATCH_OK`**（其余仍偏文档级）。

| Baseline | 任务形态 | 关键栈（文档宣称） | Habitat | 官方 Docker / 环境入口 | 额外注意 |
|----------|----------|-------------------|---------|------------------------|----------|
| **VLFM** | ObjectNav；frontier + VLM value map | Python 3.9；torch 1.12.1+cu113；GroundingDINO；LAVIS；可选 Spot | sim `v0.2.4`；lab `0.2.420230405`（`pyproject.toml`） | compose → `vln-habitat024`；上游另有 `docker/Dockerfile` | **BATCH_OK**；需 yolov7；`data/pointnav_weights.pth` |
| **ApexNav** | ObjectNav；target-centric fusion + 自适应探索 | conda `apexnav_environment.yaml`；torch 2.5.0（cu118/121/124） | **sim/lab 0.3.1** | compose → `vln-apexnav` | **BATCH_OK**；VLM=`vlm.*` 多端口；ROS Noetic planner |
| **MSGNav** | ObjectNav / GOAT-Bench；多模态 3D scene graph | Python 3.9；torch 2.0.1+cu118；open-clip；ultralytics | **sim 0.2.5**；vendored `habitat-lab/` | compose → `vln-habitat025:msgnav-deps` | **BATCH_OK**；需 LLM API（`gpt-5.6-sol`） |
| **APRR** | OVMM / Home-Robot 系 | 依赖 Facebook `home-robot` + Habitat challenge 镜像文档 | 随 home-robot / habitat-lab 子树 | compose → `vln-lite`（审计用）；完整栈仍参考官方 challenge 镜像 | 子模块未完全初始化；评测脚本 `runb.sh` / `run_rl.sh` |
| **SG-Nav** | ObjectNav；在线 3D scene graph → LLM | Python 3.9；habitat-sim 0.2.4；GLIP / GroundingDINO / SAM | **sim 0.2.4**；vendored `habitat-lab/` | compose 暂挂 `vln-habitat025`（**版本待改**） | **必须**用 `tools/agent.py` 覆盖 habitat-sim 的 `agent/agent.py` |
| **UniGoal** | 统一 goal（image/text；object 仍在完善） | Python 3.8；sim/lab 0.2.3；Grounded-SAM；detectron2；pytorch3d | **sim/lab 0.2.3**；`third_party/habitat-lab` | compose 暂挂 `vln-habitat025`（**版本待改**） | 与 SG-Nav 同组作者；接口相近但版本更旧 |

### Habitat 版本互斥（重要）

`0.2.3`（UniGoal）/ `0.2.4`（VLFM、SG-Nav）/ `0.2.5`（MSGNav）/ `0.3.1`（ApexNav）**不可**混装进同一 conda/容器环境。这是六套独立 compose/容器的主要技术理由。镜像层若仅差 Python 包，可共享同一 CUDA base，但环境前缀必须隔离。

## 5. 关键启动命令（本机路径）

路径均相对于各 `baselines/<Name>/`。带证据的标「已验证」。

- **VLFM**（BATCH_OK）：`scripts/run_vlfm_batch8.sh` → 容器内 `python -m vlfm.vlm.*` 12181–84 + `python -m vlfm.run habitat_baselines.test_episode_count=8`
- **ApexNav**（BATCH_OK）：`scripts/run_apexnav_batch8.sh` → ROS + `python -m vlm.detector/itm/segmentor.*`（**不是** `vlfm.vlm`）+ `habitat_evaluation.py --dataset hm3dv2 test_epi_num=0..7`；镜像 `:single-ep-deps`=`50e76a268b26`
- **MSGNav**（BATCH_OK）：`scripts/run_msgnav_batch8.sh` → `run_hm3d_evaluation.py -cf cfg/eval_hm3d_batch8.yaml --specific 0..7`；密钥仅 `baselines/MSGNav/.env`；`--specific` 时场景列表排序且跳过 shuffle
- **APRR**：`bash runb.sh` / `bash run_rl.sh`
- **SG-Nav**：`SG_Nav.py` + `configs/challenge_objectnav2021.local.rgbd.yaml`；MP3D **val 11 景**已够用（不扩全库；不考虑跨楼层集）
- **UniGoal**：`python main.py --goal_type {ins-image|text}`；数据：HM3D + IIN v3 + text-goal（见下）

## 6. 移动机械臂 VLN 适配——接口约束（预先遵守）

完整锚点分析（只读）：`reports/mobile_arm_adaptation_analysis.md`；摘要见 `reports/baseline_validation.md` §7。  
在未明确要求前，不做平台耦合重构。适配须遵守：

1. **保留上游评测入口**：Habitat episode、动作空间、成功判定与 SPL 等指标不被静默改写；平台相关改动放在适配层或配置开关后。
2. **观测对齐**：明确 RGB-D 分辨率、相机外参、深度单位与坐标系（光学系 vs link 系）；参考 NBV 工程中 D455 坐标教训（见 NBV `MEMORY.md`，勿在未验证时照搬）。三套仿真相机假设不同：VLFM/ApexNav **0.88 m/≈0°/79°**；MSGNav **1.5 m/−30°/120°**。
3. **动作接口**：VLFM/ApexNav 为离散 Habitat 动作（ApexNav 另有 look± 与 `/cmd_vel`）；MSGNav 为连续 `set_state` 传送。底盘/臂需经显式封装，禁止在算法核心写死 CR10 关节。执行面优先 REMANI：`/ee_goal`、`/ee_current_pose`、`/planning/finish`（`NBV_Mobilemanipulator/scripts/nbv_to_remani_ee_goal.py`）。
4. **地图与坐标系**：frontier / scene graph 假设的 2D 导航网格与 Ranger 四轮转向运动学不同；适配时单独验证足迹与碰撞。Camera→EE：`T_world_ee = T_world_cam · inv(T_ee_cam)` + `--align-remani-ee`（FK vs TF≈0.42 m Z）。
5. **环视计费**：VLFM 12 步、ApexNav 26 步计入 episode；MSGNav 7 视角**不计步**——实机对比须显式计费。
6. **资源隔离**：推理权重与 HM3D/MP3D 场景只放 D 盘共享目录；容器只挂载需要的子集。

## 7. 已验证的工程结论（本仓库）

| 结论 | 证据 |
|------|------|
| 六套源码已导入，SHA 见 `reports/source_versions.md` / `.json` | 导入记录 + strip 脚本 |
| 嵌套 `.git` 已剥离，umbrella 为唯一 Git | `find baselines -name .git` 为空 |
| 大数据走 `/media/ubuntu/D/VLN_shared`；compose 对 VLFM/MSGNav 挂载同路径以解析绝对软链 | `shared/*_large`；各 `docker-compose.yml` |
| `vln-habitat024/025` 正式镜像可用；六 `vln-*` 容器 Up | `docker images` / `docker ps` |
| VLFM=`BATCH_OK`（8/8 无崩溃；SR=25% SPL=0.1164；峰显存 19356 MiB） | `runs/VLFM/batch_8ep_status.md`；D `.../batch_20261101/VLFM/` |
| MSGNav=`BATCH_OK`（8/8 无崩溃；SR_dist=37.5% SPL≈20.7%；峰显存 16507 MiB） | `runs/MSGNav/batch_8ep_status.md`；D `.../batch_20261101/MSGNav/` |
| ApexNav=`BATCH_OK`（8/8 无崩溃；任务成功 6/8；峰显存 12912 MiB） | `runs/ApexNav/batch_8ep_status.md`；D `.../batch_20261101/ApexNav/metrics.csv`；VLM=`vlm.*` 非 `vlfm.vlm` |
| ApexNav 需 ROS1 Noetic + catkin planner；Jammy 上可用 Focal Noetic 文件树 + focal `.so`，但 `cv_bridge`/py3.8 boost 与 conda py3.9 不兼容 → 适配层手写 Image | 同 status；`habitat2ros/habitat_publisher.py` |
| MSGNav 需 `ollama` 包（即使 `use_ollama:false` 也会 import） | 已 bake 进 `:msgnav-deps` |
| MSGNav 可用 API 模型为 `gpt-5.6-sol`（`gpt-5.5` 404） | 容器内冒烟；密钥仅本地 `.env` |
| ObjectNav HM3D v2 的 `.json.gz` 需解压为 plain JSON 才可被 MSGNav `json.load` | `.../objectnav/hm3d/v2/val/content_json` |
| open3d 与 pydantic v1：需 `dash<3` | VLFM habitat024 commit 镜像 |
| UniGoal `val_text.json.gz` 的 `episodes=[]` 为设计；文本在 `attribute_data`，episode 来自 IIN；`goal_key`=`{scene}_{goal_object_id}` 与 attrs **1000/1000** 对齐 | `datasets/textnav/` + `instance_imagenav/`；代码 `instanceimagegoal_env.py` |
| IIN 磁盘目录名 `instance_imagenav_hm3d_v3`；UniGoal 期望 `hm3d/v3/` → 接线时软链 | `reports/manual_downloads.md` |
| 共享公开大数据无强制待下载项；MP3D 维持 val 11 景 | `reports/manual_downloads.md`（2026-11-02） |
| Ranger+CR10 适配落在 `adapters/habitat_rangercr10/`，不改 baseline 默认配置 | 目录 + compose `vln-rangercr10:bullet` |
| LocoManip 钉扎 `rangercr10-teleop` @ **`ec5fd65`（stage 4.10d）**；PPO `stage410d_ppo/model_5999.pt`；obs=117 act=8 hist=3 @10Hz；stage45j 仅历史对照 | `constants.py`；`VERSION_stage410d.json`；MuJoCo `teleop_eval` |
| 现网 VLN 镜像均 `built_with_bullet=False`；URDF 需专用 bullet 构建 | `habitat_sim.built_with_bullet` |
| EGL 修复后原生 URDF-in-Habitat 可用；混合 Demo 仍作后备 | `run_kinematic_demo.sh`；`reports/habitat_rangercr10_integration.md` |
| URDF Z-up→Habitat Y-up 根旋转必须 `Ry(-π/2)*Rx(-π/2)`，否则底盘倾倒 | `kinematic_demo._urdf_to_habitat`；`up_dot_hab_y≈1` |
| 底盘高度经轮贴地后 `DEFAULT_BASE_Y≈0.4419`（轮半径 0.125） | `kinematic_demo.py`；`snap_wheels_to_floor` |
| ObjectNav 原始起点常不适配完整 Ranger+CR10 → `find_adapted_start`，须标 `adapted_episode` | `spawn_utils.py` |
| Stage **4.10d** 默认臂 `[0.236,0.086,-2.398,-0.830,-1.335,0]`；D455 **顶装** AG95；MuJoCo 光学≈0.88 m，Habitat FK≈0.857 m、水平、near=0 | `ARM_DEFAULT`；`fk_compare_stage410d_*` |
| URDF/D455/PPO **必须共钉扎**；禁止旧侧装 URDF + 新 PPO | `URDF_HABITAT` pin `stage410d_ec5fd65` |
| LOOK：joint3 ±0.6 rad（臂适配）；4.10d 下 INIT/DOWN/UP near≈0 | `camera_view_diag.py` |
| 真实 ApexNav ROS 闭环：孤立 master `:11312`；勿占 NBV `:11311` | `run_apexnav_real_episode.sh` |
| FSM 前 26 步 init lookaround；其后 `callActionPlanner` | `exploration_fsm.cpp` |
| free 过少/NO_PASSABLE：近场遮挡+狭窄出生+膨胀；开阔 ep + 4.10d 可达 free≈180 与多步 FWD | `20261104_114652` vs `real_20261103_124521` |
| Demo 占据图必须订阅 `/grid_map/*`；论文风白底配色 | `map_listener.py`；`map_style.py`；`demo_compose.py` |
| Demo 价值热力复用原生 `/grid_map/value_map`（ApexNav.rviz 黄→红）；仅叠 free；occ 不被覆盖 | `map_listener.render_panel`；`VALUE_*` in `map_style.py` |
| Demo 应按 `sdf_map/resolution`（0.05 m）填充 cell 足迹，避免 1px 散点假边框；不改规划输入 | `map_raster.py`；`habitat_rangercr10_map_raster_fill.md` |
| 环视放射状在原始 `/grid_map` 点云中已存在（稀疏角向采样）；与 1px 可视化空隙需区分 | `compare_map_raster_styles.py` |
| Habitat HFOV=79° 方像素：fx=fy≈388.191，VFOV≈63.45°（**禁止** HFOV×H/W 得 fy） | `camera_model.pinhole_from_hfov`；launch fy=fx |
| Optical→ROS：`R_ros=C@R_optical`（勿用 `C@R@C.T` 发 camera pose）；render=`optical@Rx(π)` | `hab_optical_rot_to_ros`；`mat4_hab_optical_to_ros_pose` |
| `/habitat/odom` 默认真实底盘 XY；旧相机 XY 代理仅 `legacy_camera_xy_proxy` | `ros_dynamic_publisher` |
| ApexNav TURN=π/6≈30° → 水平重叠 **49° ≈ HFOV 的 62%**（勿写「49%」）；旧 VFOV=59.25° 已降级 | `habitat_rangercr10_camera_odom_coord_fix.md` |
| LOOK pitch 用 **joint3 ±0.60**；缺 TURN_DOWN 时高度滤波易清空地图；「未 TURN_DOWN 光轴朝上」**待实际光轴测量验证** | `apexnav_real_episode._execute_action` |
| `planner_first_call_diag` 是 Python 近似，不是 C++ frontier/A* 正式结果 | `planner_first_call_diag.py` 头注释 |
| 原生规划诊断：`exploration/plan_diag_*` → `native_plan_diag.jsonl`；建图流水线 `map_ros/pipeline_diag_*` | 可关；不改决策 |
| a5e291b 后运行时几何验收通过；yr17 30° 可持续探索；修复前 eF36/HY1 底盘起点 UNKNOWN→NO_PASSABLE | `habitat_rangercr10_geomreg_30deg_native_plan.md` |
| GRID_STATE：UNKNOWN=0 FREE=1 OCCUPIED=2；勿把 unknown 拒绝计数当成唯一失败原因 | `sdf_map2d.h`；native plan diag |
| 相机邻域 FREE ≠ 底盘起点 FREE；臂载 D455 相对底盘 XY 偏移 ≈0.65 m | `base_start_unknown_diagnosis.md` |
| 地面带 AGL[0,`filter_min_height`] 原丢弃→`height_other`；适配 `ground_free_ray_enable` 只打 free 射线不写 OCCUPIED | `map_ros`；`SDFMap2D::inputFreeRayCloud2D`；`algorithm_rangercr10.xml` |
| groundfree 后：eF36 起点 FREE+20×EXPLORATION；yr17 对照 OK；HY1 起点仍 UNKNOWN（部分规划后 NO_PASSABLE） | `reports/base_start_unknown_20261106/` |
| 同帧 `inputFreeRayCloud2D` 必须 **merge** `local_update_*`，否则障碍盒外 OCC 本帧不膨胀 | `sdf_map2d.cpp`；`local_update_merge_20261106` |
| 地面 free 仅 AGL≤`ground_free_max_agl`(0.03)+平面；`(max,filter_min]`→低矮 OCC；禁止整段 0–0.28 当地面 | `map_ros`；`ground_free_geometry_20261106` |
| A* `||nbr-start||≤0.25` 跳过安全检查；起点 UNKNOWN 仍成功 ⇒ 依赖该豁免（observe：`path_relied_near_start_exemption`） | `astar2d.cpp`；`hy1_failframe_20261106` |
| 门控后 short3：yr17/eF36 通；HY1 仍首规划 NO_PASSABLE（free@0.3=0）→ 覆盖不足，可另立补视 | `groundgate_short3_20261106` |
| HY1 钉死 spawn 下首规划 NO_PASSABLE 高度可复现（5/5）；首规划前深度帧 ≈54–57 | `hy1_baseline_repeats_20261106` |
| A/B/C 补视：额外 40 帧@4Hz；C=LOOK_DOWN 朝底盘侧地面；**C 相对 B 无改善**，三组均 free@0.3=0 | `hy1_look_abc_20261106` |
| HY1 固定构型：B/C 车体 0–0.6 m 地面均不在 FOV、无有效深度点；最早缺口=观察覆盖；原生 3D z=5/10/20 cm→OCC 正常 | `hy1_chassis_observability_20261106`；`MapROS::diagProcessCloud3DKeepZ` |
| 0.7× half_l≈0.46 m：0–0.3 m 诊断环多在车下；验收用车外带+前向走廊，不等于环带 | `hy1_startup_pose_geometry_20261106` |
| 完整臂搜索：走廊地面几何可见（cand05/06；C 亦可见）；生产平面/离群后走廊端点稀疏（C:62→0）；车下不可见 | 同上；`test_map_cloud_csv_replay` |
| 单帧 MapROS free-ray 候选可进管道，log-odds 端点仍常 UNKNOWN；起点在车下可能仍 UNKNOWN→接口问题另立 | 同上 |
| cand05 静态多帧：走廊 FREE 于 N=5→82 后饱和（跨度~0.25 m）；起点 absent；帧计数以 pipeline `frame_seq` 为准 | `hy1_cand05_static_multiframe_20261106` |
| 走廊地面门控最早损失在 **voxel**（C:62→0；cand05:27→3）；非先被平面/离群清零 | `gate_stage_loss_diag.json` |
| HY1 首规划包围底盘：主因 **UNKNOWN moat**（0–0.3 全 UNKNOWN 且在车下；车外 0.3–0.6 仍以 UNKNOWN 阻断）；非近场 OCC/膨胀；拒绝 unknown≫0、occ/inf=0 | `hy1_surround_nontraversable_20261106`；run `..._hy1_base_rep_v2_r1_20261106_191426` |
| `map_pipeline_diag.start_raw_occ` = **相机格**；`native_plan_diag.start_raw_occ` = **底盘**；二者不可混读 | `map_ros.cpp` pipeline 窗口 |
| 相机偏置已进链路：sensor_pose optical、odom=chassis、射线起点=camera_pos_；legacy 代理关；环视 0→1 同点重投影深度误差 max≈1.8 mm | 同上；`ros_dynamic_publisher` |
| 最近 FREE≈0.52 m > A* 0.25 m 豁免 → 本帧豁免救不了 NO_PASSABLE；禁止据此扩大豁免 | `native_plan_diag`；`astar2d` |
| `startup_prior_mode`：`none`（默认）\|`initial_footprint`；F0=底盘足迹一次生成；仅规划查询放行 F0∩UNKNOWN；不改地图；`initial_footprint` 关闭 0.25 m near-start skip | `astar2d`；`algorithm_rangercr10.xml`；`hy1_startup_prior_20261107` |
| 先验 ≠ 视觉 FREE ≠ 完整足迹安全验收；禁止用扩 F0/恢复半径豁免凑通 | 同上 |
| ObjectNav e2e（24-ep 固定清单）：先验消除 start_blocked（5→0）；b100 下 SR_proxy A 2/24→B 3/24；SPL N/A（无 geodesic）；B 主失败仍 `explore_no_goal`（14/24）→下一步攻目标搜索/停止，不扩 F0 | `reports/startup_prior_e2e_20261107.md`；`ab24_b100_20261107_123427` |
| Ranger ObjectNav 适配成功代理：`planner_stop` ∧ dtg≤1.0 m；官方 SPL 本路径不算 | `summarize_startup_prior_e2e.py` |
| 父 shell 污染 `FORCE_SPAWN_JSON` 会导致错场景；复测脚本须钉死路径 | `run_hy1_baseline_repeats.sh` |
| 豁免反事实须静默检查边+采样，禁止因起点 UNKNOWN 单独置位，禁止污染 reject 计数 | `astar2d.cpp` checkPointSafetySilent |
| GT occ 探针是 navmesh **邻域**审计，不是 precise false-occupied rate | `gt_false_occupied_probe` |
| ITM cosine 须在同帧 RGB-D 之前发布到 `/blip2/cosine_score`，否则 value_map 融旧分 | `apexnav_real_episode` 发布顺序；`value_map2d.cpp` |
| 7fps 离线重渲染勿对已含价值热力的 paper map 做 legacy 重映射 | `demo_7fps_from_run._is_paper_or_value_map` |
| Demo 7 Hz：按真实时间戳插值重渲染，检测/地图内容 hold；勿用 ffmpeg 加速 2 FPS 冒充 | `demo_7fps_from_run.py`；`run_demo_7fps.sh`；`demo_7fps_rates.json` |
| Ranger 底盘碰撞半长/半宽 ≈0.651/0.435 m；外接 R≈0.783 m；ApexNav 默认膨胀 0.18 m **小于** 足迹 | MuJoCo `base_link_col`；`apexnav_rangercr10_frontier_inflation.md` |
| Habitat→ROS odom 航向须 `hab_yaw+π`（与 `(-z,-x)` 位移一致）；否则恒差 180° 导致 TURN_LEFT 空转 | `hab_yaw_to_ros`；`ros_dynamic_publisher.py` |
| ApexNav `optimistic=false` 时未知格进 ESDF 障碍；膨胀↑会进一步吃掉 free | `sdf_map2d.cpp`；足迹对照实验 |
| 适配膨胀档：`INFLATION_PROFILE=legacy018`（默认演示）/ `mid030`（灵敏度）/ `ranger_safe`（0.485 m） | `config/apexnav_rangercr10_overlay*.yaml` |
| 在线 ≥0.30 m 半径即可把开阔图 free 压到 ≈0–1；窄场景 yaw 修复后仍 `NO_PASSABLE` | `real_yawfix_open_mid030_*`；`real_yawfix_narrow_legacy018_*` |
| HM3D val 100 景；ObjectNav-v2 val content 36 与场景对齐；MP3D 11 景可用但本轮未跑 | `scene_datasets/hm3d/val`；`objectnav/hm3d/v2/val/content` |
| Ranger 足迹筛选：重算 navmesh r=0.18/0.435/0.485/0.783；Top 几何场景 HY1、yr17、eF36、LT9、k1cup | `scene_clearance/`；`apexnav_rangercr10_scene_screening.md` |
| 大场景原起点易 NO_PASSABLE；spawn 偏好 clearance≈0.55 m 且 offset≤1.5 m 后 yr17 多步 FWD×6/1.5 m | `spawn_utils.prefer_open_clearance`；`real_wide_yr17_openband_*` |
| Habitat 四轮可视化：4WS+URDF 左右轴符号；臂静止时轮胎冻结；≠轮地动力学 | `kinematic_demo._update_wheels_from_base_delta`；`wheel_kinematics_smoke` |
| spawn 探针须 `update_wheel_joints=False` 并复位轮角，否则大场景易 NaN FK | `spawn_utils.py` |
| Top-5 均可 `entered_callActionPlanner`；多步规划：yr17=SEARCH_EXTREME，eF36=EXPLORATION；HY1/LT9/k1cup 早停 | `top5_openband_compare.json` |
| yr17 legacy018 路径足迹回放 oriented_safe_ratio=0（中心 clearance 降至 <0.435） | `footprint_path_safety/yr17_openband/` |
| 规划成功 ≠ 足迹安全 ≠ 寻物成功；须分三层记录 | `apexnav_rangercr10_top5_explore_safety.md` |
| 适配层整机均匀缩放：`robot_scale`→生成 URDF（xyz+mesh scale）+ 贴地/足迹/相机 AGL 目标；默认 1.0× 不变 | `robot_scale.py`；`scale_urdf.py`；`RangerCr10KinematicEnv` |
| `scaled_robot_proxy_070`：半宽≈0.304 m，相机目标 0.616 m；yr17 足迹 safe_ratio 1.0；不可冒充实机成绩 | `apexnav_rangercr10_scale070.md` |
| 缩尺改善足迹安全 ≠ 自动更长探索；HY1 早停在 0.7× 仍在 | `scale070_compare_batch_*.jsonl` |
| 初始化抬臂：MuJoCo 原生 teleop-PPO（`ee_command_from_offset` Z+≤0.40），Habitat **只同步臂关节**；禁止 IK 替代 | `ppo_mujoco_raise.py`；`run_ppo_raise_then_apexnav_s070.sh` |
| 0.7× FK：抬臂后 TCP AGL≈0.811 m（目标 0.88±0.02 未达）；D455 optical≈0.881 m 且水平（≠TCP） | `ppo_raise_habitat_fk_070.json`；`apexnav_rangercr10_ppo_raise_s070.md` |
| PPO/ApexNav 交接：抬臂完成保持 `arm_q`，再 26 步环视；二者不同时控底盘/臂 | `--ppo_raise_json`；`handover.json` |
| ROS Z 必须发 **AGL**（`hab_y - floor_y`）；绝对 Habitat Y 会使 map_ros 高度滤波错位 | `coord_habitat_ros.hab_pos_to_ros` |
| `/habitat/odom` 默认真实底盘 XY（`odom_xy_mode=chassis`）；旧相机 XY 代理仅 `legacy_camera_xy_proxy` | `ros_dynamic_publisher`（a5e291b 后） |
| Habitat `depth_sensor.min_depth` 会覆盖 `map_ros/depth_filter_mindist`；近距/无效深度须在适配层处理 | 无效→**NaN**（禁改写 5 m/0）；`depth_validity.py` 几何自遮挡；`map_ros` 跳过 NaN |
| 近距改写为 max-range 会在环视中产生虚假占据终点/自由射线 | `habitat_rangercr10_depth_radial_fix.md`；采用 `..._depthfix4_*` |
| catkin 前缀：`/workspace/ApexNav` → `baselines/ApexNav` | devel 路径 |
| HM3D-v2 goals 在 `goals_by_category`；宜滤同层 | `_goals_for_episode` |


## 8. 常见兼容性风险



| 风险 | 说明 | 应对方向 |
|------|------|----------|
| Habitat 小版本分裂 | 见 §4 | 一 baseline 一环境 |
| SG-Nav/UniGoal 挂错镜像 | 文档要 0.2.4 / 0.2.3，compose 暂用 habitat025 | 专用镜像或改映射 |
| MP3D 仅 `.glb` | ObjectNav `DISTANCE_TO_GOAL` → `pathfinder.geodesic_distance` 无 navmesh 会 **segfault** | `scripts/build_mp3d_navmeshes.py` 按 agent r=0.18/h=0.88 重算并落盘 `{id}.navmesh`（自算≠官方，SPL 可能偏差） |
| model8 VLM `image_url` | 传字符串会被网关/兼容层打回 502/超时；OpenAI 兼容需 `{"url":"data:..."}` | UniGoal `src/utils/llm.py`、SG-Nav `scenegraph.py`（对齐 MSGNav） |
| SG-Nav 缺 pytorch3d | `compute_3d_iou_accuracte_batch` import 失败 | 容器 `pytorch3d==0.7.4`（py39/cu118/torch2.0.1） |
| MSGNav open_clip 预训练 | `ViT-H-14-quickgelu`/`dfn5b` 需 HF 大权重；直连常失败 | `HF_ENDPOINT=hf-mirror.com` + D 盘 `HF_HOME` 预拉 |
| `docker compose --force-recreate` | 清掉未 bake 的 pip 层 | 用 `docker commit` tag（如 `:msgnav-deps`）或写入 Dockerfile |
| APRR 子模块不全 | data / detection 未拉全 | 按需补齐 |
| SG-Nav agent 热补丁 | 必须覆盖 habitat-sim `agent.py` | Dockerfile/启动脚本 |
| LLM/API 密钥 | MSGNav 等需在线 LLM | 只用 `.env`（gitignore），勿写入记忆正文 |
| 显存争用 | A6000 ~49GB；他人进程可能占用 | 跑前 `nvidia-smi`；错峰 |
| habitat-sim headless_bullet EGL | 根因常为 `10_nvidia.json` 被清空（0B） | `ensure_egl_icd.sh` 恢复 ICD；勿动宿主机驱动 |
| 原生 URDF 入场 | `vln-rangercr10:bullet` + 物理开启可加载 51+1 links | `run_kinematic_demo.sh` |
| 运动学 vs 动力学 | Demo 为状态写入 | 必须标 `kinematic_state_set`，禁止写成全身动力学 |
| habitat-sim close | 0.3.1 常 rc=134 / heap 噪声 | 以 `summary.status` 判定；脚本接受 0/134 |
| PPO→Habitat 全身控制 | 117-D 观测与 ChassisAction 仍未对齐；勿把力矩/MuJoCo 动作当 Habitat 关节位 | 抬臂仅用 MuJoCo 推理+关节同步；Habitat 探针勿当全身策略成功 |
| teleop Z+ 箱顶 | KEYBOARD_BOX_410 Z_OFFSET_MAX=0.40；再抬需训练侧改箱/策略 | 0.7× 上 TCP 0.88 当前不可达；诚实记录 shortfall |
| 抬臂后 NO_PASSABLE | 高度错位 + 相机/底盘起点分裂 + 自遮挡进 occupied | 见 `apexnav_rangercr10_nopassable_after_ppo_raise.md`；禁 optimistic=true 凑数 |
| ApexNav VLM 离线 | bert/blip2/dino 勿直连 HF | `HF_HOME`/`TORCH_HOME` + `/workspace/ApexNav/bert-base-uncased`；dino 权重用 D 盘实文件 |
| 动态相机 | 不可再用固定 +0.88 m | 适配层发真实 EE SE3；第三人称渲染勿覆盖 EE 观测 |
