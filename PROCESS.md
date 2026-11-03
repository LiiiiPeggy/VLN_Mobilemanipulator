# PROCESS.md — 工程历史

追加有价值的重要事件。完整日志留在 `runs/` / `reports/`，此处只保留摘要。  
格式：日期、模块、问题、操作、实测结果、结论、相关路径或 commit。

---

## 2026-10-29 仓库初始化与源码导入

**模块**：umbrella / baselines  

**问题**：需在单仓管理六套 ObjectNav/VLN baseline，同时与 NBV、LocoManip 等工程共存于同一 A6000 主机。  

**操作**：

- 创建 `/home/ubuntu/locomani/VLN_Mobilemanipulator`，远程 `git@github.com:LiiiiPeggy/VLN_Mobilemanipulator.git`。
- 克隆六套上游到 `baselines/`，记录 SHA 于 `reports/source_versions.md`。
- 配置 `.gitignore`（权重、数据集、缓存、嵌套 `.git`）。
- `shared/{datasets,checkpoints,cache,runs}_large` 软链至 `/media/ubuntu/D/VLN_shared/...`（根分区空间紧张）。

**实测结果**：

- SHA 与报告一致（见 `reports/source_versions.json`）。
- 宿主机：Ubuntu 22.04.5、RTX A6000、Driver 550.163.01、Docker 27.3.1。
- 他人容器 `nbv_fkie` 等仍在运行；未改动。

**结论**：导入阶段完成；**不等于**任何 baseline 可运行。大数据必须走 D 盘。

**相关**：`reports/source_versions.md`、`.gitignore`、`shared/`

---

## 2026-10-29 剥离嵌套 .git

**模块**：Git  

**问题**：各 baseline 自带 `.git`，与 umbrella 冲突；且 `.gitignore` 的 `**/.git/` 会使嵌套历史无法被 umbrella 跟踪源码。  

**操作**：编写并执行 `scripts/strip_nested_git.py`（先记录 SHA，再删除 `baselines/*` 下嵌套 `.git`）。  

**实测结果**：`find baselines -name .git` 为空；写出 `reports/source_versions.json`。  

**结论**：源码改由 umbrella 单一 Git 管理；上游 URL/SHA 以 `reports/source_versions.*` 为准。若需再同步上游，应重新 clone 到临时目录后按文件同步，而不是恢复嵌套仓库。  

**相关**：`scripts/strip_nested_git.py`、`reports/source_versions.json`

---

## 2026-10-29 Docker 脚手架（未 build）

**模块**：Docker  

**问题**：六套 Habitat/PyTorch 版本互斥，需独立 compose，并允许共享兼容镜像。  

**操作**：新增

- `shared/docker/Dockerfile.habitat024`（VLFM 类，CUDA 11.7 + torch 1.12）
- `shared/docker/Dockerfile.habitat025`（MSGNav 类，CUDA 11.8 + torch 2.0 + habitat-sim 0.2.5）
- `shared/docker/Dockerfile.apexnav`（ApexNav，CUDA 12.1 + torch 2.5）
- `shared/docker/Dockerfile.lite`（APRR 等轻量审计）
- 六个 `baselines/<Name>/docker-compose.yml`（独立 `name:` / `container_name: vln-*`）

**实测结果**：文件就位；`docker images` **无** `vln-*`；**无**对应容器。Dockerfile 中部分 `pip install ... || true` 表明依赖安装仍是草稿。  

**结论**：仅达到「编排草稿」，未达 `CONTAINER_READY`。SG-Nav（文档 0.2.4）与 UniGoal（文档 0.2.3）暂挂 `vln-habitat025`，**版本映射待校正**后再 build。  

**相关**：`shared/docker/`、`baselines/*/docker-compose.yml`、`PROGRESS.md`

---

## 2026-10-29 建立轻量工程记忆

**模块**：文档 / Agent 协作  

**问题**：多会话 Cursor 需恢复进度、避免重复安装与误改 NBV/他人环境。  

**操作**：按 NBV_Mobilemanipulator 同构四文件落地 `AGENTS.md`、`MEMORY.md`、`PROGRESS.md`、本文件；内容以当时代码/Git/Docker/磁盘证据为准，不把计划写成完成。  

