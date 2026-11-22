# PROGRESS.md — 当前状态

更新时间：2026-11-22（approach_fix：ObjectHold max_dist 配对完成；默认仍 3.0）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：部署基线接近/停止最小修复 + 小规模配对。工作树：`/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate`。

## 整合来源（完整 SHA）

| 来源 | SHA |
|------|-----|
| main | `2214550fa5f1b7c98e89b8b31f33fe15150c5415` |
| scale070 | `66869af295099bc6ab5d5eef8d627b0a67538221` |
| A | `d7926f9cd5710ea14219ce54afaeb6a22e5fcd37` |
| B tip | `09fadf4890ce3ff8f55d9639ec87269fde3fc064` |
| joint4 冻结 | `a77f7d9` |
| approach_fix | ObjectHold 参数接线 + 重编 integrate `exploration_node`（未提交） |

## approach_fix 结论（摘录）

- 唯一变量：`OBJECT_HOLD_MAX_DIST` 3.0→8.0；hy1/Dd4b 固定 `legacy018`+`v2`；无 PPO。
- hy1：dtg 0.485→**0.167**，moved 5.7→**9.2**，ObjectHold keep 0→26；**仍无 STOP/成功**。
- Dd4b：持平（无收益、无退化）。
- 历史成功回归：**缺口**（tee_chair4 现栈 `invalid_initial_penetration`）。
- **默认保持 3.0**；候选 8.0 待扩样。
- 证据：`reports/integration_20261122/approach_fix/APPROACH_FIX_REPORT.md`

## joint4（仍有效）

- 默认建议：`INFLATION_PROFILE=legacy018`，`BLOCKED_RECOVERY_MODE=legacy`；v2 候选。
- 证据：`reports/integration_20261122/joint4/JOINT4_REPORT.md`

## 默认 PPO 权重

`models/ranger_cr10/model_9999.pt`；抬臂验证未跑；本批未调用 PPO。

## 下一步（最多 5）

1. SEARCH 近距 REACH（0.20/0.45）与转角执行挡（D455/夹爪）——在 ObjectHold 候选之上单点修。  
2. 扩样评测 `OBJECT_HOLD_MAX_DIST=8.0`（含窄通道）；默认暂不翻。  
3. 找可比成功任务（合法 spawn + 现栈 SR_proxy）再做回归。  
4. 提交：PPO 默认 + joint4/approach_fix 报告 + ObjectHold 接线；确认后再合入/push scale070。  
5. 确认后删 A/B 远端分支（`REMOTE_OPS_PENDING.md`）。
