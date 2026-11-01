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
