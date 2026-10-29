# PROGRESS.md — 当前状态

更新时间：2026-10-29  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10 移动机械臂。

**当前阶段**：源码导入 + 仓库级记忆/Docker 脚手架刚落地；**尚未**构建镜像、安装完整依赖或跑通任何 episode。

## Baseline 状态

状态枚举：`NOT_STARTED / CLONED / CONTAINER_READY / DEPENDENCIES_READY / MODEL_LOADED / SINGLE_EPISODE_OK / BATCH_OK / BLOCKED`

| Baseline | 源码 | 容器 | 依赖 | 模型推理 | 单 Episode | 小批量 | 结果路径 |
|----------|------|------|------|----------|------------|--------|----------|
| VLFM | `CLONED` (`584ed56…`) | compose 已写，**镜像未 build** | 未装 | 未验证（仓内有 pointnav 权重） | — | — | `runs/VLFM/` 空 |
| ApexNav | `CLONED` (`049971b…`) | compose 已写，**镜像未 build** | 未装 | 未验证 | — | — | `runs/ApexNav/` 空 |
| MSGNav | `CLONED` (`03681a1…`) | compose 已写，**镜像未 build** | 未装 | 未验证 | — | — | `runs/MSGNav/` 空 |
| APRR | `CLONED` (`046c9c2…`) | compose 已写（lite），**镜像未 build** | 子模块不全 | 未验证 | — | — | `runs/APRR/` 空 |
| SG-Nav | `CLONED` (`d56863c…`) | compose 已写，**镜像未 build** | 未装 | 未验证 | — | — | `runs/SG-Nav/` 空 |
| UniGoal | `CLONED` (`e2c6d45…`) | compose 已写，**镜像未 build** | 未装 | 未验证 | — | — | `runs/UniGoal/` 空 |

说明：

- SHA 见 `reports/source_versions.md` / `reports/source_versions.json`。
- Compose：`baselines/<Name>/docker-compose.yml`；共享 Dockerfile：`shared/docker/`。
- `docker images` / `docker ps`（2026-10-29）无 `vln-*` 镜像或容器 → **不能**标 `CONTAINER_READY`。
- 嵌套 `.git` 已由 `scripts/strip_nested_git.py` 清除。

## 已完成（有证据）

| 项 | 证据 |
|----|------|
| 六套上游源码导入 umbrella | `baselines/*`；`reports/source_versions.*` |
| 根 `.gitignore`、共享目录与 D 盘软链 | `.gitignore`；`shared/*_large` → `/media/ubuntu/D/VLN_shared` |
| 工程记忆四文件 | `AGENTS.md` / `MEMORY.md` / `PROGRESS.md` / `PROCESS.md` |
| 每 baseline 独立 compose + 共享 Dockerfile 草稿 | `baselines/*/docker-compose.yml`；`shared/docker/Dockerfile.*` |
| 嵌套 git 剥离 | `find baselines -name .git` 为空；`source_versions.json` |

## 阻塞 / 风险

| 项 | 说明 | 日志/位置 |
|----|------|-----------|
| 镜像未构建 | Dockerfile 仅为脚手架；`habitat-lab` 安装步骤含 `\|\| true` 等占位 | `shared/docker/Dockerfile.habitat024` |
| Habitat 版本与镜像映射未对齐 | UniGoal 文档要 0.2.3、SG-Nav 要 0.2.4，但 compose 暂挂 `vln-habitat025` | 各 compose；`MEMORY.md` §4 |
| APRR 子模块不全 | 数据与部分 detection 未初始化 | `reports/source_versions.md` |
| VLFM 缺 yolov7 树 | README 要求仓内克隆 | `baselines/VLFM/` |
| 场景/权重未就绪 | D 盘 `VLN_shared/{datasets,checkpoints}` 为空 | `/media/ubuntu/D/VLN_shared` |
| 无评测 runs | 六个 `runs/*` 目录空 | `runs/` |

## 下一步（最多 5 项）

1. **Build 并验证** 共享镜像（优先 `vln-habitat024` / `vln-apexnav` / `vln-lite`），`docker compose config` + 容器内 Python/CUDA 冒烟；成功后再标 `CONTAINER_READY`。  
2. **对齐 Habitat 镜像映射**（尤其 SG-Nav 0.2.4、UniGoal 0.2.3），避免误用 0.2.5。  
3. **准备数据与权重**：HM3D/MP3D 与各模型放到 `shared/*_large`；补 VLFM `yolov7`。  
4. **选一个 baseline（建议 VLFM 或 ApexNav）打通 `SINGLE_EPISODE_OK`**，结果写入 `runs/<Name>/`。  
5. **补齐 APRR home-robot 子模块**（仅评测所需），再考虑其容器从 lite 升级。
