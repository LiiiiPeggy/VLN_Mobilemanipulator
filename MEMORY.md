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
| 磁盘 | `/` 约 281 GiB 可用（~92%，紧张）；`/media/ubuntu/D` 约 1.9 TiB 可用（大数据优先） |
| 项目根 | `/home/ubuntu/locomani/VLN_Mobilemanipulator` |

宿主机已有长期容器（**禁止动**）：`nbv_fkie`、`nbv_ssmi`、以及 `lxy`/`zxg`/`zfy`/`hkp`/`chn`/`cjf`/`gly`/`yly` 等。存在镜像 `scene_graph:latest`（19.9GB），**尚未**验证是否可用于任一 VLN baseline。

本机 conda 中**无** `vlfm` / `apexnav` / `msgnav` / `SG_Nav` / `unigoal` / `home-robot` 环境（2026-10-29 `conda env list`）。

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
| `vln-habitat025` | `Dockerfile.habitat025` | `vln-msgnav`（及暂挂的 sgnav/unigoal） | **正式**（2026-10-31）：`ff049f5c4eed`，22.6GB；CUDA 11.8 + torch 2.0.1 + habitat-sim 0.2.5；须 Aliyun apt。MSGNav 运行时 extras 另 tag：`vln-habitat025:msgnav-deps`=`24b7c26315a3`（HiPart/pytorch3d/clip；勿 recreate 冲掉未 commit 层） |
| `vln-apexnav` | `Dockerfile.apexnav` | `vln-apexnav` | CUDA 12.1 + torch 2.5.0 + habitat-sim/lab 0.3.1；空代理 + Aliyun apt/pip；**跳过** salesforce-lavis（py39）；正式 `vln-apexnav:build` 构建中见 `runs/_build/apexnav_build.log` |
| `vln-lite` | `Dockerfile.lite` | `vln-aprr` | 基于 `pytorch/pytorch:2.3.1-cuda12.1` 的轻量审计镜像 |

容器名固定为 `vln-{vlfm,apexnav,msgnav,aprr,sgnav,unigoal}`，与 `nbv_*` / 他人容器隔离。  
证据：`runs/_build/habitat024_status.md`、`runs/_build/habitat024_retry.log`。

## 4. 六个 baseline：架构与依赖差异

上游 SHA 权威表：`reports/source_versions.md`。下列依赖来自各仓库 README / 环境文件（**安装本身尚未在本机验证通过**）。

| Baseline | 任务形态 | 关键栈（文档宣称） | Habitat | 官方 Docker / 环境入口 | 额外注意 |
|----------|----------|-------------------|---------|------------------------|----------|
| **VLFM** | ObjectNav；frontier + VLM value map | Python 3.9；torch 1.12.1+cu113；GroundingDINO；LAVIS；可选 Spot | sim `v0.2.4`；lab `0.2.420230405`（`pyproject.toml`） | compose → `vln-habitat024`；上游另有 `docker/Dockerfile` | 需另克隆 `yolov7`；自带 `data/pointnav_weights.pth` |
| **ApexNav** | ObjectNav；target-centric fusion + 自适应探索 | conda `apexnav_environment.yaml`；torch 2.5.0（cu118/121/124） | **sim/lab 0.3.1** | compose → `vln-apexnav` | 需 yolov7、GroundingDINO、若干权重；VLM 多进程端口服务 |
| **MSGNav** | ObjectNav / GOAT-Bench；多模态 3D scene graph | Python 3.9；torch 2.0.1+cu118；open-clip；ultralytics | **sim 0.2.5**；vendored `habitat-lab/` | compose → `vln-habitat025` | 需 LLM API（Qwen/GPT，`src/const.py`） |
| **APRR** | OVMM / Home-Robot 系 | 依赖 Facebook `home-robot` + Habitat challenge 镜像文档 | 随 home-robot / habitat-lab 子树 | compose → `vln-lite`（审计用）；完整栈仍参考官方 challenge 镜像 | 子模块未完全初始化；评测脚本 `runb.sh` / `run_rl.sh` |
| **SG-Nav** | ObjectNav；在线 3D scene graph → LLM | Python 3.9；habitat-sim 0.2.4；GLIP / GroundingDINO / SAM | **sim 0.2.4**；vendored `habitat-lab/` | compose 暂挂 `vln-habitat025`（**版本待改**） | **必须**用 `tools/agent.py` 覆盖 habitat-sim 的 `agent/agent.py` |
| **UniGoal** | 统一 goal（image/text；object 仍在完善） | Python 3.8；sim/lab 0.2.3；Grounded-SAM；detectron2；pytorch3d | **sim/lab 0.2.3**；`third_party/habitat-lab` | compose 暂挂 `vln-habitat025`（**版本待改**） | 与 SG-Nav 同组作者；接口相近但版本更旧 |

### Habitat 版本互斥（重要）

