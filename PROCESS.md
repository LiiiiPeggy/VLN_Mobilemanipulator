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

---

## 2026-11-03 相机 FK / LOOK / free-space（不接新 PPO）

**模块**：`adapters/habitat_rangercr10`

**问题**：需区分初始视角错误 vs LOOK 遮挡；核对 LocoManip 新默认臂；解释 ApexNav free≈0。

**操作**：

- 只读 LocoManip HEAD `b0a536f` 的 `ARM_DEFAULT`（stage 4.10）；**不改**其训练、**不换** stage45j 权重。
- Habitat 诊断 `camera_view_diag.py`：对比 legacy / 4.10 / 旧搜索构型；INIT vs TURN_DOWN/UP。
- LOOK 改为 joint3（j5 在 L410 俯仰增益≈0）；符号按实测标定。
- 适配层 `ARM_DEFAULT`/`ARM_APEXNAV_INIT` 同步为 4.10 默认；光学高度容差放宽（TCP 0.88 vs D455≈0.78）。

**实测**：

- 4.10：光学水平，AGL≈0.78 m，near≈1.9%；DOWN near≈56%（执行诱发）；UP near≈1.9%。
- 先验闭环 free≈6 → NO_COVERABLE_FRONTIER：近场遮挡 + 狭窄出生 + frontier 空。

**结论**：初始视角以 4.10 默认为准；不因凑 0.88 光学高度改回搜索怪姿。新 PPO 另案钉扎。

**相关**：`.../camera_view_diag_20261103_132939/`、`reports/habitat_rangercr10_integration.md`

---

## 2026-11-04 Stage 4.10d 共钉扎 + MuJoCo PPO + ApexNav 多步探索

**模块**：`adapters/habitat_rangercr10` / LocoManip 只读同步

**问题**：需用 Stage 4.10d（顶装 D455 + 新默认关节 + `stage410d_ppo`）替换旧侧装/中间构型与 stage45j 混用；修复 LOOK/地图 free；争取真实多步探索。

**操作**：

1. 只读核对 LocoManip `rangercr10-teleop` @ `ec5fd65` / HEAD `2d6d1f5`；同步 URDF 到 D 盘 pin + `VERSION_stage410d.json`；`constants.ARM_DEFAULT` 对齐。
2. MuJoCo：`teleop_eval` drift/modes/coverage(`4.10`) + `check_self_collision --box 4.10`（不改训练代码）。
3. Habitat：`camera_view_diag`；FK 对比 Hab≈0.857 vs MuJoCo≈0.880；LOOK joint3；高度容差 2.5 cm；禁止高度追逐。
4. ApexNav：spawn 接触阈值放宽；默认更开阔 `Dd4bFSTQ8gi` eid=5；ROS `:11312`。
5. PPO–Habitat 探针改钉 stage410d，明确非成功。

**实测结果**：

- MuJoCo PPO 短测产物：`ppo_stage410d_mujoco_20261104_113929/`。
- 相机：INIT/DOWN/UP near=0；mosaic/report 落盘。
- TEEsav：free≈169 但仍 `NO_PASSABLE_FRONTIER`（1 explore STOP）。
- Dd4bFSTQ8gi：50 步，explore 24（MOVE_FORWARD×4 + TURN_LEFT×20），`step_budget_exhausted`；Demo mp4 已生成。
- PPO→Habitat：仍 blocked_by_observation_mismatch。

**结论**：P0/P1 达成；P2 在开阔 ep 达成真实多步规划与前进；P3 不阻塞。勿混 stage45j URDF/偏置。

**相关**：`reports/habitat_rangercr10_integration.md`、`.../apexnav_real/20261104_114652/`、`.../camera_view_diag_stage410d_20261104_114102/`

---

## 2026-11-04 Demo 统一 7 Hz + 白底占据图

**模块**：`adapters/habitat_rangercr10` Demo 采集/合成

**问题**：原论文风视频为每 planner 步 1 帧（ffmpeg 2 FPS），运动跳变；右下角地图为深色底，不适合论文图。

**操作**：

