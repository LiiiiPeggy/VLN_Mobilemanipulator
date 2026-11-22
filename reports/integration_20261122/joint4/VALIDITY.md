# Joint4 validity notes

Batch: `joint4_20261122_164956`  
Worktree: `/home/ubuntu/locomani/VLN_Mobilemanipulator_integrate`  
Branch: `cursor/habitat-rangercr10-scale070-integrate`  
**Frozen source tip at batch start:** `a77f7d979f0dd0068dc5adf0f221e8acf40d41b2`  
Container: `vln-rangercr10-integrate`  
Devel: `.catkin_devel_integrate`（含 soft_cost / NoFrontierLook / V2 FSM look 交替符号）

## Fixed protocol (all 8)

| knob | value |
|------|-------|
| scale | 0.7 |
| camera | `fixed_base_gimbal`（simulated_gimbal） |
| budget | max_steps=150 / max_explore=100 |
| startup_prior | initial_footprint + expand 0.3 |
| denoise | none |
| `ENABLE_NO_FRONTIER_LOOK` | **false** |
| factors | `INFLATION_PROFILE` × `BLOCKED_RECOVERY_MODE` only |

## PPO / arm pose

- **本批未调用 PPO。** 无 `PPO_RAISE_JSON`；`camera_mode=fixed_base_gimbal` 冻结臂于 `ARM_DEFAULT`。
- 本轮工作区未提交的 `model_9999` 默认权重更新 **不影响** 本批行为（抬臂链路未进入）。
- 权重更新结论单列：发布文件与 `load_actor` 推理接口检查通过；**本轮未运行抬臂验证**。

## V2 switch contents (`BLOCKED_RECOVERY_MODE=v2`)

相对 `legacy`：

1. 连续 ≥3 次同向 turn 全挡 → `opposite_turn`，再挡 → `forced_forward_after_turn_block`（仍走碰撞试探提交）。
2. MOVE_FORWARD 挡死仍可用 gimbal look / forced turn。
3. 仅 `moved_m>1e-3` 清零 escalate stage。
4. FSM NoFrontierLook 左右交替：本批 nf_look=OFF，该 FSM 分支不触发（仍编入二进制）。

## Spawns

- hy1_plant_0: frozen `.../paired_b/frozen_spawns/hy1_plant_0_start_pose.json`
- Dd4b toilet_0: `.../execgimbal_dev24_after_dinofix_20261119_011332_dd4b_toilet_0/start_pose.json`
