# PROCESS.md — 工程历史

追加有价值的重要事件。完整日志留在 `runs/` / `reports/`，此处只保留摘要。  
格式：日期、模块、问题、操作、实测结果、结论、相关路径或 commit。

---

## 2026-10-29 仓库初始化与源码导入

**模块**：umbrella / baselines  

**问题**：需在单仓管理六套 ObjectNav/VLN baseline，同时与 NBV、LocoManip 等工程共存于同一 A6000 主机。  

**操作**：

- 创建 `/home/ubuntu/locomani/VLN_Mobilemanipulator`，远程 `git@github.com:LiiiiPeggy/VLN_Mobilemanipulator.git`。
- 克隆六套上游到 `baselines/`，记录 SHA 于 `reports/source_versions.md`。
- 配置 `.gitignore`（权重、数据集、缓存、嵌套 `.git`）。
- `shared/{datasets,checkpoints,cache,runs}_large` 软链至 `/media/ubuntu/D/VLN_shared/...`（根分区空间紧张）。

**实测结果**：

- SHA 与报告一致（见 `reports/source_versions.json`）。
- 宿主机：Ubuntu 22.04.5、RTX A6000、Driver 550.163.01、Docker 27.3.1。
- 他人容器 `nbv_fkie` 等仍在运行；未改动。

**结论**：导入阶段完成；**不等于**任何 baseline 可运行。大数据必须走 D 盘。

**相关**：`reports/source_versions.md`、`.gitignore`、`shared/`

---

## 2026-10-29 剥离嵌套 .git

**模块**：Git  

**问题**：各 baseline 自带 `.git`，与 umbrella 冲突；且 `.gitignore` 的 `**/.git/` 会使嵌套历史无法被 umbrella 跟踪源码。  

**操作**：编写并执行 `scripts/strip_nested_git.py`（先记录 SHA，再删除 `baselines/*` 下嵌套 `.git`）。  

**实测结果**：`find baselines -name .git` 为空；写出 `reports/source_versions.json`。  

**结论**：源码改由 umbrella 单一 Git 管理；上游 URL/SHA 以 `reports/source_versions.*` 为准。若需再同步上游，应重新 clone 到临时目录后按文件同步，而不是恢复嵌套仓库。  

**相关**：`scripts/strip_nested_git.py`、`reports/source_versions.json`

---

## 2026-10-29 Docker 脚手架（未 build）

**模块**：Docker  

**问题**：六套 Habitat/PyTorch 版本互斥，需独立 compose，并允许共享兼容镜像。  

**操作**：新增

- `shared/docker/Dockerfile.habitat024`（VLFM 类，CUDA 11.7 + torch 1.12）
- `shared/docker/Dockerfile.habitat025`（MSGNav 类，CUDA 11.8 + torch 2.0 + habitat-sim 0.2.5）
- `shared/docker/Dockerfile.apexnav`（ApexNav，CUDA 12.1 + torch 2.5）
- `shared/docker/Dockerfile.lite`（APRR 等轻量审计）
- 六个 `baselines/<Name>/docker-compose.yml`（独立 `name:` / `container_name: vln-*`）

**实测结果**：文件就位；`docker images` **无** `vln-*`；**无**对应容器。Dockerfile 中部分 `pip install ... || true` 表明依赖安装仍是草稿。  

**结论**：仅达到「编排草稿」，未达 `CONTAINER_READY`。SG-Nav（文档 0.2.4）与 UniGoal（文档 0.2.3）暂挂 `vln-habitat025`，**版本映射待校正**后再 build。  

**相关**：`shared/docker/`、`baselines/*/docker-compose.yml`、`PROGRESS.md`

---

## 2026-10-29 建立轻量工程记忆

**模块**：文档 / Agent 协作  

**问题**：多会话 Cursor 需恢复进度、避免重复安装与误改 NBV/他人环境。  

**操作**：按 NBV_Mobilemanipulator 同构四文件落地 `AGENTS.md`、`MEMORY.md`、`PROGRESS.md`、本文件；内容以当时代码/Git/Docker/磁盘证据为准，不把计划写成完成。  

**实测结果**：四文件可读；与 `baselines/`、`shared/docker/`、空 `runs/`、无 `vln-*` 镜像一致。  

**结论**：后续会话任务开始必读 `AGENTS.md` + `PROGRESS.md`；状态变更只改变化项。  

**相关**：四记忆文件；参照 `/home/ubuntu/locomani/NBV_Mobilemanipulator/AGENTS.md`