- `map_style.py` + `map_listener`：白底/浅灰自由/深色障碍/蓝机器人/橙轨迹。
- `demo_7fps_from_run.py`：按 `actions.jsonl` 时间戳 7 Hz 时间线；Habitat 插值重渲染第三人称与 EE；检测与地图内容 hold 最近真实更新；白底 remap + 轨迹叠加。
- 保留原 `apexnav_ranger_paper_demo.mp4`；新输出 `apexnav_ranger_paper_demo_7fps.mp4`。

**实测**（`20261104_114652`）：ffprobe **7/1**，300 帧，≈42.86 s；det≈1.17 Hz，map 内容≈0.30 Hz，显示 7 Hz；`not_ffmpeg_speedup_of_2fps=true`。

**结论**：三画面同步 7 FPS 达标；未改 PPO/规划器。

**相关**：`scripts/run_demo_7fps.sh`、`demo/demo_7fps_rates.json`、`reports/habitat_rangercr10_integration.md`

---

## 2026-11-04 ApexNav 频繁转向与膨胀/足迹诊断

**模块**：`adapters/habitat_rangercr10`（ROS 发布 / 启动 overlay）

**问题**：开阔 ep 上 MOVE_FORWARD 少、TURN_LEFT 连击；窄 ep `NO_PASSABLE_FRONTIER`；需核对 0.18 m 膨胀与 Ranger 尺寸。

**操作**：

1. 实测 MOVE_FORWARD 的 ROS 位移航向 vs odom：恒差 **180°** → 适配层 `hab_yaw_to_ros(+π)`。
2. MuJoCo 量底盘半长/半宽 0.651/0.435；对照 A/B/C 膨胀与 optimistic。
3. 独立 overlay + `exploration_rangercr10.launch`；验证 `legacy018` 与 `ranger_safe`。

**实测**：

- 修复后 yaw 误差≈0°；左转连击消失；legacy018 下 FWD 1.25 m（原 1.0 m）。
- ranger_safe(0.485) 生效 inflation≈0.48，但 free→0 早停。
- 未改 baseline 规划源码 / PPO。

**结论**：转向刷屏主因是航向约定错误；膨胀 0.18 对实机不安全但不是左转主因。

**相关**：`reports/apexnav_rangercr10_frontier_inflation.md`、`frontier_inflation_diag/`、`real_yawfix_legacy018_*`

---

## 2026-11-04 狭窄验证与中档膨胀对照

**模块**：`adapters/habitat_rangercr10`

**问题**：验收要求开阔+狭窄完整短 Episode，并检验是否可在安全约束下找到折中膨胀。

**操作**：

1. 窄场景 `TEEsavR23oF` chair/4 + yaw 修 + `legacy018`。  
2. 开阔场景 + `mid030`（0.30 m，标不安全）在线对照。  
3. 离线扫 0.25–0.435 并生成 raw/0.18/0.30/0.485 面板图。  
4. 更新 `episode_compare.json` 与报告。

**实测**：

- 窄：仍 `expl_result=4` / STOP×1；与修复前一致 → NO_PASSABLE 非航向问题。  
- 中档 0.30：free→1、inflate 2864，探索约 11 步后 STOP（行为接近 0.485）。  
- 结论：无法靠各向同性加大膨胀同时满足 Ranger 足迹与可达 Frontier。

**相关**：`real_yawfix_narrow_legacy018_*`、`real_yawfix_open_mid030_*`、`map_panel_raw_018_030_0485.png`

---

## 2026-11-05 场景筛选与 yr17 多步探索

**模块**：`adapters/habitat_rangercr10`（scene_clearance / spawn / wheel viz）

**问题**：需在已下载 HM3D 中找适合 Ranger 足迹的场景，并验证 ApexNav 多步探索；轮胎不随底盘运动。

**操作**：

1. 对 36 个 ObjectNav-v2 场景重算多半径 navmesh，排出 Top-5。  
2. 在 HY1/yr17 等场景跑真实 ApexNav；发现原起点易 NO_PASSABLE，过度外移易 NO_COVERABLE。  
3. `prefer_open_clearance`：起点 1.5 m 内偏好 ~0.55 m clearance。  
4. 接入 4WS 轮胎可视化并烟雾验证。

**实测**：`yr17PDCnDDW` chair/0 → Explore L3/R2/F6，前进 1.5 m；HY1 同策略仍早停。未改 ApexNav 规划/膨胀扫描。

