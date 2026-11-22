# 接近/停止/执行离线核对（joint4 g3 hy1）

证据根：`.../joint4_20261122_164956_g3_hy1_legacy_on` · 冻结 `a77f7d9` · `legacy018`+`v2` · nf_look=OFF · 无 PPO

## 1. 实际姿态

| 项 | 实测 |
|----|------|
| camera_mode | `fixed_base_gimbal`（simulated_gimbal=true） |
| 臂关节 | `ARM_APEXNAV_INIT == ARM_DEFAULT = [0.236, 0.086, -2.398, -0.830, -1.335, 0]` |
| 与 LocoManip/PPO ARM_DEFAULT | **一致**（`ranger_policy.py` 同值） |
| 光心 | 底盘系固定 `[0.639,-0.075,0.291]`；LOOK 只改俯仰，臂冻 |
| D455/夹爪 | URDF 实体碰撞体参与 `kinematic_collision_v1.2` 探针；非虚拟相机豁免 |
| PPO | 未调用；`ppo_raise_json=""` |

结论：固定云台链路使用作者预期收拢构型；与 PPO 默认关节一致，但本批不经 PPO。

## 2. 成功口径

| 字段 | 含义 |
|------|------|
| `success_claimed` | **恒为 False**（代码写死：无官方 evaluator 不宣称）→ **不能**用「无 True」证明无成功 |
| `near_goal` | eval-only：`VIEW_POINTS` 距 ≤ `success_distance`(默认 1.0 m)；**不**触发 STOP |
| `dtg_point` | 目标中心距，仅诊断 |
| 在线 STOP | FSM `REACH_OBJECT`：`SEARCH_OBJECT` 且距 `next_pos_` < **0.20 m**（软：前进卡住且 <0.45 m） |
| SR_proxy（历史批脚本） | `termination==planner_stop` 且 STOP 时 VIEW_POINTS≤1.0 |

joint4 预算：`max_steps=150` / `max_explore=100`（init lookaround 26 另计）。

历史可比：`apexnav_real` 下有 scale070+gimbal 的 `planner_stop∧near_goal` 例（formalgimbal_formal150…），但 SHA/恢复开关与当前 integrate **不完全同条件** → 正向回归需现跑 OFF 确认，否则记缺口。

## 3. hy1 接近时间线（要点）

| step | dtg_vp | final_state | 事件 |
|------|--------|-------------|------|
| 70–75 | ~2.16→1.89 | **SEARCH_OBJECT(1)** | Over-depth 目标云；`next_pos` 距 **5.25–5.51 m**；日志 “going to object dist=0.5m”≠next_pos |
| ~76 | — | → EXPLORE | **`[ObjectHold] drop hold (miss would be 1, dist=5.00m)`**（阈值 3.0） |
| 91–109 | 1.56 | EXPLORE | TURN_RIGHT 连拒；v2 opposite/FF；**step106 FF 被 d455+夹爪挡**（仍在 1.0 m **之外**） |
| 119 | **0.994** | EXPLORE | 首次进入 success_distance；ndet=0 |
| 125 | **0.485** | EXPLORE | 预算耗尽；从未 REACH/STOP |

### A/B/C/D

- **A**：进入 1.0 m 时 **未**处于 `SEARCH_OBJECT`，无在线确认可用于 STOP 的目标。
- **B**：处于 EXPLORE 追 frontier；到达条件不满足 → 无 STOP。
- **C**：step106 碰撞在进入 1.0 m **之前**；进入后仍有合法前进。
- **D**：终端原因=**预算耗尽**；根因链=**候选/ObjectHold 过早放弃**（最早阻断）→ 后段执行空转烧预算；非 STOP 信号丢失。

## 4. 规划 vs 执行

- 最早 explore 拒绝：step37 `MOVE_FORWARD` truncated。
- 最明确空转：同 `next_pos` 下 TURN_RIGHT 全挡 streak；`stucking_next_pos_count_`→14 后 dormant。
- 失败试探保留在 `exec.motion_probe` / block_reason（step106 FF）。

## 5. 最小修复（本轮唯一）

**因果**：Over-depth 接近点 ~5 m → ObjectHold 在首 miss 因 `max_dist=3.0` 丢弃 → 无法维持 SEARCH 至 REACH。

**修改**：ROS/`OBJECT_HOLD_MAX_DIST` 可配；配对 ON=**8.0**，OFF/默认=**3.0**（不自动改默认）。不叠膨胀/恢复/感知/新 STOP。
