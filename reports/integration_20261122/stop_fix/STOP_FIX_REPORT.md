# stop_fix：soft_reach_on_any_stuck（2026-11-23）

基线 SHA（修复前）：`383691d3becf0372b575dceecefb355d542ecb9c`（`origin/cursor/habitat-rangercr10-scale070`）  
路径：B — 在线目标合理、确认成立，卡在 soft REACH→STOP 状态转换。

## 阻断（仅 ON 日志）

证据：`approach_fix/ON_FINAL_BLOCKER.md` + `approach_fix_20261122_215609_hy1_hold8_on`

| 问题 | 结论 |
|------|------|
| 最终 FSM | 周期 C ObjectHold drop 后→**EXPLORE**（非一直 SEARCH） |
| over-depth | 后期无 ≈5 m；next_pos 5→2→**0.25 m** |
| 在线距随接近缩短 | 是 |
| 最早阻断 | soft REACH 要求 `last_action==MOVE_FORWARD`；卡在被拒 TURN 时 `newest_action_` 仍为转向 |

## 修复（单点，默认 OFF）

- 开关：`SOFT_REACH_ON_ANY_STUCK` / `soft_reach_on_any_stuck`（**默认 false**）
- 行为：SEARCH + pose stuck + dist&lt;0.45 m 时，允许任意 `last_action` 触发 REACH→STOP
- 未改：ARM_DEFAULT、相机、资产、碰撞体、膨胀、检测阈值、评测口径；不接 PPO/主动臂；碰撞检查保留

## 配对配置（唯一变量 = soft_reach）

固定：`legacy018` + `recovery=v2` + `ObjectHold=8.0` + `NoFrontierLook=OFF` + 同 spawn/预算/感知执行

| 任务 | soft_reach | 结束动作 | STOP 源 | 寻物成功* | dtg_eval | 在线 STOP 距 | moved | blocked |
|------|------------|----------|---------|-----------|----------|--------------|-------|---------|
| hy1 | OFF（复用 approach_fix hold8） | MOVE_FORWARD | none | 否 | 0.167 | —（最小 next≈0.25） | 9.21 | 39 |
| hy1 | ON | **STOP** | soft_reach dist=0.25 last_action=TURN any_stuck=1 | **是** | 0.525 | 0.25 | 6.86 | 30 |
| Dd4b | ON | TURN_DOWN | none | 否 | 3.011（best 2.82） | — | 2.13 | 69 |
| ziup_plant3 | ON | TURN_RIGHT | none | 否 | 3.541 | — | 0.93 | 101 |

\*寻物成功 = 正确目标确认 + 合法到达（online soft/hard REACH）+ STOP；`success_claimed` 协议仍恒 False；此处用 `planner_stop ∧ dtg_eval≤1.0` 作 SR_proxy。

## 解读

- **hy1**：修复命中最早阻断；ON 在 next_pos≈0.25 m、TURN stuck 时 STOP；eval dtg 0.525≤1.0。
- **Dd4b**：全程未进入评价近距（best≈2.82 m）；属发现/接近不足，非本 STOP 门问题。
- **ziup_plant3**：合法初始化（`initial_penetration=false`）；高 blocked、未接近目标；正向回归未体现 STOP 收益。
- **tee_chair4**：仍单列 `invalid_initial_penetration`，不计本修复失败。

## 默认策略

| 项 | 值 |
|----|-----|
| ObjectHold | **3.0**（候选 8.0） |
| inflation | **legacy018** |
| recovery | **legacy**（候选 v2） |
| soft_reach_on_any_stuck | **false**（候选 true） |

## 运行路径

- hy1 OFF：`.../approach_fix_20261122_215609/..._hy1_hold8_on`
- hy1 ON：`.../stop_fix_20261123_002141/..._hy1_soft_reach_on`
- Dd4b/ziup ON：`.../stop_fix_ext_20261123_154208/...`
- 入口：`adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh`