**相关**：`reports/apexnav_rangercr10_scene_screening.md`、`real_wide_yr17_openband_*`

---

## 2026-11-05 Top-5 短测、HY1 差异与足迹安全

**模块**：`adapters/habitat_rangercr10`

**问题**：需验证 Top-5 探索稳定性；解释 yr17 vs HY1；证明 legacy018 路径对 Ranger 是否安全。

**操作**：

1. 开放带短测 eF36/LT9/k1cup；修复 spawn 轮角累积导致的 NaN FK。  
2. 离线对照 yr17/HY1 日志与 expl_result。  
3. yr17 路径定向足迹扫掠（GT navmesh 仅评价）。

**实测**：

- Top-5 均进入正式探索；eF36 为 EXPLORATION×24；yr17 为 SEARCH_EXTREME×12。  
- HY1/LT9：NO_PASSABLE；k1cup：NO_COVERABLE（建图弱）。  
- yr17 足迹 safe_ratio=0 → 展示规划 ≠ 安全通行。

**相关**：`reports/apexnav_rangercr10_top5_explore_safety.md`

---

## 2026-11-05 Habitat 整机 0.7× 代理缩放

**模块**：`adapters/habitat_rangercr10`（分支 `cursor/habitat-rangercr10-scale070`）

**问题**：1.0× Ranger 在 HM3D 通道偏紧；需验证均匀缩尺对通行/探索/Demo 的影响，且不改动真机 URDF/PPO。

**操作**：

1. 适配层生成 `..._s070.urdf`（缩放 origin xyz + mesh/box）；`robot_scale=0.7` 同步贴地与足迹。  
2. `scale070_verify`：高度比/轮距比≈0.70，相机≈0.60 m，贴地 OK。  
3. 同 episode 强制 1.0× spawn，跑 yr17/eF36/Dd4b/HY1；离线足迹回放。

**实测**：yr17 足迹 safe_ratio 0→1；探索距离未全面增加；HY1 仍 NO_PASSABLE。规划仍 legacy018。

**相关**：`reports/apexnav_rangercr10_scale070.md`

---

## 2026-11-05 MuJoCo teleop-PPO 抬臂 → 0.7× ApexNav

**模块**：`adapters/habitat_rangercr10`（同分支 `cursor/habitat-rangercr10-scale070`）

**问题**：需用已训练 stage410d PPO（非 IK）在 0.7× 代理上抬臂至可用视高，再交接 ApexNav 探索。

**操作**：

1. 核对契约：obs=117、hist=3、act=8、ACTION_SCALE=0.25、10 Hz；条件输入 `vel_cmd`+`ee_cmd`。  
2. `ppo_mujoco_raise.py`：MuJoCo `teleop_eval.Sim` 执行 Z+0.40（箱顶），底盘 cmd=0；写出 `arm_q`。  
3. Habitat 加载 0.7×，FK 验收 TCP/D455 AGL；`--ppo_raise_json` 同步关节后 26 步环视再探索。  
4. 批跑 yr17/eF36/HY1；生成 7 FPS Demo。

**实测**：

- MuJoCo EE 跟踪≈1.9 cm / 3.4°；底盘漂移≈0.023 m；近限位 false。  
- Habitat 0.7×：TCP≈0.811 m（目标 0.88 **未达**）；D455≈0.881 m 水平 OK。  
- 三场景均 `entered_explore` 后立即 STOP（NO_PASSABLE 类 planner_stop）；FWD=0。  
- Demo：`real_s070_pporaise_{yr17,ef36,hy1}_*/demo/*_7fps.mp4`（1280×720）。

**结论**：抬臂交接链路打通且未改权重/ApexNav/1.0×；TCP 高度与多步探索均未达核心验收的后半部分，已如实记录。

**相关**：`reports/apexnav_rangercr10_ppo_raise_s070.md`；`ppo_raise_s070_batch_20261105_171118.jsonl`

---

## 2026-11-05 抬臂后 NO_PASSABLE 根因与适配修复

**模块**：`adapters/habitat_rangercr10`（同分支）

**问题**：PPO 抬臂后 yr17/eF36/HY1 首次 `callActionPlanner` 均 `NO_PASSABLE_FRONTIER`。

