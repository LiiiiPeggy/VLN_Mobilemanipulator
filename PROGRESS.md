# PROGRESS.md — 当前状态

更新时间：2026-11-01（记忆同步 / 三套主线 `SINGLE_EPISODE_OK`）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10 移动机械臂。

**当前阶段**：正式 Habitat 三族镜像就位；**VLFM / MSGNav / ApexNav = `SINGLE_EPISODE_OK`**。

## Baseline 状态

状态枚举：`NOT_STARTED / CLONED / CONTAINER_READY / DEPENDENCIES_READY / MODEL_LOADED / SINGLE_EPISODE_OK / BATCH_OK / BLOCKED`

| Baseline | 状态 | 证据摘要 |
|----------|------|----------|
| VLFM | `SINGLE_EPISODE_OK` | `vln-habitat024:latest`=`fe6b1ca643fd`；日志 `runs/VLFM/single_episode_*`；摘要 `runs/VLFM/single_episode_status.md`（success=0 / false_positive，管道 OK）。VLM 已停腾 GPU |
| ApexNav | `SINGLE_EPISODE_OK` | `vln-apexnav:latest`=`50e76a268b26`（`:single-ep-deps`，28.2GB；build 保留 `118284656358`）；hm3dv2 `test_epi_num=0` bed **success** SR=100% SPL=70.06%；日志 `runs/ApexNav/single_episode_20261101_retry4.log`；摘要 `runs/ApexNav/single_episode_status.md` |
| MSGNav | `SINGLE_EPISODE_OK` | `vln-habitat025:msgnav-deps`；场景 `zt1RVoi7PcG`/chair；SR=0 miss / EXIT:0；`runs/MSGNav/single_episode_status.md`；API=`gpt-5.6-sol` |
| APRR | `CONTAINER_READY`（轻量） | `vln-aprr` Up；百度权重已就位 |
| SG-Nav | `CONTAINER_READY`（轻量） | `vln-sgnav` 在 habitat025；需 MP3D+GLIP；Habitat 应对齐 0.2.4 |
| UniGoal | `CONTAINER_READY`（轻量） | `vln-unigoal` 在 habitat025；需 HM3D+目标数据集 |

## 已完成（有证据）

| 项 | 证据 |
|----|------|
| 六套源码 + SHA | `reports/source_versions.*` |
| 正式 habitat024 / 025 / apexnav | `fe6b1ca643fd` / `ff049f5c4eed`(+msgnav-deps) / apexnav `50e76a268b26`（build `118284656358`） |
| 共享权重/数据 | `verify_shared_assets.sh` → ok=11 miss=0 |
| VLFM / MSGNav 单 episode | `runs/VLFM/`、`runs/MSGNav/` |
| MSGNav API | 本地 `.env`（gitignored）；`gpt-5.5` 不可用 → `gpt-5.6-sol` |
| ApexNav numpy 钉死 | Dockerfile 末强制 `numpy==1.23.5`；baselines `--no-deps` |
| ApexNav 单 episode | ROS Noetic（自 `nbv-fkie:noetic` **镜像**拷贝）+ catkin `exploration_node` + VLM 12181–84；`habitat_publisher` 去 cv_bridge；证据 `runs/ApexNav/single_episode_status.md` |

## 阻塞 / 风险

| 项 | 说明 |
|----|------|
| 磁盘 | 根分区紧张；大文件必须落 D 盘 |
| VLFM/MSGNav 任务成功率 | 单 ep 均为 miss/false_positive（非崩溃） |
| ApexNav 镜像栈 | Jammy 容器叠 Focal Noetic 靠拷库；长期应改为 `ros:noetic` 基座或专用 Dockerfile |
| SG-Nav/UniGoal | 版本/数据未对齐正式评测 |

## 下一步（最多 5 项）

1. 按需停 ApexNav VLM/ROS 腾 GPU；或补小批量。  
2. 按需重启 VLFM VLM 或补小批量。  
3. SG-Nav 对齐 habitat024 + MP3D；UniGoal 数据核对。  
4. 移动机械臂接口锚点与 4070 8GB 判断（`baseline_validation.md` §7）。  
5. 可选：把 ApexNav/MSGNav/VLFM 运行时层写回 Dockerfile，减少 recreate 丢依赖。
