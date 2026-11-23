# PROGRESS.md — 当前状态

更新时间：2026-11-24（HY1 倒车规划 A/B/C 消融首轮完成；**正式默认仍 REVERSE_PLANNING_MODE=A / EXEC=ppo_chassis**）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：默认评测抬臂/LOOK/底盘低层均走 teleop-PPO；ApexNav 高层规划。HY1 狭窄贴墙案例上完成倒车消融首轮。  
**唯一工作区**：`/home/ubuntu/locomani/VLN_Mobilemanipulator`（分支 `cursor/habitat-rangercr10-scale070`）。  
**容器**：`vln-rangercr10-integrate`。

## 已完成（本轮）

- `LOOK_BACKEND=ppo_ee_rpy` + `EXEC_BACKEND=ppo_chassis` + PPO raise z040（默认保持）。
- **HY1 reverse ablation**：`REVERSE_PLANNING_MODE=A|B|C`（默认 A，不改正式部署）。
  - PPO 倒车实测 OK（0.15/0.25/0.40 m）：`.../ppo_reverse_validation_model9999/`
  - A 基线：`.../ppo_chassis_hy1_20261123_220210_hy1_plant_0`（moved≈0.85, blocked=29）
  - B：`.../hy1_rev_B_orig_r1_20261124_050148_...`（moved≈2.92, rev×4≈1.16 m, blocked=23）
  - C：`.../hy1_rev_C_orig_r3_20261124_065931_...`（moved≈4.23, rev×6≈1.74 m, blocked=13, hybrid=4）
  - 报告/图：`reports/hy1_reverse_planning_ablation.md`；`reports/hy1_reverse_planning/{metrics.csv,figures,plot_metrics.py}`
- KinoAstar 确认为 Dubins+非负 arc；方案 C 用 PPO 基元 Hybrid A*（非 Reeds–Shepp 宣称）。

## 默认保持

ObjectHold=3.0，legacy018，recovery=legacy，soft_reach=false，LOOK=ppo_ee_rpy，**exec=ppo_chassis**，PPO raise z040，**REVERSE_PLANNING_MODE=A**。

## 扩展预算（已跑）

- B ext：moved≈3.84，blocked=60，rev≈1.74 m（`hy1_rev_B_ext_r1_20261124_070540_...`）
- C ext：moved≈5.27，blocked=50，rev≈1.74 m，hybrid_calls=38（`hy1_rev_C_ext_r1_20261124_071619_...`）

## 下一步（最多 5）

1. 开阔/另一狭窄场景小回归。  
2. 少量重复一致性（或标明确定性）。  
3. 跑前强制清理残留 exploration_node（已写入运维注意）。  
4. 用户确认后再考虑是否将 B/C 升为可选默认（当前禁止，默认 A）。  
5. 大批量暂缓。
