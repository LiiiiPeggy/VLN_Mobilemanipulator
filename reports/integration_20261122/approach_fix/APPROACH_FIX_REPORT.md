# 接近/停止最小修复交付（2026-11-22）

## 因果链（首个阻断）

hy1 joint4 g3：过深目标云进入 `SEARCH_OBJECT`，`next_pos`≈5.0–5.5 m；置信度一 miss 即  
`[ObjectHold] drop hold (miss would be 1, dist=5.00m)`（阈值 `OBJECT_HOLD_MAX_DIST=3.0`）→ 立刻退回 EXPLORE。  
之后虽靠 v2 挪到 VIEW_POINTS 0.485 m，但已无 SEARCH，无法 `REACH_OBJECT`→STOP；预算耗尽。

step106 D455/夹爪挡 `forced_forward` 发生在进入 1.0 m **之前**，是次级烧预算因素，本轮未改碰撞/恢复。

## 最小修复（唯一变量）

- 模块：`exploration_fsm` ObjectHold 距离门 + ROS/`OBJECT_HOLD_MAX_DIST`
- OFF/默认：**3.0**（与 joint4 行为一致）
- ON：**8.0**（覆盖 over-depth ≈5 m 接近点）
- 不改膨胀、碰撞体、恢复策略、感知、STOP 规则、PPO/臂姿

## 冻结与有效性

| 项 | 值 |
|----|-----|
| 工作区 | `VLN_Mobilemanipulator_integrate` / `…-scale070-integrate` |
| 容器/devel | `vln-rangercr10-integrate` / `.catkin_devel_integrate`（已重编 exploration_node） |
| 预算 | max_steps=150 / max_explore=100（与 joint4） |
| 配对固定 | scale0.7、fixed_base_gimbal、ARM_DEFAULT、nf_look=OFF、无 PPO |
| hy1/Dd4b 配置 | `legacy018` + `v2` |
| 批次 | `approach_fix_20261122_215609` |

姿态核对：ARM_DEFAULT==ARM_APEXNAV_INIT==LocoManip `[0.236,…,0]`；simulated_gimbal 只改俯仰；D455/夹爪为实体碰撞体。  
`success_claimed` **恒 False**（设计如此）；成功代理用 `planner_stop ∧ near_goal(VIEW_POINTS≤1.0)`。

离线细节：`OFFLINE_AUDIT.md`。

## 配对表

见 `results_approach_fix_20261122_215609/PAIR_TABLE.md`。

| 任务 | 修复 | dtg↓ | moved↑ | near | sr_proxy | OH keep/drop | 备注 |
|------|------|------|--------|------|----------|--------------|------|
| hy1 | OFF(复用 j4g3) | 0.485 | 5.71 | T | F | 0/1 | SEARCH≈6 |
| hy1 | ON | **0.167** | **9.21** | T | F | **26/2** | SEARCH≈35；仍无 REACH |
| Dd4b | OFF | 3.011 | 2.13 | F | F | 0/0 | |
| Dd4b | ON | 3.011 | 2.13 | F | F | 0/0 | 无收益、无退化 |
| tee chair4 | OFF | 0.021 | 1.96 | T | F | — | **invalid_initial_penetration** → 缺口 |
| tee | ON | — | — | — | — | — | 跳过（OFF 非可比成功） |

## 判断

| 问题 | 结论 |
|------|------|
| 状态/停止链？ | ObjectHold **维持 SEARCH 更久**；仍 **无 STOP/REACH** |
| 合法移动？ | hy1 moved 5.7→9.2；blocked 56→39 |
| 真正寻物成功？ | **否**（无 planner_stop / sr_proxy） |
| 回归？ | Dd4b 无退化；历史成功任务 **缺口**（现栈 spawn 非法） |

## 默认与下一步

- **默认暂不改**（仍 `OBJECT_HOLD_MAX_DIST=3.0`）；候选 **8.0** 进入下一批固定清单。
- 下一项：SEARCH 近距仍难 `REACH`（next_pos 0.20 / soft 0.45）与转角 D455/夹爪执行挡。
- 帧：`frames_before/`（joint4）与 `frames_after_hy1/`（ON）。

## 直接回答

1. **hy1 到附近未成功**：进入 1.0 m 时已是 EXPLORE；无 `SEARCH_OBJECT`→无 REACH→无 STOP；终端=预算。根因最早是 ObjectHold 在 5 m 丢弃接近。  
2. **D455/夹爪**：中段（如 step106）拒绝转向/FF，烧预算；非最终 1.0 m 内唯一死因。  
3. **改了什么**：ObjectHold `max_dist` 可配，配对 ON=8.0。  
4. **是否恢复移动/停止/成功**：hy1 移动与接近明显改善；**停止与任务成功未恢复**。  
5. **Dd4b / 成功任务**：Dd4b 持平；成功回归 **缺口**。  
6. **能否进主动感知**：接近链路有改善，但 **STOP/成功仍未闭环** → **尚不适合**把主动感知当主线；先补 REACH/执行近距。

## 远端

仍见 `../REMOTE_OPS_PENDING.md`；本轮新增 approach_fix 报告与 ObjectHold 接线，**不自行 push/删分支**。
