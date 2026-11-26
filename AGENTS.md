# AGENTS.md — 工作规则

本文件供 Cursor 及其他 AI Agent **共享**使用。  
公共工程记忆仅使用仓库内四个文件：`AGENTS.md`、`PROGRESS.md`、`MEMORY.md`、`PROCESS.md`。  
**不**创建 Agent 专属记忆文件，**不**引入数据库、向量检索、记忆服务或复杂维护脚本。  
**不**额外创建 `STATUS` / `TASKS` / `SUMMARY` 等重复状态文件。

## Project Memory

### 任务开始

- 必读：本文件与 `PROGRESS.md`。
- 按需：`MEMORY.md`（环境、依赖、接口、已验证结论）、`PROCESS.md`（历史根因与重要决策）。
- 信任当前代码、配置、容器状态、`reports/` 与 `runs/` 实测证据，胜过过时文档。

### 任务执行

- 以实际代码与运行结果为准；发现记忆过时立即修正对应文件。
- 不得把计划、意图或未跑通步骤写成已完成。
- 同一内容只维护一份：规则→`AGENTS.md`，稳定知识→`MEMORY.md`，最新状态→`PROGRESS.md`，历史过程→`PROCESS.md`；细节证据→`reports/` / `runs/`。
- `MEMORY.md` 不重复 `PROGRESS.md` 的状态表；`PROCESS.md` 不粘贴完整实验报告。

### 任务完成

- 只更新实际发生变化的内容；移除 `PROGRESS.md` 中已过期的待办。
- 已失效的 `MEMORY.md` 结论要修正，并在 `PROCESS.md` 保留变更原因。
- 检查 Git diff；按用户要求提交并安全推送当前工作分支（禁止 force push）。

日常约定：缺乏证据的结论标记为「待验证」，禁止编造。

## 项目范围

- 唯一项目根：`/home/ubuntu/locomani/VLN_Mobilemanipulator`
- GitHub：`git@github.com:LiiiiPeggy/VLN_Mobilemanipulator.git`
- 目标：在六套 ObjectNav / goal-oriented VLN baseline（VLFM、ApexNav、MSGNav、APRR、SG-Nav、UniGoal）上建立可复现评测，再适配移动机械臂平台。
- 相邻工程（**禁止破坏、停改复用其容器/配置**）：
  - `/home/ubuntu/locomani/NBV_Mobilemanipulator`（FKIE / SSMI）
  - `/home/ubuntu/locomani/LocoManip_Lab`（RangerBox-CR10 / AGX 策略）
  - REMANI 及相关实机/仿真栈

## 工作空间与目录

| 路径 | 用途 |
|------|------|
| `baselines/<Name>/` | 六个 baseline 源码（umbrella 管理；见 `reports/source_versions.md`） |
| `shared/docker/` | 可共享的 Dockerfile（按 Habitat/PyTorch 族划分） |
| `shared/{datasets,checkpoints,cache}/` | 小文件占位；大资源走 `*_large` 符号链接 |
| `shared/{datasets,checkpoints,cache,runs}_large` | → `/media/ubuntu/D/VLN_shared/...` |
| `baselines/<Name>/docker-compose.yml` | 该 baseline 的独立 compose（独立 project/容器名） |
| `runs/<Name>/` | 轻量运行摘要（可进 Git 的 json/csv/txt/md） |
| `reports/` | 审计与复现报告 |
| `scripts/` | 仓库级工具脚本 |

## Git 管理规则

1. 六个 baseline 以 umbrella 仓库统一版本；上游 SHA 记录在 `reports/source_versions.md`。
2. 嵌套 `.git` 目录被 `.gitignore` 忽略；导入后应运行 `scripts/strip_nested_git.py` 清理（当前是否已清理以实测为准，见 `PROGRESS.md`）。
3. **不推送**：模型权重、数据集、缓存、大型日志/视频（已由根 `.gitignore` 覆盖）。
4. 不提交密钥（`.env`、token、credentials）。
5. 不随意改写上游评测协议、指标定义或默认 split；适配层应外置或可开关。
6. 提交前核对：记忆文件与代码/日志一致；勿提交本应忽略的大文件。

## Docker 与环境隔离

1. 宿主机保持 Ubuntu 22.04 + 现有 NVIDIA 驱动；不重装、不降级驱动/CUDA。
2. 六个 baseline 使用**独立** Docker Compose / 容器；依赖兼容时可**共享镜像**，但容器名与 compose project 必须分离。
3. 不停止、不修改、不复用他人容器（含 `nbv_fkie`、`nbv_ssmi`、`lxy`/`zxg`/…）；不执行 `docker system prune`；不删除他人镜像/网络/卷。
4. 不破坏已有 NBV、FKIE、SSMI、REMANI 工程及其 compose。
5. GPU 使用最小必要可见设备；避免与占用大量显存的他人进程恶性争抢（先观察再占用）。

