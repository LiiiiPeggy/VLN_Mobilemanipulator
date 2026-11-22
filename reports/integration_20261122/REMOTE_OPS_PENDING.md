# 待你一次确认的远端操作清单（本地验证已完成）

## 建议提交（本地已有，尚未 push）

工作分支：`cursor/habitat-rangercr10-scale070-integrate`（目标合并进 `cursor/habitat-rangercr10-scale070`）

已有本地提交（整合相关，举例）：
- `89fdafb` Merge A nav-inflation
- `022bbdb` Merge B followup
- `9879e9d` B V2 switch + unified entry
- `1030eb7` joint4 harness
- `a77f7d9` delivery draft

**未提交工作区改动（需纳入下一提交）**：
- PPO 默认 → `model_9999`（`constants.py` / `run_ppo_raise_then_apexnav_s070.sh` / README / MEMORY / PROGRESS）
- joint4 报告与汇总（`reports/integration_20261122/joint4/**`）
- approach_fix：ObjectHold 接线 + 报告（`exploration_fsm*` / launch / `run_apexnav_real_episode.sh` / `reports/integration_20261122/approach_fix/**`）
- 其他 integration 审计文件

## 建议推送

1. 快进/合并 `cursor/habitat-rangercr10-scale070-integrate` → `cursor/habitat-rangercr10-scale070`
2. `git push origin cursor/habitat-rangercr10-scale070`（**禁止 force**）

## 建议删除的远端分支（独有成果已合入）

| 分支 | tip | 条件 |
|------|-----|------|
| `origin/cursor/nav-inflation-halfwidth-softcost` | `d7926f9` | 已合入；A 报告可追溯 |
| `origin/cursor/ranger-target-discovery-followup` | `09fadf4` + V2 补丁 | 已合入；B 证据在 `reports/.../b_v2` 与 paired_b |

**保留**：`main`、`cursor/habitat-rangercr10-scale070`

## 建议归档/暂留（勿删数据）

| 资源 | 建议 |
|------|------|
| `VLN_Mobilemanipulator_agentA_navinf` | 暂留至统一分支 push 后 |
| `B_VLN_Mobilemanipulator` + `B_followup_safe` | 暂留（V2 工作副本/补丁） |
| `vln-rangercr10-agentA-navinf` / `agentB-nofrontier` | 确认无任务后再停 |
| D 盘 joint4 / 历史 `apexnav_real*` | **保留**追溯 |
| `_agentA_nav_inflation_backup_*` | 可归档 |

## 执行状态

- 用户已授权提交/推送/核验后删 A·B 远端分支（2026-11-22）。
- 执行记录见本节提交后的 `REMOTE_OPS_DONE.md`（推送完成后写入）。
