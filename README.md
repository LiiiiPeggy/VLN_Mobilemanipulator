# VLN_Mobilemanipulator

A6000 上统一管理的视觉语言导航（VLN / ObjectNav）基线工作空间，面向后续 Ranger + CR10 移动机械臂接入。

## 目录

```text
VLN_Mobilemanipulator/
├── baselines/          # 六个算法源码 + 各自 docker-compose.yml
├── shared/             # 仓库内轻量共享 + docker/Dockerfile*
├── scripts/            # 安装、校验、审计脚本
├── reports/            # 验证报告与下载清单
└── runs/               # 小摘要；大体量结果在 D 盘
```

大文件共享根目录（宿主机）：`/media/ubuntu/D/VLN_shared/{datasets,checkpoints,cache,runs}`  
软链：`shared/*_large` → 上述路径。

## 六个基线

| 项目 | 本轮目标 | 容器名 | 镜像策略 |
|------|----------|--------|----------|
| VLFM | 完整仿真 | `vln-vlfm` | `vln-habitat024`（Habitat 0.2.4 栈） |
| ApexNav | 完整仿真 | `vln-apexnav` | `vln-apexnav`（Habitat 0.3.1 + ROS 路径） |
| MSGNav | 完整仿真 | `vln-msgnav` | `vln-habitat025` |
| APRR | 轻量检查 | `vln-aprr` | `vln-lite` |
| SG-Nav | 轻量检查 | `vln-sgnav` | 与 MSGNav 共享 `vln-habitat025` |
| UniGoal | 轻量检查 | `vln-unigoal` | 与 MSGNav 共享 `vln-habitat025` |

源码版本见 [`reports/source_versions.md`](reports/source_versions.md)。

## 快速启动容器

```bash
# 轻量审计容器（复用已有 pytorch 镜像标签）
cd baselines/APRR && docker compose up -d --no-build

# 第一批（镜像构建完成后）
cd baselines/VLFM && docker compose up -d
cd baselines/ApexNav && docker compose up -d
cd baselines/MSGNav && docker compose up -d
```

## 数据与权重

- **已复用**：GroundingDINO、PointNav、可选 CLIP（见 `reports/manual_downloads.md`）
- **需你准备**：HM3D val 场景（Matterport 授权）；可选 ObjectNav episode / SAM-L
- 校验：`bash scripts/verify_shared_assets.sh`

## 状态报告

主报告：[`reports/baseline_validation.md`](reports/baseline_validation.md)（持续更新）

远端：`git@github.com:LiiiiPeggy/VLN_Mobilemanipulator.git`
