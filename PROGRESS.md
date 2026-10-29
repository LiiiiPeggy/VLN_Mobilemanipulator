# PROGRESS.md — 当前状态

更新时间：2026-10-29（容器实测后）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10 移动机械臂。

**当前阶段**：源码统一管理 + **六个独立容器已创建验证** + 共享权重部分就绪；官方单 episode **仍阻塞于 HM3D 场景与正式 Habitat 镜像**。

## Baseline 状态

状态枚举：`NOT_STARTED / CLONED / CONTAINER_READY / DEPENDENCIES_READY / MODEL_LOADED / SINGLE_EPISODE_OK / BATCH_OK / BLOCKED`

| Baseline | 状态 | 证据摘要 |
|----------|------|----------|
| VLFM | `CONTAINER_READY`（仿真 `BLOCKED`：HM3D+Habitat0.2.4 实装） | `vln-vlfm` Up；`data/` 已链 GroundingDINO/MobileSAM/YOLOv7/PointNav；容器内 `torch.cuda` OK |
| ApexNav | `CONTAINER_READY`（仿真 `BLOCKED`） | `vln-apexnav` Up；权重软链就绪；需 ROS+Habitat0.3.1 |
| MSGNav | `CONTAINER_READY`（仿真 `BLOCKED`） | `vln-msgnav` Up；缺场景/SAM-L/API |
| APRR | `CONTAINER_READY`（轻量） | `vln-aprr` Up；入口 `home-robot/runb.sh`、`run_rl.sh` 可见；百度权重未下 |
| SG-Nav | `CONTAINER_READY`（轻量） | `vln-sgnav` Up；`SG_Nav.py` 可见；需 MP3D+GLIP；Habitat 版本应对齐 0.2.4 |
| UniGoal | `CONTAINER_READY`（轻量） | `vln-unigoal` Up；`main.py` 可见；需 HM3D+目标数据集 |

## 已完成（有证据）

| 项 | 证据 |
|----|------|
| 六套源码 + SHA | `reports/source_versions.*`；嵌套 `.git` 已删 |
| 六 compose + 容器 Up | `docker ps --filter name=vln-`；`reports/baseline_validation.md` |
| 共享权重复用/下载 | GroundingDINO（NBV）、MobileSAM 39MB、YOLOv7 291MB、PointNav；路径 `/media/ubuntu/D/VLN_shared/checkpoints/` |
| 轻量审计 | `reports/lightweight_audit.md` |
| 手动下载清单 | `reports/manual_downloads.md`（**P0=HM3D val**） |
| 校验脚本 | `scripts/verify_shared_assets.sh` |

## 阻塞 / 风险

| 项 | 说明 |
|----|------|
| HM3D val 场景 | Matterport 授权；本机无 `.basis` 场景 → 官方闭环阻塞 |
| 镜像为 pytorch 占位 | `vln-habitat024/025` / `vln-apexnav` 现 tag 自 pytorch 2.3.1，**非**正式 Habitat 栈 |
| ObjectNav episodes | 公开 zip 未落地 `shared/datasets_large/objectnav` |
| MSGNav API | `src/const.py` 仍为占位；无密钥不调用付费 API |
| 磁盘 | 根分区约 91%；大文件必须落 D 盘 |

## 下一步（最多 5 项）

1. 用户放入 **HM3D val**（及可选 ObjectNav zip）后跑 `verify_shared_assets.sh`。  
2. 构建并替换正式 `vln-habitat024` / `vln-habitat025` / `vln-apexnav` 镜像。  
3. VLFM：VLM 服务 + 单 episode。  
4. ApexNav → MSGNav 依次单 episode（同时段只跑一个 GPU 导航任务）。  
5. 补全移动机械臂接口锚点与 4070 8GB 判断（`baseline_validation.md` §7）。
