# phase0：`hy1_plant_0` OFF→ON（batch `phase0_hy1_20261121_235918`）

- 主机锁：`/home/ubuntu/locomani/_sim_host_run.lock`（已释放 `LOCK_FREE`）
- FSM：`enable_no_frontier_look` OFF=`false` / ON=`true`（exploration.log 已确认）
- Spawn：冻结 `x=23.717… yaw=0.810…`，与原审计一致；`spawn_status=ok`
- 触发前轨迹：至 step 83 前动作序列一致；仅在首次 `expl_result=4` 处分叉（OFF→STOP，ON→TURN_LEFT）

## 四问

| 问 | 答 |
|----|----|
| OFF 是否重现原错误 STOP？ | **是**。`NO_PASSABLE(4)→FINAL NO_FRONTIER(3)→FINISH→STOP`；moved=2.458、dtg=2.313、n_steps=84，与原 `dev24_after_dinofix` 审计例数值一致。 |
| ON 是否触发补视、几步？ | **是，15 步**（`[NoFrontierLook] 1/24…15/24`）。 |
| 补视是否产生新 frontier 并恢复有效移动？ | **有新 frontier**（step 98 起 `expl_result` 回到 0=探索类）；**底盘未恢复有效平移**（无 `MOVE_FORWARD`；总 moved 仍 2.458）。 |
| 最终是否寻物成功？ | **否**。`explore_budget_exhausted`（explore 100/100）；dtg 仍 2.313；非延迟 STOP。 |

## 备注

- 先前错误批（spawn 路径未进容器）已作废；以本 batch 为准。
- 开关本身有效；本例 ON 把错误 STOP 推成预算耗尽，且未形成可计的寻物成功。