**根因**（诊断 dump）：

1. ROS Z 用绝对 Habitat Y → map_ros 高度滤波错位。  
2. 建图原点在 D455、规划起点在底盘（≈0.65 m）→ 起点 UNKNOWN。  
3. AGL 对齐后机体近距点进 occupied；Habitat 覆盖 mindist 使 launch 近距滤波无效。

**修复**：AGL Z；odom XY=相机；发布前 self-hit 深度屏蔽 0.65 m；首次规划诊断落盘。

**实测**：yr17 EXPLORATION×8 + FWD 0.25 m；HY1 n_explore=54 + FWD；eF36 弱多步。未改 ApexNav 源码默认 / PPO / 1.0×。

**相关**：`reports/apexnav_rangercr10_nopassable_after_ppo_raise.md`；`ppo_raise_s070_nopassable_fix_20261105_183429.jsonl`

---

## 2026-11-05 环视占据放射伪影 / 无效深度修复

**模块**：`adapters/habitat_rangercr10` + ApexNav `map_ros` 局部补丁（同分支）

**问题**：抬臂环视时 `/grid_map` 出现大量自原点外射线条；怀疑近距自遮挡被写成 5 m。

**根因**：

1. 适配层曾将机体近距深度改写为 `depth_max` → 虚假终点参与占据与自由射线。  
2. `convertTo` uint16 会把 NaN/Inf 变成 0/极值，须在转换前建有效掩码并跳过。  
3. 仅靠 blanket `<0.65 m` 会误伤近距家具；几何掩码初期因 Habitat **-Z** 光轴与薄球模型漏检。

**修复**：`prepare_depth_for_apexnav` 无效→NaN；几何球/胶囊/AABB；`map_ros` NaN skip；归一化保 NaN。

**实测**（yr17，不覆盖旧 Demo）：

- before fix run：`..._yr17_fix_20261105_183316` occ/free 1026/675。  
- after：`..._depthfix4_20261105_201112` occ/free 727/932；FWD 0.50 m；满 step budget。  
- 占据相对相机 `r_med≈2 m`，无 r≈5 m 团簇。

**结论**：无效深度不再生成虚假终点/射线；短程真实 ApexNav 规划恢复。Demo 稀疏扇形仍可能来自 PointCloud2 射线散点可视化，不等于 max-range 伪影。

**相关**：`reports/habitat_rangercr10_depth_radial_fix.md`；`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/depth_radial_fix/`

---

## 2026-11-05 Demo Occupancy + Value Map 叠加

**模块**：`adapters/habitat_rangercr10` Demo 层（同分支）

**问题**：右下角仅显示几何占据，缺少 ApexNav 原生价值热力。

**操作**：订阅 `/grid_map/value_map`；按 `ApexNav.rviz` Intensity 黄→红叠加到 free；图例 Target/Value/occ；ITM cosine 与深度同帧对齐（先 `/blip2/cosine_score` 后 RGB-D）；7fps 保留热力色。

**实测**：`real_s070_pporaise_yr17_valuemap_20261105_210015` — value_map 点数=free=1067；cosine 0.10–0.40；7fps 1280×720@7Hz。未改规划/PPO/检测后端。

**相关**：`reports/habitat_rangercr10_valuemap_demo.md`

---

## 2026-11-05 Demo 地图取消 cell 边框

**模块**：`map_raster` / `map_listener`（Demo only）

**问题**：Occ+Value 面板每个 cell 呈独立小方块；需区分放射状真数据 vs 可视化空隙。

**操作**：按 0.05 m 分辨率填充 cell 足迹；离线 A/B 与 live 同时刻对照；证明 prior/after `/grid_map` cell 集合 Jaccard=1。

**结论**：假边框为 1px 欠采样；放射扇区为环视稀疏观测。未改规划输入。

**相关**：`reports/habitat_rangercr10_map_raster_fill.md`

---

## 2026-11-06 视场/环视/不可通行诊断 + yaw 步长对照

**模块**：`adapters/habitat_rangercr10` 诊断层（同分支）

**问题**：白栅格观感是否仍含可视化伪影；30° 环视是否造成覆盖盲区；NO_PASSABLE/A* 与地图误识别关系。