**实测结果**：四文件可读；与 `baselines/`、`shared/docker/`、空 `runs/`、无 `vln-*` 镜像一致。  

**结论**：后续会话任务开始必读 `AGENTS.md` + `PROGRESS.md`；状态变更只改变化项。  

**相关**：四记忆文件；参照 `/home/ubuntu/locomani/NBV_Mobilemanipulator/AGENTS.md`

---

## 2026-10-31 habitat025 libOpenGL + VLFM 软链挂载 / 单 episode

**模块**：Docker / VLFM / MSGNav  

**问题**：

1. `habitat_sim` 0.2.5 容器缺 `libOpenGL.so.0`。  
2. VLFM `data/*` 大量绝对软链指向 `/media/ubuntu/D/VLN_shared/...`，容器内原先未挂载同路径导致场景/权重解析失败；GroundingDINO 权重链还二次指向未挂载的 NBV 路径。  
3. `docker compose --force-recreate` 会清掉此前装在可写层的 VLFM 运行时 pip 包。

**操作**：

- `Dockerfile.habitat025` 增加 `libopengl0` / `libglvnd0` / `libgles2`；`DOCKER_BUILDKIT=1 docker build --network=host`（空 proxy build-args）→ `vln-habitat025:build` 再 tag `latest`；recreate `msgnav`（及 sgnav/unigoal）。  
- VLFM compose 增加 `- /media/ubuntu/D/VLN_shared:/media/ubuntu/D/VLN_shared`；GD 权重改挂 `/shared/weights/grounding_dino`。  
- 本地克隆 git 依赖到 `D/.../cache/vlfm_src` 后容器内 `pip install -e`；离线补 `bert-base-uncased` / `blip2_pretrained.pth` / `eva_vit_g.pth`；四 VLM 后台进程日志落 `D/.../runs/VLFM/vlm_servers/`。  
- `python -m vlfm.run habitat_baselines.test_episode_count=1`。

**实测结果**：

- habitat025 rebuild **EXIT:0**（`runs/_build/habitat025_rebuild.log`）；smoke：`habitat_sim 0.2.5` + `libOpenGL.so.0 OK`。  
- VLFM 单 episode **EXIT:0**；SR=0（`false_positive`）；日志 `/media/ubuntu/D/VLN_shared/runs/VLFM/single_episode_20261031_234730.log`；摘要 `runs/VLFM/single_episode_20261031_234730_summary.md`。

**结论**：025 OpenGL 与 VLFM 路径挂载问题已关闭；VLFM 升至 `SINGLE_EPISODE_OK`（任务成功与否另计）。运行时依赖需 bake 进镜像以免 recreate 丢失。

**相关**：`shared/docker/Dockerfile.habitat025`、`baselines/VLFM/docker-compose.yml`、`runs/_build/habitat025_rebuild.log`、`runs/VLFM/`

---

## 2026-11-01 VLFM deps bake-in + ApexNav Dockerfile 对齐

**模块**：Docker / VLFM / ApexNav

**问题**：VLFM 运行时包在 recreate 后丢失；open3d 拉 dash 4.x 与 pydantic 1.x 冲突；ApexNav 仍为占位镜像。

**操作**：

- `docker commit` `vln-vlfm` → `vln-habitat024:latest`/`build`（含 runtime deps + `dash<3`）。
- 确认 VLM 12181–12184；重跑单 episode；摘要 `runs/VLFM/single_episode_status.md`。
- `Dockerfile.apexnav` 对齐 024/025（空 proxy、Aliyun apt/pip、libopengl0/libglvnd0、跳过 lavis）；后台 `docker build -t vln-apexnav:build`。

**实测结果**：

- 镜像 ID `fe6b1ca643fd`；单 ep 再确认 EXIT:0 / SR=0 false_positive（`single_episode_20261101_001121.log`）。
- ApexNav build 拉取 CUDA base 中（见 `runs/_build/apexnav_build.log`）。

**结论**：VLFM 依赖已固化进 habitat024；ApexNav 正式构建进行中。

