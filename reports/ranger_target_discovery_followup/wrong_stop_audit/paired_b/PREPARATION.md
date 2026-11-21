# Agent B 配对准备（等 A 释放锁后再跑）

B HEAD 须含本地提交 `a8d16ab`。A 容器 `vln-rangercr10-agentA-navinf` **永不复用**。

## 专用资源

| 项 | 路径 / 名 |
|----|-----------|
| 源码 | `/home/ubuntu/locomani/B_VLN_Mobilemanipulator` |
| Compose | `adapters/habitat_rangercr10/docker-compose.agentB_nofrontier.yml` |
| 容器 | `vln-rangercr10-agentB-nofrontier` |
| 挂载 | **仅** B clone → `/workspace/VLN_Mobilemanipulator`（不把 ApexNav 双挂到 `/workspace/ApexNav`） |
| devel | `/workspace/VLN_Mobilemanipulator/.catkin_devel_agentB` |
| 输出 | `/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_agentB_nofrontier` |
| 报告 | `reports/.../wrong_stop_audit/paired_b/results/` |
| 主机锁（A/B 共用，启动以取得为准） | `/home/ubuntu/locomani/_sim_host_run.lock` |
| 锁助手 | `adapters/habitat_rangercr10/scripts/host_sim_lock.sh` |
| A 释放旗标（仅交接记录） | `/home/ubuntu/locomani/B_followup_safe/host_lock/A_RELEASED_LOCK` 或 `A_RELEASED_LOCK=1` |

## 源码安全

- `ensure_apex_symlink_safe.sh`：**禁止**对非 symlink 的 `/workspace/ApexNav` 执行 `rm -rf`。
- 配对入口只用 `run_apexnav_real_episode_agentB.sh` / `run_nofrontier_look_paired_agentB.sh`。
- 共享脚本 `run_apexnav_real_episode.sh` 在 ApexNav 被 bind-mount 时有清源码风险；B **不调用**。

## 配对清单

`lists/paired_manifest.json`

1. **phase0_switch_verify**：`hy1_plant_0` × OFF/ON（同 spawn 冻结 JSON、预算 150/100）  
2. **phase1_small_batch**（开关确认后）：`yr17_tv_0`、`ef36_plant_4`、`hy1_chair_3` + 成功对照 `dd4b_plant_5`

冻结 spawn：`frozen_spawns/*_start_pose.json`（来自原审计 run，保证同起点）。

## 启动（仅在 A 释放后）

```bash
# 交接旗标（非主机锁）：
touch /home/ubuntu/locomani/B_followup_safe/host_lock/A_RELEASED_LOCK
# 取得主机锁后再跑（脚本内会 acquire `_sim_host_run.lock`）：
cd /home/ubuntu/locomani/B_VLN_Mobilemanipulator
PHASE=phase0_switch_verify \
  bash adapters/habitat_rangercr10/scripts/run_nofrontier_look_paired_agentB.sh
# 首对确认后再：
PHASE=phase1_small_batch SKIP_BUILD=1 \
  bash adapters/habitat_rangercr10/scripts/run_nofrontier_look_paired_agentB.sh
```

每例四问见 `analyze_nofrontier_pair_run.py`；另标「延迟 STOP」「预算耗尽」。  
结束后脚本 `trap` 释放 `_sim_host_run.lock`（owner=`agentB_nofrontier`）。

## 当前状态

见最新配对 runs / `paired_b/results/`；A 容器可保留。
