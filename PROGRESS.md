# PROGRESS.md — 当前状态

更新时间：2026-11-01（三套主线 `BATCH_OK`）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10 移动机械臂。

**当前阶段**：正式 Habitat 三族镜像就位；**VLFM / MSGNav / ApexNav = `BATCH_OK`**（固定 8-ep 小批量，日志在 D 盘 `batch_20261101`）。

## Baseline 状态

状态枚举：`NOT_STARTED / CLONED / CONTAINER_READY / DEPENDENCIES_READY / MODEL_LOADED / SINGLE_EPISODE_OK / BATCH_OK / BLOCKED`

| Baseline | 状态 | 证据摘要 |
|----------|------|----------|
| VLFM | `BATCH_OK` | `vln-habitat024:latest`=`fe6b1ca643fd`；8/8 无崩溃；SR=25% SPL=0.1164；峰显存 19356 MiB；`runs/VLFM/batch_8ep_status.md`；CSV `.../batch_20261101/VLFM/` |
| ApexNav | `BATCH_OK` | `vln-apexnav:single-ep-deps`=`50e76a268b26`；8/8 无崩溃；任务成功 6/8（SR=75%）；峰显存 12912 MiB；VLM=`python -m vlm.*`；`runs/ApexNav/batch_8ep_status.md`；CSV `.../batch_20261101/ApexNav/metrics.csv` |
| MSGNav | `BATCH_OK` | `vln-habitat025:msgnav-deps`；8/8 无崩溃；任务成功 3/8（SR_dist=37.5% SPL≈20.7%）；峰显存 16507 MiB；API=`gpt-5.6-sol`（有 502/timeout 重试）；`runs/MSGNav/batch_8ep_status.md` |
| APRR | `CONTAINER_READY`（轻量） | `vln-aprr` Up；百度权重已就位 |
| SG-Nav | `CONTAINER_READY`（轻量） | `vln-sgnav` 在 habitat025；需 MP3D+GLIP；Habitat 应对齐 0.2.4 |
| UniGoal | `CONTAINER_READY`（轻量） | `vln-unigoal` 在 habitat025；需 HM3D+目标数据集 |

## 已完成（有证据）

| 项 | 证据 |
|----|------|
| 六套源码 + SHA | `reports/source_versions.*` |
| 正式 habitat024 / 025 / apexnav | `fe6b1ca643fd` / `ff049f5c4eed`(+msgnav-deps=`1b1bdc94f963`) / apexnav `50e76a268b26` |
| 共享权重/数据 | `verify_shared_assets.sh` → ok=11 miss=0 |
| 三套单 episode | `runs/{VLFM,ApexNav,MSGNav}/single_episode_status.md` |
| 三套 8-ep 小批量 | `runs/*/batch_8ep_status.md`；D 盘 `/media/ubuntu/D/VLN_shared/runs/batch_20261101/{ApexNav,VLFM,MSGNav}/` |
| ApexNav VLM | 项目内 `vlm.detector/itm/segmentor`（**不是** `vlfm.vlm`） |
| MSGNav API | 本地 `.env`（gitignored）；`gpt-5.6-sol` |

## 阻塞 / 风险

| 项 | 说明 |
|----|------|
| 磁盘 | 根分区紧张；大文件必须落 D 盘 |
| VLFM/MSGNav 任务 SR | 批量仍偏低（false_positive / miss）；管道无崩溃 |
| MSGNav API | `model8.run` 间歇 502/timeout；靠客户端重试 |
| ApexNav 镜像栈 | Jammy 叠 Focal Noetic；长期应改 `ros:noetic` 基座 |
| SG-Nav/UniGoal | 版本/数据未对齐正式评测 |

## 下一步（最多 5 项）

1. SG-Nav 对齐 habitat024 + MP3D；UniGoal 数据核对。  
2. 按 `reports/mobile_arm_adaptation_analysis.md` 选路径：优先 ApexNav topic 替换 → VLFM adapter → MSGNav 连续执行器（**尚未实现**）。  
3. 可选：把 ApexNav/MSGNav/VLFM 运行时层写回 Dockerfile，减少 recreate 丢依赖。  
4. 可选：更大 batch / 官方全 val（注意 GPU 与 API 配额）。  
5. 停用后确认各 baseline VLM/ROS 已退出腾 GPU。
