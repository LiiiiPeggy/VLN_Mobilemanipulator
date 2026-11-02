# 镜像可复现性对照（2026-11-01）

区分两级：**已写回**（脚本/Dockerfile 中有对应步骤）vs **已通过干净构建验证**（独立 tag 从 Dockerfile 无 commit 层成功 build）。

| 镜像 tag | Image ID | 角色 | 已写回 | 干净构建验证 | 备注 |
|----------|----------|------|--------|--------------|------|
| `vln-habitat024:build` / `:latest` | `fe6b1ca643fd` | VLFM 运行 | `Dockerfile.habitat024` 核心栈 + `scripts/install/vlfm_runtime_deps.sh` | **否**（当前 latest 含 `docker commit` 的 LAVIS/GD/SAM 层） | 独立验证 tag 目标：`vln-habitat024:repro-verify`（磁盘紧张时延后） |
| `vln-habitat025:build` / `:latest` | `ff049f5c4eed` | MSGNav 基座 | `Dockerfile.habitat025` | **是**（base build EXIT:0，sim 0.2.5） | |
| `vln-habitat025:msgnav-deps` | `1b1bdc94f963` | MSGNav 评测 | `scripts/install/msgnav_runtime_deps.sh` | **否**（commit 层） | compose 应钉此 tag |
| `vln-apexnav:build` | `118284656358` | ApexNav 基座 | `Dockerfile.apexnav`（numpy 钉死） | **是**（smoke OK） | |
| `vln-apexnav:single-ep-deps` / `:latest` | `50e76a268b26` | ApexNav 评测 | `scripts/install/apexnav_runtime_deps.sh` + ROS 说明 | **否**（含 Focal Noetic 拷贝 + catkin） | 长期应 `ros:noetic` 专用 Dockerfile |

根分区 ~93% 满；本轮**不覆盖**可用 tag。若做干净验证，仅 build 到 `*:repro-verify`，成功后再考虑切换 compose。

## 推荐 compose 钉死

- VLFM → `vln-habitat024:latest`（=`fe6b1ca643fd`）直至 `repro-verify` 通过  
- MSGNav → `vln-habitat025:msgnav-deps`  
- ApexNav → `vln-apexnav:single-ep-deps`  