**相关**：`shared/docker/Dockerfile.apexnav`、`runs/VLFM/single_episode_status.md`

---

## 2026-11-01 MSGNav deps + API + 单 episode 阻塞于 open_clip

**模块**：MSGNav / Docker / API

**问题**：MSGNav 需 HiPart/pytorch3d/CLIP、HM3D 路径、LLM API；上游 `const.py` / `explore_utils_concept.py` 含占位或硬编码密钥；ObjectNav 官方为 `.json.gz` 而评测用 `json.load`；单 ep 还需 open_clip DFN5B 权重。

**操作**：

- 容器内装 deps 后 `docker commit` → `vln-habitat025:msgnav-deps`；compose 钉该 tag，并挂载 `/media/ubuntu/D/VLN_shared` + `env_file: .env`。
- 密钥改为环境变量；删除源码中硬编码 key；`.env.example` 入库；冒烟确认 `gpt-5.6-sol`（`gpt-5.5` 404）。
- 修正 `cfg/eval_hm3d.yaml` 场景/episode/SAM 路径；新增 `cfg/eval_hm3d_single_ep.yaml`；gunzip ObjectNav content → D 盘 `content_json`。
- 跑 `run_hm3d_evaluation.py -cf cfg/eval_hm3d_single_ep.yaml --specific 0`。

**实测结果**：

- deps/API：`runs/MSGNav/deps_status.md`（hipart/pytorch3d/clip OK；API OK）。
- 单 ep：YOLO/SAM 加载成功；`open_clip` 拉 `apple/DFN5B-CLIP-ViT-H-14` 时 `huggingface.co` `Network is unreachable` → EXIT:1（`runs/MSGNav/single_episode_status.md`）。
- 缓解：容器内 `HF_ENDPOINT=https://hf-mirror.com` 预拉至 `/shared/cache/huggingface`（下载进行中，未完成前不得宣称 MODEL_LOADED）。

**结论（当时）**：MSGNav=`DEPENDENCIES_READY`；单 ep 一度阻塞在 open_clip 权重拉取。后续用 HF 镜像预拉后已跑通（见下条）。

**相关**：`baselines/MSGNav/`、`runs/MSGNav/deps_status.md`、`runs/MSGNav/single_episode_status.md`

---

## 2026-11-01 MSGNav 单 episode 跑通

**模块**：MSGNav  

**问题**：上一轮 open_clip DFN5B 直连 HuggingFace 失败。  

**操作**：`HF_ENDPOINT=https://hf-mirror.com` + `HF_HOME=/shared/cache/huggingface` 预拉；停 VLFM VLM 腾 GPU；`run_hm3d_evaluation.py -cf cfg/eval_hm3d_single_ep.yaml --specific 0`。  

**实测结果**：EXIT:0；场景 `zt1RVoi7PcG` / chair；SR/SPL=0（miss，非崩溃）；日志 `.../single_episode_20261101_012834.log`。  

**结论**：MSGNav → `SINGLE_EPISODE_OK`。API 用 `gpt-5.6-sol`（本地 `.env`）。  

**相关**：`runs/MSGNav/single_episode_status.md`

---

## 2026-11-01 ApexNav 正式镜像 rebuild（numpy pin）

**模块**：ApexNav / Docker

**问题**：`habitat-baselines` 把 numpy 升到 2.0.2/1.26.4，habitat-sim 0.3.1 import 崩；另 GitHub `git clone` TLS 失败。

**操作**：

- `Dockerfile.apexnav`：本地 tarball `COPY` habitat-lab v0.3.1；`pip install -e habitat-baselines --no-deps` + 手工 deps（`moviepy==1.0.3`）；`--force-reinstall --no-deps numpy==1.23.5 numba==0.60.0`。
- build → tag `:latest` → `compose up -d --force-recreate` → smoke。

**实测结果**：

- EXIT:0；镜像 `118284656358`（24.2GB）；smoke `1.23.5 0.3.1 2.5.0+cu121 True`。
- 状态 → `DEPENDENCIES_READY`。

**结论**：正式 ApexNav 镜像可用；应用权重/VLM/单 ep 仍待做。

