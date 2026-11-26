# PROGRESS.md — 当前状态

更新时间：2026-11-26（默认 **C + inf020_soft030**；评估 dtg=相机→VIEW_POINT 3D；在线 STOP 仍为 ApexNav）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：默认导航 = PPO LOOK/EXEC + ApexNav + **方案 C** + **硬 0.20 / soft R=0.30·w=2.0·lock**。  
**唯一工作区**：`/home/ubuntu/locomani/VLN_Mobilemanipulator`（分支 `cursor/habitat-rangercr10-scale070`）。  
**容器**：`vln-rangercr10-integrate`。

## 已完成（本轮）

- 正式默认：`REVERSE_PLANNING_MODE=C`，`INFLATION_PROFILE=inf020_soft030`；`inf020_soft010`/`legacy018`/`A|B` 仅复现。
- Demo：**`PLAN_DIAG_ENABLE=true`** → 紫 A* + 红目标（`native_plan_diag.jsonl`）。
- 评估：`near_goal`/`SR_proxy` 的 dtg = **相机→最近 VIEW_POINT 三维距**；底盘水平/POINT 诊断；**不改在线 STOP**。
- HY1 soft030：`hy1_defC_inf020_soft030_attach_20261126_205757_hy1_plant_0`  
  - `planner_stop`，steps=73，moved≈5.76，blocked=25；路径离墙观感改善；STOP 时检测弱（`n_detections=0`）。
- 设计共识（未实现）：若要「相机到视点附近再 STOP」，优先 **视点→底盘停靠点偏置** \(p_{vp}-R\cdot t_{cam}\)，而非只改评估。

## 默认保持

ObjectHold=3.0，**inf020_soft030**，recovery=legacy，LOOK=`ppo_ee_rpy`，EXEC=`ppo_chassis`，raise z040，**REVERSE=C**，**PLAN_DIAG=true**，Demo 2fps。

## 下一步（最多 5）

1. （用户点名）实现相机对齐 STOP：视点反解底盘目标 / 或适配层相机距强制 STOP。  
2. 正式入口重跑 HY1（含 plan_diag）验收紫路径+红目标与 soft030。  
3. 评估改 3D 后旧 run 的 SR_proxy 不可混比；新跑才可比。  
4. 大批量暂缓。  
5. 未经要求勿改回 soft010/A/legacy018。
