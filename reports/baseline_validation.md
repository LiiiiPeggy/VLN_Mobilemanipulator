# VLN Baseline Validation Report（进行中）

主机：A6000（Driver 550.163.01 / CUDA 12.4，约 49 GiB）  
工作区：`/home/ubuntu/locomani/VLN_Mobilemanipulator`  
共享大文件：`/media/ubuntu/D/VLN_shared/`  
远端：`git@github.com:LiiiiPeggy/VLN_Mobilemanipulator.git`

## 1. 源码版本与容器状态

| 算法 | Commit | 容器 | 镜像（当前） | 状态 |
|------|--------|------|--------------|------|
| VLFM | `584ed560…` | `vln-vlfm` Up | `vln-habitat024`←暂为 pytorch 2.3.1 标签 | `CONTAINER_READY` |
| ApexNav | `049971b6…` | `vln-apexnav` Up | `vln-apexnav`←同上占位 | `CONTAINER_READY` |
| MSGNav | `03681a17…` | `vln-msgnav` Up | `vln-habitat025`←同上占位 | `CONTAINER_READY` |
| APRR | `046c9c24…` | `vln-aprr` Up | `vln-lite` | `CONTAINER_READY` |
| SG-Nav | `d56863c9…` | `vln-sgnav` Up | `vln-habitat025` 占位 | `CONTAINER_READY` |
| UniGoal | `e2c6d456…` | `vln-unigoal` Up | `vln-habitat025` 占位 | `CONTAINER_READY` |

说明：六个 compose 已 `config` 通过并完成创建验证；GPU 在容器内可见（`torch.cuda.is_available()==True`, A6000）。  
**占位镜像 ≠ Habitat 依赖就绪**。完整 `vln-habitat024/025` / ApexNav 专用栈仍待按 `shared/docker/Dockerfile.*` 构建替换（不中断其它任务）。

嵌套上游 `.git` 已剥离，伞形仓库管理源码。版本机读：`reports/source_versions.json`。

## 2. Docker 镜像复用

| 镜像名 | 构建/来源 | 使用者 |
|--------|-----------|--------|
| `vln-lite` | tag ← `pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime` | APRR；亦作其它占位 |
| `vln-habitat024` | 目标：`Dockerfile.habitat024`；**现为 lite 占位** | VLFM |
| `vln-habitat025` | 目标：`Dockerfile.habitat025`；**现为 lite 占位** | MSGNav, SG-Nav, UniGoal |
| `vln-apexnav` | 目标：`Dockerfile.apexnav`；**现为 lite 占位** | ApexNav |

复现（占位容器）：

```bash
cd /home/ubuntu/locomani/VLN_Mobilemanipulator
docker tag pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime vln-lite:latest
docker tag vln-lite:latest vln-habitat024:latest
docker tag vln-lite:latest vln-habitat025:latest
docker tag vln-lite:latest vln-apexnav:latest
for p in VLFM ApexNav MSGNav APRR SG-Nav UniGoal; do
  docker compose -f baselines/$p/docker-compose.yml up -d --no-build
done
```

## 3. 权重与数据

### 已具备（共享目录）

- GroundingDINO、MobileSAM、YOLOv7-e6e、PointNav（已链到 VLFM/ApexNav `data/`）
- 可选 CLIP ViT-H（DovSG）

### 阻塞官方仿真

- **HM3D val 场景（Matterport 授权）— 本机未找到** → VLFM / ApexNav / MSGNav / UniGoal 官方闭环 `BLOCKED` 直至放入  
  `/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/`
- ObjectNav episode zip（公开）— 待下载到 `.../datasets/objectnav/hm3d/{v1,v2}`
- MSGNav：SAM-L、LLM API；SG-Nav：MP3D + GLIP；APRR：百度权重

详见 [`manual_downloads.md`](manual_downloads.md)。下载完成后运行：`bash scripts/verify_shared_assets.sh`。

## 4. 第一批仿真（VLFM / ApexNav / MSGNav）

| 算法 | 单步推理 | 单 Episode | 小批量 | 备注 |
|------|----------|------------|--------|------|
| VLFM | 未跑 | 未跑 | 未跑 | 权重齐；缺 HM3D + Habitat0.2.4 实装 |
| ApexNav | 未跑 | 未跑 | 未跑 | 需 ROS+Habitat0.3.1；可用预生成 `llm/answers` |
| MSGNav | 未跑 | 未跑 | 未跑 | 缺场景；无付费 API 时仅本地模块 |

## 5. 轻量审计摘要

见 [`lightweight_audit.md`](lightweight_audit.md)。入口均已在容器内确认：`runb.sh`/`run_rl.sh`、`SG_Nav.py`、`main.py`。

## 6. 资源快照

- 磁盘：根分区约 91% 用；大文件放 D 盘（~1.9 TiB 可用）
- GPU：有其它用户进程占用数 GB；本任务容器默认 `sleep infinity`，未抢占训练
- 未改动 FKIE/SSMI/REMANI 与其它项目容器

## 7. 移动机械臂接口（初稿，待第一批实跑后补代码锚点）

共性（ObjectNav 类）：输入 RGB-D + 类别目标；输出离散 Habitat 动作；相机多假定固定于底盘高度。  
ApexNav 另有 ROS / `habitat2ros` 与真实机示例，更贴近 REMANI 替换低层。  
末端 D455：`T_world_camera = T_world_base × T_base_ee(q) × T_ee_camera`，需区分底盘导航目标与相机观察目标。  
4070 8GB：需顺序加载/量化；原版多 VLM 同驻 A6000 可行，笔记本需轻量改版（不作实机结论）。

## 8. 未解决问题

1. HM3D 场景授权与落地  
2. 正式 Habitat 镜像构建（磁盘与时间）  
3. ObjectNav episode 与 MSGNav SAM-L / API  
4. APRR 百度权重可用性验证  

## 9. 后续建议保留的 baseline（暂定）

待第一批实跑后定稿；倾向 **VLFM**（接口清晰、零样本类别导航）、**ApexNav**（ROS/真机示例）、**MSGNav 或 UniGoal**（场景图 + 语言目标，视 API/数据成本）。