**相关**：`shared/docker/Dockerfile.apexnav`、`runs/_build/apexnav_status.md`、`runs/_build/apexnav_rebuild.log`

---

## 2026-11-01 ApexNav 单 episode（ROS + VLM）

**模块**：ApexNav

**问题**：评测硬依赖 ROS1 Noetic + catkin `exploration_manager`；正式镜像为 Jammy、无 ROS；绝对软链需挂 `/media/ubuntu/D/VLN_shared`；Noetic `cv_bridge` 需 py3.8 boost，与 conda py3.9 冲突。

**操作**：

- compose 增加同路径挂载；补 mp3d `v1` 软链；装 LAVIS/GD/MobileSAM（`transformers==4.26.1`，numpy 钉死）。
- 从 **`nbv-fkie:noetic` 镜像**（非运行中容器）拷 `/opt/ros/noetic` + focal `.so`；`catkin_make` 出 `exploration_node`。
- VLM 12181–84 离线 HF bert；`habitat_publisher` 改为手写 `sensor_msgs/Image`（免 cv_bridge）。
- `habitat_evaluation.py --dataset hm3dv2 test_epi_num=0`；`docker commit` → `:single-ep-deps`。

**实测结果**：

- bed episode **Result: success**；SR=100%、SPL=70.06%、SoftSPL=69.35%、dtg=0.0556。
- 镜像 `50e76a268b26`；日志 `runs/ApexNav/single_episode_20261101_retry4.log`；`nbv_*` 未动。

**结论**：ApexNav → `SINGLE_EPISODE_OK`。Jammy+Focal Noetic 叠法可跑通但脆弱，长期宜专用 ROS/Noetic 基座 Dockerfile。

**相关**：`runs/ApexNav/single_episode_status.md`、`baselines/ApexNav/habitat2ros/habitat_publisher.py`、`baselines/ApexNav/docker-compose.yml`

---

## 2026-11-01 移动机械臂适配只读分析（VLFM/ApexNav/MSGNav）

**模块**：适配规划 / reports

**问题**：三套 `SINGLE_EPISODE_OK` 后需明确接 RangerBox-CR10（EE-D455 + REMANI）的代码锚点与最小改动面，避免误改上游评测协议。

**操作**：只读追踪三套 camera→state→action→stop；对照 `NBV_Mobilemanipulator` REMANI 接口与 `LocoManip_Lab` TCP（未改相邻仓）。

**实测结果（分析结论）**：

- VLFM：0.88 m/0°；12 步环视计费；STOP ρ&lt;0.9 vs Habitat success 0.1。
- ApexNav：0.88 m 硬编码；26 步 init 计费；habitat2ros topic 为最低成本实机钩子；success 0.2。
- MSGNav：1.5 m/−30°；连续 `set_state`；7 视角环视不计步；success 1.0 m。
- REMANI：`/ee_goal` + align FK/TF≈0.42 m Z；无 collision bool。

**结论**：优先 ApexNav topic 替换 → VLFM adapter → MSGNav 执行器；详见报告（**未实现**）。

**相关**：`reports/mobile_arm_adaptation_analysis.md`、`reports/baseline_validation.md` §7

---

## 2026-11-01 三套主线固定 8-ep 小批量（BATCH_OK）

**模块**：VLFM / ApexNav / MSGNav 评测 harness

**问题**：单 ep 通过后需可复现小批量；ApexNav 脚本误用 `vlfm.vlm`；MSGNav `NN_<scene>.json` 与 `listdir`+`shuffle` 导致 `--specific` 错位/崩溃；沙箱写 D 盘需容器内 runner。

**操作**：

- 容器确认：`vln-apexnav:single-ep-deps`、`vln-habitat024:latest`=`fe6b1ca643fd`、`vln-habitat025:msgnav-deps`。
- ApexNav：改用 `python -m vlm.{detector,itm,segmentor}.*`；`run_batch8_inner.sh`；ep0 校验后跑 0..7。
- VLFM / MSGNav：同模式容器内 runner；MSGNav 修 sorted/`--specific` 跳过 shuffle、剥离数字前缀；成功判定对齐 `Success rate by distance: 100.00`。
- 顺序独占 GPU：ApexNav → VLFM → MSGNav。

