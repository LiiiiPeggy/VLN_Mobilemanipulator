# VLN Baseline Validation Report

主机：A6000（Driver 550.163.01 / CUDA 12.4，约 49 GiB）  
工作区：`/home/ubuntu/locomani/VLN_Mobilemanipulator`  
共享大文件：`/media/ubuntu/D/VLN_shared/`  
远端：`git@github.com:LiiiiPeggy/VLN_Mobilemanipulator.git`  
更新：2026-11-01（三套主线 `BATCH_OK`）

## 1. 源码版本与容器状态

| 算法 | Commit | 容器 | 镜像（当前） | 状态 |
|------|--------|------|--------------|------|
| VLFM | `584ed560…` | `vln-vlfm` Up | `vln-habitat024:latest`=`fe6b1ca643fd` | **`BATCH_OK`** |
| ApexNav | `049971b6…` | `vln-apexnav` Up | `vln-apexnav:single-ep-deps`=`50e76a268b26` | **`BATCH_OK`** |
| MSGNav | `03681a17…` | `vln-msgnav` Up | `vln-habitat025:msgnav-deps`=`1b1bdc94f963` | **`BATCH_OK`** |
| APRR | `046c9c24…` | `vln-aprr` Up | `vln-lite:latest` | `CONTAINER_READY` |
| SG-Nav | `d56863c9…` | `vln-sgnav` Up | `vln-habitat025:latest`（版本待对齐 0.2.4） | `CONTAINER_READY` |
| UniGoal | `e2c6d456…` | `vln-unigoal` Up | `vln-habitat025:latest`（文档要 0.2.3） | `CONTAINER_READY` |

说明：六个 compose 独立；GPU 在容器内可见。嵌套上游 `.git` 已剥离。版本机读：`reports/source_versions.json`。

## 2. Docker 镜像复用

| 镜像名 | 构建/来源 | 使用者 |
|--------|-----------|--------|
| `vln-lite` | `Dockerfile.lite` / pytorch 2.3.1 cu121 | APRR（审计） |
| `vln-habitat024` | `Dockerfile.habitat024` + VLFM deps commit `fe6b1ca643fd`（19 GB） | VLFM |
| `vln-habitat025` | `Dockerfile.habitat025` `ff049f5c4eed`；MSGNav extras `:msgnav-deps`=`1b1bdc94f963` | MSGNav（及暂挂 sgnav/unigoal） |
| `vln-apexnav` | `Dockerfile.apexnav` build `118284656358` + 单 ep 运行时 commit `:single-ep-deps`=`50e76a268b26`（28.2 GB） | ApexNav |

启动（勿 `--force-recreate` 冲掉未 bake 层；用已 pin 的 tag）：

```bash
cd /home/ubuntu/locomani/VLN_Mobilemanipulator
docker compose -f baselines/VLFM/docker-compose.yml up -d --no-build
docker compose -f baselines/ApexNav/docker-compose.yml up -d --no-build
docker compose -f baselines/MSGNav/docker-compose.yml up -d --no-build
```

批量入口：`scripts/run_{apexnav,vlfm,msgnav}_batch8.sh`（容器内 `baselines/*/run_batch8_inner.sh`）。

## 3. 权重与数据

### 已具备（共享目录）

- GroundingDINO、MobileSAM、YOLOv7-e6e、PointNav（链到 VLFM/ApexNav `data/`）
- HM3D val 场景 + ObjectNav v1/v2；MSGNav SAM-L、CLIP ViT-H（HF mirror 缓存）
- `scripts/verify_shared_assets.sh` → ok=11 miss=0（以实测为准）

### 仍缺 / 注意

- SG-Nav：MP3D + GLIP；UniGoal：instance-image-goal 等
- MSGNav LLM：密钥仅 `baselines/MSGNav/.env`；模型 `gpt-5.6-sol`（`model8.run` 可能 502）
- 大文件一律 `/media/ubuntu/D/VLN_shared/`

详见 [`manual_downloads.md`](manual_downloads.md)。

## 4. 第一批仿真（VLFM / ApexNav / MSGNav）

固定小批量目录：`/media/ubuntu/D/VLN_shared/runs/batch_20261101/{ApexNav,VLFM,MSGNav}/`  
摘要：`runs/<Name>/batch_8ep_status.md` / `single_episode_status.md`

