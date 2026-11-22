# Integration delivery draft (2026-11-22) — pending remote ops confirmation

## 统一入口

`adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh`  
+ `adapters/habitat_rangercr10/scripts/run_integrate_defaults.env`

| 开关 | 含义 | 当前默认 |
|------|------|----------|
| `INFLATION_PROFILE` | `legacy018` / `inf020_soft010`（另有 halfwidth* 离线档） | `legacy018`（待 joint4 后定） |
| `BLOCKED_RECOVERY_MODE` | `legacy` / `v2`（opposite→forced_forward） | `legacy`（待 joint4 后定） |
| `ENABLE_NO_FRONTIER_LOOK` | 补视 | `false` |
| `CONTAINER` | 运行时 | `vln-rangercr10-integrate` |
| `CATKIN_DEVEL_PREFIX` | 私有 devel | `.../.catkin_devel_integrate` |

历史入口（仅复现）：`run_apexnav_real_episode_agentA.sh` / `_agentB.sh`、reports 内一次性脚本。

## 来源提交（完整）

| 来源 | SHA |
|------|-----|
| main | `2214550fa5f1b7c98e89b8b31f33fe15150c5415` |
| scale070 | `66869af295099bc6ab5d5eef8d627b0a67538221` |
| A navinf | `d7926f9cd5710ea14219ce54afaeb6a22e5fcd37` |
| B followup | `09fadf4890ce3ff8f55d9639ec87269fde3fc064` |
| B V2 | B clone 未提交；已打入 integrate（`9879e9d` 起）+ 证据 `reports/integration_20261122/b_v2/` |

本地整合分支：`cursor/habitat-rangercr10-scale070-integrate`（目标统一到 `cursor/habitat-rangercr10-scale070` 后推送）。

## B V2 是否收齐

**是。** Look 左右交替（FSM）、opposite_turn→forced_forward、仅 `moved_m>0` 清零 escalate，均已进统一树并经 smoke 加载 `blocked_recovery_mode=v2`。实验证据保留：`RESULTS_post_look_noforward_fix.md`（hy1 dtg≈1.10；**未再进补视**）。

## 合并冲突处理

| 文件 | 决议 |
|------|------|
| `category_map.py` | **保留 scale070**（含 decorative bowl / bottle of detergent） |
| `pairing_index.json` | **保留 scale070**（12 对 / 可靠 9；拒 A 的 2-fixture） |
| `PROGRESS`/`PROCESS`/`MEMORY` | 合并两边有效条目；主会话重写现状 |
| launch | **同时保留** inflation/soft-cost 与 `enable_no_frontier_look` 参数 |

## 验证

| 项 | 状态 |
|----|------|
| 容器 `vln-rangercr10-integrate` | 已起 |
| 重编 plan_env / path_searching / exploration_node | 符号核对通过 |
| smoke hy1 legacy+v2 @40/20 | **OK**：spawn ok，40 步，recovery×2，params 正确 |
| joint4 8 组 | **运行中**（见 `reports/integration_20261122/joint4/`） |

## 拟删除远端分支（待你确认后再删）

条件满足后建议删：

1. `origin/cursor/nav-inflation-halfwidth-softcost`（独有成果已合入 `d7926f9`）
2. `origin/cursor/ranger-target-discovery-followup`（tip `09fadf4` + V2 已收）

**保留**：`main`、`cursor/habitat-rangercr10-scale070`（统一工作分支）。

## 旧 clone / 容器 / 大数据（保留建议）

| 资源 | 用途 | 建议 |
|------|------|------|
| `VLN_Mobilemanipulator_agentA_navinf` | A 隔离证据与 devel 种子 | 暂留至 joint4 交付后 |
| `B_VLN_Mobilemanipulator` | B V2 未提交源与 phase0b 日志 | 暂留（V2 权威工作副本） |
| `B_followup_safe` | 补丁与保全 | **保留** |
| `_agentA_nav_inflation_backup_*` | A 备份 | 可归档 |
| `vln-rangercr10-agentA-navinf` / `agentB-nofrontier` | 旧隔离运行时 | 暂不停；确认无任务后再停 |
| `vln-rangercr10`（共享） | 仍挂旧共享树 | 勿当 integrate 入口 |
| D 盘 `apexnav_real*` 大批次 | 历史评测 | **保留**（追溯） |

## 本轮不自动做的远端操作

- 不 push、不删远端分支、不 force-push。  
- 待 joint4 汇总后一次性给你确认清单。

## 下一项最值得推进的寻物优化（预判）

在 joint4 确认 V2/膨胀交互后，优先打 **执行侧 plan−exec gap**（跟踪/提交滞后与 3D 臂相机碰撞），而不是继续加大规划膨胀；并行评估近距 **SEARCH_OVER_DEPTH→BEST**。
