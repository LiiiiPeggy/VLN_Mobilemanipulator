# PROGRESS.md — 当前状态

更新时间：2026-11-22（主会话：A+B+V2 已合入；关联库已重编；joint4 验证启动中）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：**统一分支本地整合完成 → 最小联合验证**。工作树：`/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate`（`cursor/habitat-rangercr10-scale070-integrate` @ 见 `git rev-parse HEAD`）。

## 整合来源（完整 SHA）

| 来源 | 分支 | SHA |
|------|------|-----|
| main | `main` | `2214550fa5f1b7c98e89b8b31f33fe15150c5415` |
| base | `cursor/habitat-rangercr10-scale070` | `66869af295099bc6ab5d5eef8d627b0a67538221` |
| A | `cursor/nav-inflation-halfwidth-softcost` | `d7926f9cd5710ea14219ce54afaeb6a22e5fcd37` |
| B tip | `cursor/ranger-target-discovery-followup` | `09fadf4890ce3ff8f55d9639ec87269fde3fc064` |
| B V2 | B clone 未提交 → 已打入 + 开关 | `BLOCKED_RECOVERY_MODE=v2`；证据 `reports/integration_20261122/b_v2/` |

## 统一入口

`adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh` + `run_integrate_defaults.env`  
开关：`INFLATION_PROFILE` / `ENABLE_NO_FRONTIER_LOOK` / `BLOCKED_RECOVERY_MODE` / `CONTAINER=vln-rangercr10-integrate` / `CATKIN_DEVEL_PREFIX=.../.catkin_devel_integrate`

## 编译核对

| 库 | 符号证据 |
|----|----------|
| `libpath_searching.so` | `soft_cost enabled` |
| `libplan_env.so` | `lock_obstacles_inflation=true` |
| `exploration_node` | `NoFrontierLook` / `enable_no_frontier_look` |

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| joint4 结果未齐 | `reports/integration_20261122/joint4/` | 提前宣称寻物收益 |
| 规划净空≠执行净空 | A sofa/narrow | 只加大膨胀 |
| toilet_2 init 异常 | A narrow abort | 当有效失败 |

## 下一步（最多 5）

1. 跑完 joint4（hy1 + dd4b × 4 组）并写汇总。  
2. 两例有收益则加一原成功任务回归。  
3. 定默认：`INFLATION_PROFILE` / `BLOCKED_RECOVERY_MODE`。  
4. 本地交付清单：待推送提交、拟删远端分支、旧 clone/容器保留建议。  
5. 下一项寻物优化候选：执行侧 plan−exec gap / over-depth，而非继续加膨胀。