**实测结果**：

| Baseline | 完成/崩溃 | 任务成功 | SR / SPL | 峰显存 |
|----------|-----------|----------|----------|--------|
| ApexNav | 8/0 | 6/8 | 75% / ~58% mean | 12912 |
| VLFM | 8/0 | 2/8 | 25% / 0.1164 | 19356 |
| MSGNav | 8/0 | 3/8 | 37.5% / ~20.7 | 16507 |

证据：`runs/*/batch_8ep_status.md`；D `.../runs/batch_20261101/`。

**结论**：三套均 `BATCH_OK`（≥5/8 无崩溃）。任务 SR 偏低属算法/API 质量，非基础设施失败。

**相关**：`scripts/run_*_batch8.sh`、`baselines/*/run_batch8_inner.sh`、`reports/baseline_validation.md` §1–4

---

## 2026-11-02 共享数据缺口关闭（UniGoal / SG-Nav）

**模块**：`/media/ubuntu/D/VLN_shared` 数据集盘点

**问题**：清单曾把 UniGoal text-goal、instance 权限、全量 MP3D 标为待办；需按用户决策收敛。

**操作 / 核实**：

- 用户重下并替换 `datasets/textnav/val/val_text.json.gz`（mtime 2026-11-02）；`episodes=[]` 但 `attribute_data`=795。对照 UniGoal 代码：text 模式仍跑 IIN episode，按 `goal_key` 取文本 → **空 episodes 正常**；与 IIN val 1000 ep 的 `goal_key` 全对齐。
- instance_imagenav：用户已 `chmod`；宿主机可读；content=36。
- MP3D：维持现有 11 个 val `.glb`（对齐 objectnav mp3d val）；**不下载全库**；**不考虑跨楼层数据集**。

**结论**：公开大数据强制下载项清空；SG-Nav/UniGoal 下一阶段是 Habitat 版本对齐与挂载/软链，不是缺文件。

**相关**：`reports/manual_downloads.md`、`PROGRESS.md`、`MEMORY.md` §7

---

## 2026-11-02 Habitat Ranger+CR10 运动学 Demo（混合路径）

**模块**：`adapters/habitat_rangercr10/`

**问题**：要在现有 Habitat HM3D 中做 Ranger+CR10 可视化/运动/末端 RGB-D，且不破坏已通过 baseline。现网镜像均无 Bullet；URDF 需要 Bullet。

**操作**：

1. 自 `vln-apexnav:single-ep-deps` 克隆 `vln-rangercr10`，conda 安装 `habitat-sim=0.3.1=*headless_bullet*` → `built_with_bullet=True`，commit 为 `vln-rangercr10:bullet`（不覆盖 baseline tag）。
2. Bullet 容器 Windowless EGL 失败；`vln-apexnav` nobullet 仍可渲场景。
3. 交付混合 Demo：宿主机 MuJoCo（`env_isaaclab5`）FK+机器人网格；`vln-apexnav` 读 `fk_poses.json` 渲 EE RGB-D；拼图落 D 盘。
4. MuJoCo Teleop PPO smoke：117/8/3hist，`model_5999.pt` @ `1973cb4`。
5. ApexNav 闭环代码骨架保留，本轮 `deferred`。

**结论**：最低验收（入场/运动/动态相机）以**运动学混合 Demo**达成；不得写成全身动力学。URDF-in-Habitat 与 ApexNav 闭环待 EGL 修复。

**相关**：`reports/habitat_rangercr10_integration.md`、`runs/habitat_rangercr10/INDEX.md`

---

## 2026-11-03 EGL ICD 修复与原生 Habitat URDF

**模块**：`vln-rangercr10:bullet` + `adapters/habitat_rangercr10`

**问题**：Bullet 容器 Windowless EGL 失败，URDF 无法在 Habitat 内可视化。

**根因**：对比 `vln-apexnav` 后发现 `/usr/share/glvnd/egl_vendor.d/10_nvidia.json` 在 rangercr10 中为 **0 字节**（疑似 conda 换 headless_bullet 副作用）；GPU/capabilities 本身正常。

