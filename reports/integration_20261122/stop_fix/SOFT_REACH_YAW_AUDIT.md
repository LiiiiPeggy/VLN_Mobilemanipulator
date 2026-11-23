# soft_reach 卡住核验与 yaw-aware 修正（2026-11-23）

基线 tip：`55e8c8d`；已发布候选：`ef71d31`（XY `pose_stuck` + any last_action）。

## 二、已发布 ON 的 STOP 真义（hy1）

运行：`stop_fix_20261123_002141_hy1_soft_reach_on`

| 问题 | 答案 |
|------|------|
| 上一动作 | **成功完成的 TURN_RIGHT**（非拒绝） |
| req vs act | 一致；无 recovery 替换 |
| 底盘 | Δxy=0；Δyaw=**−30°**；俯仰无变化 |
| 接近点 | next_pos≈(6.22,−26.03)，距 **0.25 m**；SEARCH 刷新后的接近点（非最终 Hold drop） |
| 触发代码 | `soft_reach_on_any_stuck` + **XY pose_stuck** + dist&lt;0.45（忽略成功转向） |

**结论：已发布候选会把正常原地转向误判为卡住。** LOOK 同理仅因 XY 不变也会误判（本跑 STOP 前未以 LOOK 触发）。

证据图：`evidence_hy1_published_any_stuck/`（step94 trunc → step95 成功转向 → step96 误 STOP）。

## 三、最小修复

| 项 | 内容 |
|----|------|
| 落点 | `ExplorationFSM::callActionPlanner`（`exploration_fsm.cpp`） |
| 反馈 | 已有 odom：`Δxy`（平移）、`Δyaw`（转向）；LOOK 无俯仰反馈 → **不**因 XY 闲置触发 |
| 行为 | 开关仍 `soft_reach_on_any_stuck`（默认 false）。ON 时：MOVE→XY stuck；TURN_L/R→`|Δyaw|<ACTION_ANGLE/2`；TURN_UP/DOWN→永不因本候选触发 |
| 未改 | soft/hard 距离、Hold、碰撞试探、膨胀、检测、评测、无 PPO |

边界脚本（阈值镜像）：`test_soft_reach_stuck_boundary.py`（10/10 pass）。

## 四、配对结果

固定：legacy018 + v2 + ObjectHold=8.0 + nf_look=OFF + 150/100。

| 任务 | 版本 | 结束 | STOP源 | SR_proxy | 目标确认 | dtg_eval | next_pos | moved | blocked |
|------|------|------|--------|----------|----------|----------|----------|-------|---------|
| hy1 | OFF（复用 approach hold8） | MOVE_FORWARD | — | 否 | 后期 drop→EXPLORE | 0.167 | min≈0.25 | 9.21 | 39 |
| hy1 | 已发布 any_stuck | STOP | soft_reach after **成功** TURN | 是* | SEARCH/云刷新 | 0.525 | 0.25 | 6.86 | 30 |
| hy1 | **yaw-aware ON** | STOP | soft_reach yaw_stuck dyaw=−0.087 after **TRUNC TURN** | **是** | SEARCH next=0.25 | 0.483 | 0.25 | 6.96 | 30 |
| Dd4b | yaw-aware | （重试中/见下） | — | — | — | — | — | — | — |

\*已发布 SR_proxy 成立但 STOP 条件不合法（成功转向误判）。

正向 OFF/ON：**缺口**——当前栈尚无同配置 OFF 已成功、可配对的合法 spawn 任务（tee_chair4 仍 invalid_initial_penetration；ziup 仅有失败 ON）。不把失败 ON 写成回归通过。

## 五、截图

- 误判案例：`evidence_hy1_published_any_stuck/`
- 正确 STOP：`evidence_hy1_yaw_aware/`（step95 TRUNC turn → step96 STOP）

## 默认

ObjectHold=3.0，legacy018，recovery=legacy，`soft_reach_on_any_stuck=false`。

Dd4b 回归：`stop_fix_dd4b2_20261123_181703`（scene=`Dd4bFSTQ8gi`）；与先前 soft_reach ON 同型（未近距、无 STOP）。错场景重试不计。
