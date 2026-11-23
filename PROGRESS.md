# PROGRESS.md — 当前状态

更新时间：2026-11-23（默认 LOOK=ppo_ee_rpy + **EXEC_BACKEND=ppo_chassis** + PPO raise z040；**保持 PPO，不回退 kinematic-only**）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10（0.7× + 固定夹爪）。

**当前阶段**：默认评测抬臂/LOOK/底盘低层均走 teleop-PPO（`model_9999`）；ApexNav 仍做高层规划。  
**唯一工作区**：`/home/ubuntu/locomani/VLN_Mobilemanipulator`（分支 `cursor/habitat-rangercr10-scale070`）。  
**容器**：`vln-rangercr10-integrate`。

## 已完成（本轮）

- `LOOK_BACKEND=ppo_ee_rpy` + `PPO_LOOK_DIR` + `PPO_RAISE_JSON` z040。
- **`EXEC_BACKEND=ppo_chassis`**：宿主 `run_ppo_chassis_bundle_host.sh` → `ppo_chassis_bundle_model9999/{move_forward,turn_left,turn_right}.json`；episode 回放 ΔSE2 + Habitat `probe_base_motion`。
- Bundle 实测：forward path≈0.27 m；turn |yaw|≈0.59–0.60 rad；`lock_output=True`。
- 回退仅对照：`EXEC_BACKEND=kinematic`；`LOOK_BACKEND=gimbal`（**默认勿切回**）。
- Demo 观影：用户确认 **7fps** 可见轮胎滚动；2fps（一帧一动作）过粗，轮转不明显。
- Demo 地图 inset：已执行轨迹（橙）+ 原生 A* `selected_path`（紫）；在线 `map_listener.render_panel(plan_xy=...)`，离线 `scripts/overlay_astar_path_on_demo.py`。

## 默认保持

ObjectHold=3.0，legacy018，recovery=legacy，soft_reach=false，LOOK=ppo_ee_rpy，**exec=ppo_chassis**，PPO raise z040。

## hy1 冒烟（ppo_chassis）

- Run：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/ppo_chassis_hy1_20261123_220210_hy1_plant_0`
- `exec_backend=ppo_chassis`，segments 三份已加载；`steps.jsonl` 含 `ppo_delta`
- `n_steps=46`，`termination=explore_budget_exhausted`，`sum_moved_m≈0.85`，blocked 较多（场景门控仍生效）
- Demo（观影优先 7fps）：
  - 2fps：`.../demo/apexnav_ranger_paper_demo.mp4`（一帧一动作，轮转难辨）
  - **7fps**：`.../demo/apexnav_ranger_paper_demo_7fps.mp4`（**用户确认可见轮胎/轮运动**）
- 轮胎为运动学可视化（底盘 ΔSE2 / segment `wheel_q_final` + 位姿插值），≠轮地动力学
- 脚本：`reports/integration_20261122/ppo_chassis/run_hy1_smoke.sh`

## 下一步（最多 5）

1. 需要时用 `EXEC_BACKEND=kinematic` 对照同一 spawn（默认仍保持 ppo_chassis）。  
2. 用户重训更收拢 home 后换 ckpt → 重出 raise/look/chassis bundles。  
3. soft_reach 正向 OFF/ON（默认仍 false）。  
4. 大批量暂缓。  
5. 可选：在线 MuJoCo twin（当前仅 unit-segment 预计算）。
