# PROGRESS.md — 当前状态

更新时间：2026-11-26（**正式默认**：`REVERSE_PLANNING_MODE=C` + `INFLATION_PROFILE=inf020_soft010`；EXEC/LOOK 仍 PPO）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：默认导航 = teleop-PPO 低层 + ApexNav 高层 + **方案 C 倒车 Hybrid A\*** + **0.20 m 硬膨胀 / soft 0.10·w=2.0**。  
**唯一工作区**：`/home/ubuntu/locomani/VLN_Mobilemanipulator`（分支 `cursor/habitat-rangercr10-scale070`）。  
**容器**：`vln-rangercr10-integrate`。

## 已完成（本轮）

- 默认切换：`run_integrate_defaults.env` / `run_apexnav_real_episode.sh` / `exploration_rangercr10.launch` / argparse / `AGENTS.md` → **C + inf020_soft010**。
- 运行时验收（`hy1_defC_inf020_ms200_20261126_160827`）：
  - ROS：`obstacles_inflation=0.2`，`lock_obstacles_inflation=true`，`astar/soft_cost_range_m=0.1`，`soft_cost_weight=2.0`
  - C++：`[Astar2D] soft_cost enabled: R=0.100 m  w=2.000`；`libpath_searching.so` 含 `edgeTraversalCost`
  - 方案 C：`reverse_planning_mode=C`；PPO 段含 `move_backward`；`n_hybrid_calls=91`，`MOVE_BACKWARD×11`
- HY1 Demo（同 spawn，max_steps=200 / explore=170，2fps）：
  - run：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/hy1_defC_inf020_ms200_20261126_160827_hy1_plant_0`
  - demo：`.../demo/apexnav_ranger_paper_demo.mp4`（2fps，196 frames）
  - `termination=explore_budget_exhausted`，`sum_moved_m≈14.03`，`n_blocked_exec=117`（对照先前 C+legacy018 ms200：moved≈15.36 / blocked=109）
- 历史 `legacy018` / mode A|B 仍可显式复现；未做膨胀扫参。

## 默认保持

ObjectHold=3.0，**inf020_soft010**（inflate=0.20，lock=true，soft R=0.10/w=2.0），recovery=legacy，soft_reach=false，LOOK=ppo_ee_rpy，**exec=ppo_chassis**，PPO raise z040，**REVERSE_PLANNING_MODE=C**。

## 下一步（最多 5）

1. 目视验收本轮 Demo：A* 离墙与贴墙转向碰撞。  
2. 可选另一场景冒烟（非膨胀扫参）。  
3. 大批量暂缓。  
4. 用户点名再调 soft/R 或 Hybrid 细节。  
5. Demo 默认仍 2fps；7fps 仅点名。
