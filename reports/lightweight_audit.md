# APRR / SG-Nav / UniGoal 轻量可用性检查

检查方式：源码与 README 审计 + 独立容器挂载/GPU 冒烟（完整 Habitat 训练栈未安装）。

## APRR — `046c9c24…`

| 项 | 结果 |
|----|------|
| 状态 | `CONTAINER_READY`（轻量） |
| 入口 | `home-robot/runb.sh`（baseline）、`home-robot/run_rl.sh`（APRR） |
| 依赖 | HomeRobot / Habitat；建议官方 Docker `fairembodied/habitat-challenge`；YOLO-World + SAM |
| 权重 | 百度网盘：https://pan.baidu.com/s/1bp8iO3GBbmfE9bZ93IKQng?pwd=uw53 （**需手动下载**） |
| 子模块 | `home-robot/.gitmodules` 含 Detic、detectron2、OVMM/HSSD 数据等；数据类 submodule 未拉全 |
| 两阶段 | README：Active Perception + Rule-Guided RL；`runb` vs `run_rl` |
| 结论 | 可审计入口与脚本；完整推理需 HomeRobot 镜像 + 网盘权重 + OVMM/场景数据。**不默认训练。** |

## SG-Nav — `d56863c9…`

| 项 | 结果 |
|----|------|
| 状态 | `CONTAINER_READY`（轻量） |
| 入口 | `SG_Nav.py`（`SG_Nav_Agent`） |
| 栈 | habitat-sim **0.2.4** + 仓内 `habitat-lab`；需替换 `habitat_sim/agent/agent.py` |
| 视觉 | GroundingDINO、SAM vit_h、GLIP large；LLM：Ollama `llama3.2-vision` |
| 数据 | **MP3D** 场景（非 HM3D）+ ObjectNav MP3D episodes；清华云盘 episode 包 |
| 注意 | 需改 Habitat 源码 → **仅容器内**；与 MSGNav 的 0.2.5 不完全兼容，当前 compose 暂共用 `vln-habitat025` 占位标签，正式跑需单独 0.2.4 镜像 |
| 结论 | 入口清晰；缺 MP3D 授权数据与 GLIP/SAM-H 权重前无法官方评测。 |

## UniGoal — `e2c6d456…`

| 项 | 结果 |
|----|------|
| 状态 | `CONTAINER_READY`（轻量） |
| 入口 | `main.py`；`--goal_type`：`ins-image` / `text`（README：object-goal 仍待完善） |
| 栈 | habitat-sim/lab **0.2.3**；Grounded-SAM；Ollama 或 GPT-4o |
| 数据 | HM3D val 场景 + instance-image-goal v3 + text-goal（Google Drive） |
| 真实机器人 | `--real_world` 开关存在；需对照 `src/envs` 与运动接口再接 REMANI |
| 结论 | 文本/实例图像目标入口已在仓库实现；类别目标按 README 仍未完全支持。勿把论文能力等同于当前代码。 |

## 共享阻塞

1. **HM3D val 场景**（Matterport 授权）— VLFM/ApexNav/MSGNav/UniGoal 官方闭环共同依赖。  
2. APRR 百度权重、SG-Nav 的 MP3D/GLIP、UniGoal text-goal zip — 见 `manual_downloads.md` 补充项。