**操作**：

1. 恢复 ICD JSON；加入 `ensure_egl_icd.sh`；`docker commit` 更新 `vln-rangercr10:bullet`（不碰 baseline 镜像）。
2. 最小 RGB-D 通过后加载 URDF（52 links），跑 `kinematic_demo`（运动学）。
3. `apexnav_bridge` 有界脚本闭环（ApexNav 动作 ID + EE 反馈）。
4. PPO Habitat 探针明确 `probe_only_not_integrated`；权重仍 `model_5999.pt`。
5. 脚本以 `summary.status` 验收，容忍 close() rc=134。

**结论**：EGL→原生机器人/相机→ApexNav 运动学闭环 已独立达成；PPO 迁移另案。

**相关**：`reports/habitat_rangercr10_integration.md`

---

## 2026-11-03 真实 ApexNav planner → Ranger+CR10 多步闭环

**模块**：`adapters/habitat_rangercr10`

**问题**：需用真实 ApexNav 感知/地图/规划驱动 Habitat 中 Ranger+CR10，且初始 D455≈0.88 m 水平朝前（URDF FK）。

**操作**：

- 适配层：`ros_dynamic_publisher`（分开发布 base/EE）、`pointcloud_dynamic`、`apexnav_real_episode`、`initial_camera_pose`；`ARM_APEXNAV_INIT` 关节搜索钉扎。
- 孤立 ROS master `:11312`（不碰主机 NBV `:11311`）；rangercr10 内 `ln -sfn` `/workspace/ApexNav`；VLM 用本地 HF/TORCH cache + bert 目录软链；groundingdino 权重改为 D 盘实文件。
- 跑有界 Episode：HM3D TEEsavR23oF / chair，max_steps=12。

**实测结果**：

- 运行 `real_20261103_120649`：`scripted_policy_used=false`，12 个 `/habitat/plan_action`，ITM 有值，终止 `step_budget_exhausted`，未宣称成功。
- 初始相机 AGL≈0.870 m，角误差&lt;5°；LOOK 标明臂适配。
- `Simulator.close()` 仍可能 abort；任务以 summary 为准。
- 中心 patch 点云“一致性”随运动漂移≈步长，仅作代理诊断，非正式静态路标跟踪。

**结论**：最低验收（真实 planner 多步寻物尝试 + 可复现证据）达成；非 PPO、非批量 benchmark。

**相关**：`reports/habitat_rangercr10_integration.md`、`.../apexnav_real/real_20261103_120649/`

---

## 2026-11-03 姿态修复 + 论文风 Demo + 正式规划阶段

**模块**：`adapters/habitat_rangercr10`

**问题**：Demo 中机器人倾倒/穿模；第三人称易被挡；布局缺在线占据图；先前 12 步仅 FSM 初始化环视。

**操作**：

1. 根因：缺 Z-up→Y-up 根旋转 → 加 `Ry(-90)*Rx(-90)`；轮贴地 `snap_wheels_to_floor`；`find_adapted_start` 避开床柜（标 adapted）。
2. 第三人称后上方跟随 + 距离/高度回退避墙；`demo_compose` 16:9；`map_listener` 订阅 `/grid_map/*`。
3. `max_steps≥36`；phase 区分 `init_lookaround` / `explore_planner`；重标定 `ARM_APEXNAV_INIT`。

**实测结果**（`real_20261103_124521`）：

- 直立：`up_dot_hab_y=1.0`，轮高差≈1.6 mm；出生偏移≈1.8 m，`adapted_episode=true`。
- 26 步 init + 1 步 explore：`callActionPlanner` 返回 `NO_COVERABLE_FRONTIER`→STOP；地图有 occupied/free/unknown 消息。
- Demo：`demo/apexnav_ranger_paper_demo.mp4`；未宣称寻物成功。

**结论**：姿态与 Demo 验收达标；正式规划已进入但本场景 frontier 不足早停——后续换开阔 Episode 验证多步 FWD。

**相关**：`reports/habitat_rangercr10_integration.md`、`.../apexnav_real/real_20261103_124521/`、`.../pose_fix_20261103/`