**操作**：

- 从 mapfill 正式环视提取每帧位姿/FOV 重叠/深度有效率（`lookaround_fov_diag`）。
- 首规划 passability 统计（free 分量、frontier、A*、inflate）。
- 有界对照：同 yr17 spawn、同 0.7×/PPO raise/legacy018，仅改 yaw 步 15/30/45°（mapping-only）。
- 发现对照空地图：缺 TURN_DOWN 时高度滤波易清空；曾写「光轴朝上」——**降级为待实际光轴测量验证**（非本轮实测结论）。对照脚本补 joint3−0.60 后地图恢复。

**实测**：

- HFOV/VFOV 方像素约 79°/63.45°（旧 59.25° 为错误 fy 推论，已降级）；30° 重叠 **49°（约 HFOV 的 62%）**，无水平盲楔。
- yaw15/30/45 末帧 occ/free：1010/1275、584/954、281/550。
- 未改规划器/缩放/PPO/深度 NaN/膨胀；未覆盖旧 Demo。

**结论**：当前不可通行压力主要来自 unknown+膨胀连通，而非 30° FOV 漏扫。若改环视步长须单独开实验。

**相关**：`reports/habitat_rangercr10_lookaround_fov_passability.md`；`reports/lookaround_yawstep_compare_20261106/`

---

## 2026-11-06 相机 optical 投影 / 内参 / 底盘 odom 修复

**模块**：`coord_habitat_ros` / `camera_model` / `ros_dynamic_publisher` / `depth_validity` / `pointcloud_dynamic`

**问题**：审查指出（并经独立解析验证）：(1) `C@R@C.T` 误用于 optical 位姿；(2) 曾向 map_ros 发 render 而非 optical；(3) 自遮挡 optical+`z=-d`；(4) fy 用 HFOV×H/W；(5) odom XY 相机代理。

**操作**：新增 optical 专用转换与方像素 K；默认 chassis odom；统一 self-hit/语义点云；修正 Python A* 起点 passable；更正 GT 探针命名；离线 `validate_camera_coord_chain` all_pass。

**未做（当时）**：完整 C++ episode 重测；未改膨胀/环视步长/PPO/缩放。

**相关**：`reports/habitat_rangercr10_camera_odom_coord_fix.md`；`reports/camera_coord_fix_20261106/`

---

## 2026-11-06 a5e291b 后 30° 正式回归 + 原生规划归因

**操作**：收尾 optical 调用方/文档；运行时几何验收；C++ `plan_diag`/`pipeline_diag`；同 spawn yr17→eF36→HY1 有界 30° 回归（≤20 探索）。

**结果**：

- 运行时：投影/ROS K/map_ros 射线、底盘 odom、几何自遮挡 **通过**。
- yr17：20× 原生 `EXPLORATION`，无 NO_PASSABLE，FWD×4。
- eF36/HY1：首规划 `NO_PASSABLE_FRONTIER`；底盘 `start_raw_occ=UNKNOWN`；候选 `NO_PATH` 且 inferred reject 以 unknown 为主（非 inflate）。
- 全程 `height_ground_band=0`（观察）；本轮未改 free 策略。

**决策**：下一步单变量修底盘 free 缺口；暂缓 15°。

**相关**：`reports/habitat_rangercr10_geomreg_30deg_native_plan.md`；`reports/geomreg_30deg_20261106/`

---

## 2026-11-06 底盘起点 UNKNOWN：地面 free-ray 单变量

**模块**：`map_ros` / `sdf_map2d` / `algorithm_rangercr10.xml`

**问题**：臂载相机相对底盘前向约 0.65 m；free 由障碍终点→相机射线雕刻。AGL∈[0, `filter_min_height`] 地面点原计入 `height_other` 丢弃 → 相机邻域可 FREE、底盘中心仍 UNKNOWN（eF36/HY1）。

**操作（仅一变量）**：

- Launch：`map_ros/ground_free_ray_enable=true`
- `filterPointCloudToXY`：地面带 → free-ray 候选（不写 OCCUPIED）
- `SDFMap2D::inputFreeRayCloud2D`：只 miss/free，遇已 OCCUPIED 不穿透
- 禁止项均未做：强制 UNKNOWN→FREE、缩膨胀、相机假 odom、15°、PPO/0.7×/环视

