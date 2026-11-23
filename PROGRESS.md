# PROGRESS.md — 当前状态

更新时间：2026-11-23（soft_reach yaw-aware 核验/修正；默认仍 false）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：固定云台 ApexNav 停止门候选已 yaw-aware 修正；可开主动感知实验开关，默认保守。工作树：`/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate`。

## 远端基线

| 项 | 值 |
|----|-----|
| 工作分支 | `origin/cursor/habitat-rangercr10-scale070` |
| 核验起点 tip | `55e8c8dec85496edf8355d90eaef4012881a6d4c` |
| 已删远端 A/B | 已完成（不再重复） |

## soft_reach yaw-aware（本轮）

- 已发布 any_stuck（`ef71d31`）把 **成功 TURN（Δyaw=±30°）** 因 XY 不变误判为卡住 → 误 STOP。
- 修正：`callActionPlanner` 按动作用 Δxy / Δyaw；LOOK 不因 XY 闲置触发；开关默认 false。
- hy1 yaw-aware：TRUNC TURN dyaw=−0.087 → 合法 soft_reach STOP；SR_proxy 成立（dtg≈0.483）。
- Dd4b：未进近距，无 STOP（与先前一致）。
- 正向 OFF/ON：**缺口**（无同配置 OFF 成功任务）。
- 证据：`reports/integration_20261122/stop_fix/SOFT_REACH_YAW_AUDIT.md` + `evidence_hy1_*`

## 默认保持

ObjectHold=3.0，legacy018，recovery=legacy，soft_reach_on_any_stuck=false。

## 下一步（最多 5）

1. 主动感知实验（候选开关，不改默认）。  
2. 补合法 spawn 的正向 OFF/ON。  
3. Dd4b 发现/通行单独查。  
4. 大批量暂缓。  
5. 确认本轮 tip SHA 已 push。