## Baseline 验证层级（必须区分）

记录成功时严格区分，状态枚举见 `PROGRESS.md`：

1. `CLONED` — 源码就位且 SHA 可核对  
2. `CONTAINER_READY` — 对应镜像/compose 可启动  
3. `DEPENDENCIES_READY` — 容器/环境内依赖可 import  
4. `MODEL_LOADED` — 所需权重加载成功  
5. `SINGLE_EPISODE_OK` — 单 episode 跑通并有 `runs/` 证据  
6. `BATCH_OK` — 小批量评测完成并有结果路径  
7. `BLOCKED` — 阻塞（须指向日志/报告）

「镜像 build 成功」≠「单 episode 成功」；不得跳级宣称。

## 修改原则

- 修改已验证方案前，检查 `MEMORY.md` / `PROCESS.md` 与 `reports/`、`runs/` 证据。
- 不要仅因新方案看起来更简洁就替换已有有效实现。
- 本轮默认：**不重新安装算法、不启动训练、不跑额外仿真、不重构原有工程**，除非任务明确要求。

## 文档维护

| 文件 | 职责 |
|------|------|
| `AGENTS.md` | 开发规则与记忆使用流程（本文件） |
| `PROGRESS.md` | 当前状态与下一步（只保留最新） |
| `MEMORY.md` | 长期有效、可复用知识 |
| `PROCESS.md` | 重要工程历史与根因（无故不删） |
| `reports/`、`runs/` | 实验报告与完整/摘要数据 |

更新记忆前先读现有内容并保留有效信息。

## 主会话与子代理（Ranger 整合期）

- **唯一工作区**：`/home/ubuntu/locomani/VLN_Mobilemanipulator`（禁止再开 `*_integrate` / `*_agentA*` / `B_VLN_*` 并列目录作日常入口）。
- **主会话唯一统筹**：分支整合、公共文件、编译、仿真调度、结果验收与最终交付。统一工作分支：`cursor/habitat-rangercr10-scale070`。
- **子代理**：仅承担边界清晰的任务（审查、日志分析、指标汇总）。每项任务须写明输入、负责文件、输出；**同一文件串行**；默认在同一工作区内改码，由主会话验收。
- **子代理 Git**：不得另开并列 clone 作长期工作区；不得 push 公共远端（除非主会话明确要求）；不得动他人容器。
- **在线仿真锁**：主会话统一调度。取得 `/home/ubuntu/locomani/_sim_host_run.lock` 后方可启动仿真；持有至相关运行结束再释放。等跑期间可并行分析已有日志。
- **统一运行入口**：`adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh`（可先 `source .../run_integrate_defaults.env`）。  
  关键开关：`INFLATION_PROFILE`（**默认 `inf020_soft010`**|`legacy018`）、`ENABLE_NO_FRONTIER_LOOK`、`BLOCKED_RECOVERY_MODE`、`LOOK_BACKEND`（**默认 `ppo_ee_rpy`**|`gimbal`）、`EXEC_BACKEND`（**默认 `ppo_chassis`**|`kinematic`）、`REVERSE_PLANNING_MODE`（**默认 `C`**|`A`|`B`）、`PPO_LOOK_DIR`、`PPO_CHASSIS_DIR`、`PPO_RAISE_JSON`（默认 z040）、`CONTAINER`、`CATKIN_DEVEL_PREFIX`。 
  **默认保持**：PPO LOOK/EXEC；**规划默认 `inf020_soft010`（硬膨胀 0.20 + soft R=0.10/w=2.0 + lock）+ `REVERSE_PLANNING_MODE=C`**。历史复现可显式设 `legacy018` / `A|B`；未经用户明确要求勿改回。
  **Demo 录制默认 2fps**（`apexnav_ranger_paper_demo.mp4` / `ffmpeg -framerate 2`）；**未经用户明确要求勿自动跑 7fps**。仅当用户点名要 7fps / 查轮胎运动时再用 `run_demo_7fps.sh`。  
  `run_apexnav_real_episode_agentA.sh` / `_agentB.sh` 及 reports 内一次性脚本仅作历史复现，不作新实验入口。
- **容器**：整合评测用 `vln-rangercr10-integrate`（`docker-compose.integrate.yml`，挂载本仓根目录）。`vln-rangercr10-agentA-navinf` / `vln-rangercr10-agentB-nofrontier` 已退役，勿再启动。
- **机载 RGB 截图**：用 `env.observe_ee_only()`；禁止只调 `sync_agent_sensors()` 后读 `ee_rgb`（会贴地假视角）。
- **中间产物**：污染/失败重试/wrapper pid/`*_clear` 重复件/look bundle `*.jsonl` 可删；保留最终 `ppo_look_*`、成功 demo 与证据目录。