**结果（同 spawn 30° ≤20 探索）**：

| 场景 | 起点 | NO_PASSABLE | EXPLORATION | 净位移 |
|------|------|-------------|-------------|--------|
| yr17 | FREE→FREE | 0 | 20 | 0.85→1.56 m |
| eF36 | UNKNOWN→**FREE** | 1→**0** | 0→**20** | 0→**3.17 m** |
| HY1 | UNKNOWN→仍 UNKNOWN | 仍 1（第 4 次） | 0→3 后失败 | 0→0.25 m |

**结论**：根因判断成立（地面过滤）；eF36 完全恢复；HY1 为同根因下场景覆盖不足（地面候选多但未落底盘 0.3 m），另立单变量；暂缓 15°；足迹安全未专项宣称。

**相关**：`reports/base_start_unknown_diagnosis.md`；`reports/base_start_unknown_20261106/`

---

## 2026-11-06 地面 free-ray 正确性收口（分提交）

**模块**：`sdf_map2d` / `map_ros` / `astar2d` plan_diag / 三场景短跑

**操作与提交**：

1. `6df8ceb` — 同帧 `local_update` merge；离线对照全图膨胀。  
2. `ef70acd` — AGL≤0.03+平面才 free-ray；5/10/20 cm→OCC；单测通过。  
3. `813827c` — 0.25 m 豁免 observe-only；HY1 失败帧 dump；经典第 4 次=覆盖不足。  
4. 本轮 short3 报告 — yr17/eF36 20 探索；HY1 再现首规划 NO_PASSABLE。

**结论**：地图更新与地面候选正确性门槛通过；HY1 仍归因底盘侧地面覆盖不足 → **允许另立补视单变量**（本轮未改姿态）。

**相关**：`reports/local_update_merge_20261106*`；`reports/ground_free_geometry_20261106*`；`reports/hy1_failframe_20261106*`；`reports/groundgate_short3_20261106*`

---

## 2026-11-06 HY1 重复性与补视 A/B/C

**操作**：triad 并列证据；豁免静默计数；C++ `test_map_pipeline_replay`；基线 5×（v2）；A/B/C 各 5×（EXTRA_PUBS=40）。

**结果**：基线 NO_PASSABLE 5/5；A/B/C 均为 NO_PASSABLE 5/5、free@0.3=0；C 不优于 B → **不支持朝向补视有效**。默认部署未改。

**相关**：`reports/hy1_triad_evidence_20261106*`；`reports/hy1_baseline_repeats_20261106*`；`reports/hy1_look_abc_20261106*`

---

## 2026-11-06 HY1 近底盘可观测性缺口定位

**模块**：固定构型探针 + `MapROS::diagProcessCloud3DKeepZ` + `test_map_pipeline_replay` Case C

**问题**：A/B/C 均 free@0.3=0；需区分「未见地面 / 过滤误杀 / 射线未穿格 / 地图更新失效」。

**操作**（未改默认部署与门控）：

- 探针保存 B/C 关节、相机位姿/optical R、底盘位姿、同步 RGB/raw depth/self-hit，并投影 0–0.3/0.3–0.6 m 候选地面。
- 镜像生产管道做环带逐阶段统计与 UNKNOWN 格追踪。
- 原生测试保留 XY-only Case A/B 并准确命名范围；新增真实 z=5/10/20 cm 3D-keep-Z Case C。

**实测**：

- B：光学近水平；环带 `n_in_fov=0`；点云 0–0.6 m=0；最近点≈1.58 m。
- C：j3−0.60 下俯成立（cam_z 0.88→0.56，fwd_z→−0.52）；环带仍 `n_in_fov=0`；点云 0–0.6 m=0；最近点≈0.85 m（织物，非足迹）。
- 0–0.3 m 代表格：无 free-ray miss；过滤/地图更新路径未触发。
- Case C ALL_PASS：低矮障碍经生产过滤后 OCCUPIED。

**结论**：最早缺口 = **目标地面未被看到**（传感器/姿态可观测性）。优先另立启动策略任务做几何可验证覆盖姿态；不修过滤/不强制 FREE。

