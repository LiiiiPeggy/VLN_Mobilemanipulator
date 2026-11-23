# PROGRESS.md — 当前状态

更新时间：2026-11-23（stop_fix：soft_reach_on_any_stuck 配对完成；默认仍 false）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：接近/停止门候选已交付；部署基线可支撑主动感知实验开关，但默认仍保守。工作树：`/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate`。

## 远端基线

| 项 | 值 |
|----|-----|
| 工作分支目标 | `origin/cursor/habitat-rangercr10-scale070` |
| 修复前基线 SHA | `383691d3becf0372b575dceecefb355d542ecb9c` |
| 当前 tip（含 soft_reach 候选） | `ef71d3190a1f78191f9d4bee1de4970cd9dcf64e` |
| 已删远端 | `cursor/nav-inflation-halfwidth-softcost`、`cursor/ranger-target-discovery-followup` |
| 保留 | `main`、`cursor/habitat-rangercr10-scale070` |
| 记录 | `reports/integration_20261122/REMOTE_OPS_DONE.md` |

## stop_fix 结论（摘录）

- 路径 B：hy1 ON（hold=8）卡在 soft REACH 要求 `MOVE_FORWARD`；next_pos≈0.25 m 时 TURN 被拒。
- 修复：`soft_reach_on_any_stuck`（**默认 false**）；hy1 ON→STOP（soft_reach dist=0.25），SR_proxy 成立（dtg_eval=0.525≤1.0）。
- Dd4b/ziup_plant3：未进入近距，无 STOP（发现/通行问题，非本门）。
- 证据：`reports/integration_20261122/stop_fix/STOP_FIX_REPORT.md`、`approach_fix/ON_FINAL_BLOCKER.md`

## approach_fix（仍有效）

- ObjectHold 3.0→8.0：hy1 更近仍无 STOP；默认保持 **3.0**。
- 证据：`reports/integration_20261122/approach_fix/APPROACH_FIX_REPORT.md`

## joint4（仍有效）

- 默认建议：`INFLATION_PROFILE=legacy018`，`BLOCKED_RECOVERY_MODE=legacy`；v2 / soft_reach 为候选开关。
- 证据：`reports/integration_20261122/joint4/JOINT4_REPORT.md`

## 默认保持

| 参数 | 默认 | 候选 |
|------|------|------|
| ObjectHold | 3.0 | 8.0 |
| inflation | legacy018 | — |
| recovery | legacy | v2 |
| soft_reach_on_any_stuck | false | true |
| PPO | model_9999（未调用） | — |

## 下一步（最多 5）

1. 主动感知实验：在固定 soft_reach/ObjectHold 候选上开实验开关，不改默认。  
2. Dd4b 类「未进入近距」：单独查目标发现/通行，不扩大 Hold。  
3. 找合法 spawn 的历史成功任务做扩样回归（tee_chair4 仍 invalid_initial_penetration）。  
4. 确认 soft_reach 推送后的 scale070 tip SHA。  
5. 大批量评测暂缓。
