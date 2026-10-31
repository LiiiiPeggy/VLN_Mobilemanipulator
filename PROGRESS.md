# PROGRESS.md — 当前状态

更新时间：2026-11-01（VLFM 单 ep OK；MSGNav deps 就绪但单 ep 卡在 open_clip HF 权重；ApexNav 仍在拉 CUDA base）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10 移动机械臂。

**当前阶段**：正式 Habitat 镜像就位；**VLFM=`SINGLE_EPISODE_OK`**；**MSGNav=`DEPENDENCIES_READY`**（单 ep 尝试失败）；ApexNav 正式镜像仍在构建。

## Baseline 状态

状态枚举：`NOT_STARTED / CLONED / CONTAINER_READY / DEPENDENCIES_READY / MODEL_LOADED / SINGLE_EPISODE_OK / BATCH_OK / BLOCKED`

| Baseline | 状态 | 证据摘要 |
|----------|------|----------|
| VLFM | `SINGLE_EPISODE_OK` | 镜像 `vln-habitat024:latest`=`fe6b1ca643fd`（含 runtime deps）；VLM 12181–12184；单 ep 日志 `runs/VLFM/single_episode_20261101_001121.log`；摘要 `runs/VLFM/single_episode_status.md`（success=0 / false_positive，管道 OK） |
| ApexNav | `CONTAINER_READY`（正式镜像 `BUILDING`） | 占位 `vln-apexnav:latest` 仍 Up；`docker build -t vln-apexnav:build` 拉 CUDA base ~1.04/1.47GB → `runs/_build/apexnav_build.log` |
| MSGNav | `DEPENDENCIES_READY`（单 ep `BLOCKED`） | 镜像 `vln-habitat025:msgnav-deps`=`24b7c26315a3`；deps/API 见 `runs/MSGNav/deps_status.md`；单 ep YOLO/SAM OK，open_clip DFN5B 权重 HF 不可达 → `runs/MSGNav/single_episode_status.md` |
| APRR | `CONTAINER_READY`（轻量） | `vln-aprr` Up；百度权重已就位 |
| SG-Nav | `CONTAINER_READY`（轻量） | `vln-sgnav` 在 `vln-habitat025`；需 MP3D+GLIP；Habitat 应对齐 0.2.4 |
| UniGoal | `CONTAINER_READY`（轻量） | `vln-unigoal` 在 `vln-habitat025`；需 HM3D+目标数据集 |

## 已完成（有证据）

| 项 | 证据 |
|----|------|
| 六套源码 + SHA | `reports/source_versions.*`；嵌套 `.git` 已删 |
| 六 compose + 容器 Up | `docker ps --filter name=vln-` |
| 正式 habitat024 / 025 | `vln-habitat024:latest`=`fe6b1ca643fd`；`vln-habitat025:latest`=`ff049f5c4eed`；MSGNav 专用 tag `:msgnav-deps` |
| 共享权重/数据 | `verify_shared_assets.sh` → ok=11 miss=0；HM3D / ObjectNav / SAM 等已挂 D 盘 |
| VLFM runtime deps + dummy policy | `data/dummy_policy.pth`；`dash<3` 修复 open3d/pydantic |
| VLFM VLM 服务 + 单 episode | `runs/VLFM/single_episode_status.md` |
| MSGNav API / deps | 本地 `.env`（gitignored）；冒烟 `gpt-5.6-sol`；`runs/MSGNav/deps_status.md` |
| MSGNav 路径/配置 | compose 挂载 D 盘；`cfg/eval_hm3d.yaml` + `eval_hm3d_single_ep.yaml`；密钥改走 env |

## 阻塞 / 风险

| 项 | 说明 |
|----|------|
| MSGNav open_clip 权重 | 缺 `apple/DFN5B-CLIP-ViT-H-14`（~数 GB）；容器直连 HF 失败；正用 `hf-mirror.com` 写入 `/shared/cache/huggingface`（待验证完成） |
| ApexNav 正式镜像 | CUDA base 层慢拉（~1.04/1.47GB）；日志 `runs/_build/apexnav_build.log` |
| GPU | 当前显存占用较低（~5GB，含他人进程）；跑 MSGNav/ApexNav 前仍先 `nvidia-smi` |
| 磁盘 | `/` 约 281G 可用（~92%）；大文件必须落 D 盘 |
| VLFM 任务成功率 | 单 ep 为 false_positive（非崩溃）；批量前可再选 ep |

## 下一步（最多 5 项）

1. 完成 DFN5B open_clip 权重落地 → 重跑 MSGNav `eval_hm3d_single_ep.yaml` → 争取 `SINGLE_EPISODE_OK`。  
2. 等待 `vln-apexnav:build` 完成 → tag `:latest`、重建容器、smoke habitat_sim 0.3.1。  
3. 按需把 SG-Nav 对齐 habitat024；补 MP3D。  
4. UniGoal 数据与版本核对。  
5. 移动机械臂接口锚点与 4070 8GB 判断（`baseline_validation.md` §7）。