**相关**：`reports/hy1_chassis_observability_20261106*`；`adapters/.../hy1_chassis_ground_observability_probe.py`

---

## 2026-11-06 HY1 启动观测几何可行性

**模块**：臂完整构型离线搜索 + 几何一致性 + MapROS CSV 回放

**操作**：冻结可观测性证据与 0.7× 足迹区带定义；在 URDF 限位内搜索 1449 构型；FOV/接触/深度/生产镜像/走廊连通；几何一致性复核；`test_map_cloud_csv_replay` 静态回放。未改默认部署与门控。

**结果**：

- 走廊目标地面：**可被看到**（cand05/06；lookdown_C geom=60）。
- 生产后走廊地面端点：**稀疏**（cand05=3；C raw62→after0）——门控过滤记录在案，本轮不改。
- 车下 0–0.3 m：**不可见**（足迹遮挡）。
- 起点模拟 free：**否** → 预告 start-state/接口风险。
- 优选：`cand05`（备选 `cand06`）。

**结论**：有限搜索内存在可行观察姿态；下一步特征开关静态多帧+独立启动实验，不把无解说成全局不存在。

**相关**：`reports/hy1_startup_pose_geometry_20261106*`

---

## 2026-11-06 cand05 静态多帧生产链路

**模块**：`STATIC_OBS_ENABLE` + exploration map_ros（无底盘、无改门控）

**操作**：固定 cand05；按 pipeline `frame_seq` 在 1/5/10/20 检查点采样走廊 FREE/起点/门控镜像；离线追踪 C 与 cand05 走廊地面损失阶段。

**结果**：

- N=5：走廊 FREE=82；其后新增=0 → **空间饱和**（停 40）。
- 跨度~0.25 m，非足迹级连续通路；底盘中心 **absent**。
- C：走廊 raw 62 → voxel 后 0（最早损失）。cand05：27→3 后保持。

**结论**：禁止加帧宣称改善；下一步覆盖重设计，并可选独立修 voxel Z 混合；不改起点豁免。

**相关**：`reports/hy1_cand05_static_multiframe_20261106*`

---

## 2026-11-06 HY1「空旷却包围底盘不可通行」根因

**模块**：离线冻结 run 分层诊断（只诊断）

**操作**：

- 冻结 `99ebb49` + `real_s070_hy1_base_rep_v2_r1_20261106_191426`（不用旧 7fps 视频推断）。
- 原生 `plan_seq_1_local_map` 分 FREE/UNKNOWN/OCC/inflate；足迹内/外分带；叠加相机轨迹与候选拒绝。
- 核对 odom/sensor_pose/射线起点；帧0→1 静态种子重投影。
- 交叉 cand05/C voxel 损失（独立支线）。

**结果**：

- 包围环 = **UNKNOWN**（0–0.3 全在车下；车外 moat≈0.5 m）；最近 OCC≈0.87 m；候选拒绝 unknown=3943、occ/inf=0。
- 相机偏置正确；legacy 代理关；重投影 max≈1.8 mm → 不支持外参/同步假障。
- 最近 FREE 0.52 m > 0.25 m 豁免 → 豁免不能打通。

**结论**：主因观测盲区→UNKNOWN；下一步覆盖重做；可选独立修 voxel；不强制 FREE/不扩豁免/不注 GT。

**相关**：`reports/hy1_surround_nontraversable_20261106*`

---

## 2026-11-07 初始足迹通行先验（startup_prior）

**模块**：Astar2D 规划查询 + 适配 launch；HY1 冻结地图原生 A/B

**操作**：

- 唯一开关 `startup_prior_mode=none|initial_footprint`（默认 none）。
- F0 由底盘位姿+`footprint_at_scale` 半轴一次生成；不改写占据；`initial_footprint` 关闭 0.25 m skip。
- `test_startup_prior_astar` 加载冻结 cells/candidates 跑生产 A*。

**结果**：A 0/26；B 5/26，路径长≈0.63 m；安全边 F0 外 UNKNOWN=0；OCC/inflate 仍拒；地图未变。

**结论**：启动先验接口有效；默认仍 none；执行安全另立。

**相关**：`reports/hy1_startup_prior_20261107*`