`0.2.3`（UniGoal）/ `0.2.4`（VLFM、SG-Nav）/ `0.2.5`（MSGNav）/ `0.3.1`（ApexNav）**不可**混装进同一 conda/容器环境。这是六套独立 compose/容器的主要技术理由。镜像层若仅差 Python 包，可共享同一 CUDA base，但环境前缀必须隔离。

## 5. 关键启动命令（本机路径）

路径均相对于各 `baselines/<Name>/`。带证据的标「已验证」。

- **VLFM**（已验证单 ep）：容器内先起 VLM 12181–12184，再 `python -m vlfm.run habitat_baselines.test_episode_count=1`；证据 `runs/VLFM/single_episode_status.md`
- **ApexNav**：先起 VLM 服务，再 `python habitat_evaluation.py --dataset hm3dv2`（正式镜像构建中）
- **MSGNav**（deps 已验证；单 ep 待 open_clip 权重）：`python run_hm3d_evaluation.py -cf cfg/eval_hm3d_single_ep.yaml --specific 0`；批量用 `cfg/eval_hm3d.yaml`；密钥仅 `baselines/MSGNav/.env`（见 `.env.example`）
- **APRR**：`bash runb.sh` / `bash run_rl.sh`
- **SG-Nav**：`SG_Nav.py` + `configs/challenge_objectnav2021.local.rgbd.yaml`（需 MP3D）
- **UniGoal**：`python main.py`（需 HM3D + instance-image-goal）

## 6. 移动机械臂 VLN 适配——接口约束（预先遵守）

在未完成 discrete ObjectNav 基线前，不做平台耦合重构。后续适配须遵守：

1. **保留上游评测入口**：Habitat episode、动作空间、成功判定与 SPL 等指标不被静默改写；平台相关改动放在适配层或配置开关后。
2. **观测对齐**：明确 RGB-D 分辨率、相机外参、深度单位与坐标系（光学系 vs link 系）；参考 NBV 工程中 D455 坐标教训（见 NBV `MEMORY.md`，勿在未验证时照搬）。
3. **动作接口**：baseline 多为离散 Habitat 动作（move/turn/stop）；底盘连续速度 / 臂自由度需经显式封装，禁止在算法核心里写死 CR10 关节。
4. **地图与坐标系**：frontier / scene graph 假设的 2D 导航网格与 Ranger 四轮转向运动学不同；适配时单独验证足迹与碰撞。
5. **资源隔离**：推理权重与 HM3D/MP3D 场景只放 D 盘共享目录；容器只挂载需要的子集。

## 7. 已验证的工程结论（本仓库）

| 结论 | 证据 |
|------|------|
| 六套源码已导入，SHA 见 `reports/source_versions.md` / `.json` | 导入记录 + strip 脚本 |
| 嵌套 `.git` 已剥离，umbrella 为唯一 Git | `find baselines -name .git` 为空 |
| 大数据走 `/media/ubuntu/D/VLN_shared`；compose 对 VLFM/MSGNav 挂载同路径以解析绝对软链 | `shared/*_large`；各 `docker-compose.yml` |
| `vln-habitat024/025` 正式镜像可用；六 `vln-*` 容器 Up | `docker images` / `docker ps` |
| VLFM=`SINGLE_EPISODE_OK`（任务 SR=0 false_positive） | `runs/VLFM/single_episode_status.md` |
| MSGNav deps/API 就绪；单 ep 卡在 open_clip HF 权重 | `runs/MSGNav/deps_status.md`、`single_episode_status.md` |
| MSGNav 可用 API 模型为 `gpt-5.6-sol`（`gpt-5.5` 404） | 容器内冒烟；密钥仅本地 `.env` |
| ObjectNav HM3D v2 的 `.json.gz` 需解压为 plain JSON 才可被 MSGNav `json.load` | `.../objectnav/hm3d/v2/val/content_json` |
| open3d 与 pydantic v1：需 `dash<3` | VLFM habitat024 commit 镜像 |

## 8. 常见兼容性风险

| 风险 | 说明 | 应对方向 |
|------|------|----------|
| Habitat 小版本分裂 | 见 §4 | 一 baseline 一环境 |
| SG-Nav/UniGoal 挂错镜像 | 文档要 0.2.4 / 0.2.3，compose 暂用 habitat025 | 专用镜像或改映射 |
| MSGNav open_clip 预训练 | `ViT-H-14-quickgelu`/`dfn5b` 需 HF 大权重；直连常失败 | `HF_ENDPOINT=hf-mirror.com` + D 盘 `HF_HOME` 预拉 |
| `docker compose --force-recreate` | 清掉未 bake 的 pip 层 | 用 `docker commit` tag（如 `:msgnav-deps`）或写入 Dockerfile |
| APRR 子模块不全 | data / detection 未拉全 | 按需补齐 |
| SG-Nav agent 热补丁 | 必须覆盖 habitat-sim `agent.py` | Dockerfile/启动脚本 |
| LLM/API 密钥 | MSGNav 等需在线 LLM | 只用 `.env`（gitignore），勿写入记忆正文 |
| 显存争用 | A6000 ~49GB；他人进程可能占用 | 跑前 `nvidia-smi`；错峰 |