| 算法 | 单 Episode | 小批量（8） | 峰显存 | 备注 |
|------|------------|-------------|--------|------|
| VLFM | OK（SR=0 false_positive） | **BATCH_OK** 8/8 无崩溃；SR=25% SPL=0.1164 | 19356 MiB | `vlfm.vlm` 12181–84；`test_episode_count=8` |
| ApexNav | OK（bed SR=100 SPL=70.06） | **BATCH_OK** 8/8 无崩溃；任务成功 6/8（SR=75%） | 12912 MiB | ROS+`exploration_node`；VLM=`python -m vlm.*`（非 vlfm） |
| MSGNav | OK（chair miss EXIT:0） | **BATCH_OK** 8/8 无崩溃；SR_dist=37.5% SPL≈20.7% | 16507 MiB | `eval_hm3d_batch8.yaml`；API 有 502/timeout 重试 |

## 5. 轻量审计摘要

见 [`lightweight_audit.md`](lightweight_audit.md)。入口均已在容器内确认：`runb.sh`/`run_rl.sh`、`SG_Nav.py`、`main.py`。

## 6. 资源快照

- 磁盘：根分区约 91% 用；大文件放 D 盘（~1.9 TiB 可用）
- GPU：有其它用户进程占用数 GB；本任务容器默认 `sleep infinity`，未抢占训练
- 未改动 FKIE/SSMI/REMANI 与其它项目容器

## 7. 移动机械臂接口（代码锚点，2026-11-01）

完整只读分析：[`mobile_arm_adaptation_analysis.md`](mobile_arm_adaptation_analysis.md)。相邻接口参考 `NBV_Mobilemanipulator`（REMANI）/`LocoManip_Lab`/`agx`（**未改**）。

### 7.1 三套 I/O 锚点

| 项 | VLFM | ApexNav | MSGNav |
|----|------|---------|--------|
| RGB-D 入口 | `vlfm/policy/habitat_policies.py` `_cache_observations`（~173–237）：`rgb`/`depth` | `habitat_evaluation.py` + `habitat2ros/habitat_publisher.py`（~/habitat/camera_*） | `src/multimodal_3d_scene_graph.py` `get_observation`：`color_sensor`/`depth_sensor` |
| 状态 | `gps`(2D)+`compass`；`camera_height`←sensor.position[1] | `gps`(3D)+`compass`+`camera_pitch`；odom/sensor_pose | 绝对 `(pts,yaw)`（无 GPS 传感器） |
| 动作 | 离散 0–3（`TorchActionIDs`）；Spot 实机为线/角速度 | 离散 0–5（含 look_up/down）经 `/habitat/plan_action`；可选 `/cmd_vel` | **连续** `(pts,yaw)` via `tsdf_planner.agent_step`（`set_state` 传送） |
| 停止/成功 | 策略 `ρ<0.9`→STOP；Habitat **success_distance=0.1** | Planner `REACH_DISTANCE=0.20`→STOP；Habitat **0.2** | VLM end + 测地距 **&lt;1.0 m**（`cfg/eval_hm3d.yaml`） |
| 相机假设 | **0.88 m / 0° / HFOV79° / 640×480** | **0.88 m**（多处硬编码）/ 可变 pitch±30° / 79° | **1.5 m / −30° / HFOV120° / 1280²** |
| 环视计费 | **计入**：12×`TURN_LEFT` | **计入**：26 步 init（DOWN+12L+UP+12L） | **不计步/不计路径**：每步 7 视角 `set_state` |

### 7.2 几何与 REMANI 执行面

- 共性：`T_world_camera = T_world_base × T_base_ee(q) × T_ee_camera`；三套仿真均把相机当 base 刚体。
- EE 目标：`T_world_ee = T_world_cam · inv(T_ee_cam)`（`NBV/.../nbv_to_remani_ee_goal.py`）；必须 `--align-remani-ee`（`/ee_current_pose` 相对 TF `cr10_Link6` ≈ **−0.42 m Z**）。
- 推荐 topics：RGB-D `/realsense/{rgb,depth}/image_raw`（optical=`d455_depth_optical_frame`）；状态 `/ee_current_pose`+`/mm/car/odom`；指令 `/ee_goal`；反馈 `/planning/{start,finish}`（无专用 collision bool）。
- **最低成本替换**：ApexNav topic remap；其次 VLFM Reality/HabitatMixin 适配层；MSGNav 需新建连续目标执行器并给环视显式计费。
- 4070 8GB：多 VLM 需顺序加载/量化（待实机验证，非本报告结论）。

## 8. 未解决问题

1. SG-Nav / UniGoal Habitat 版本与数据对齐  
2. MSGNav API 稳定性（`model8.run` 502）与更大 val 规模  
3. ApexNav 长期 ROS 基座镜像（Jammy+Focal 叠法脆弱）  
4. APRR 百度权重可用性 / 完整评测栈验证 

## 9. 后续建议保留的 baseline（暂定）

待第一批实跑后定稿；倾向 **VLFM**（接口清晰、零样本类别导航）、**ApexNav**（ROS/真机示例）、**MSGNav 或 UniGoal**（场景图 + 语言目标，视 API/数据成本）。
