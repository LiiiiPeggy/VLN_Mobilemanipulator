# hy1 ON（hold=8.0）最终阻断（不套用 OFF 结论）

运行：`approach_fix_20261122_215609_hy1_hold8_on`  
固定：legacy018 + v2 + ObjectHold=8.0 + nf_look=OFF + 无 PPO

## OH keep=26 结构（多周期累计）

| 周期 | keep | next_pos 距 | 释放 |
|------|------|-------------|------|
| A | miss 1–12 | 5.00→2.26 m（从 over-depth 接近点逼近） | miss 帽满，drop@2.01 m |
| B | miss 1–2 | 0.97→0.72 m（重新拿到 object_cloud） | 中间再获 SEARCH 刷新 |
| C | miss 1–12 | **恒 0.25 m** | miss 帽满，drop@0.25 m |

不是同一候选无限刷新单一存续期。

## 进入评价距离后时间线（要点）

| step | FSM | 在线 next_pos 距 | VIEW_POINTS | 动作 |
|------|-----|------------------|-------------|------|
| 82 | SEARCH | ~仍在逼近 | 0.949 | MOVE_FORWARD OK |
| 90–94 | SEARCH | ↓ | 0.83→0.48 | 前进/转向 |
| 95–106 | SEARCH | **≈0.25 m** | 0.483 | TURN_RIGHT 连拒；FF 亦拒 |
| 107+ | EXPLORE | 丢掉接近点 | 0.48→0.14 | 无 STOP；预算耗尽 |

- 全程 **无** `Reach the object` / STOP。
- Hard REACH 阈值 0.20 m；本跑 **从未** next_pos_dist&lt;0.20（最小 0.25）。
- Soft REACH 0.45 m：本应覆盖 0.25 m，但代码要求 `last_action==MOVE_FORWARD`；卡在 planner 的 TURN_RIGHT 时 `newest_action_` 仍是转向（Habitat 侧 recovery FF 不回写 FSM）。

## 必答

1. **最终退回探索**：周期 C drop 后 → EXPLORE（不是一直 SEARCH 到结束）。  
2. **后期无 5 m over-depth**：前期 over-depth next≈5.5 m；重新检测后 next≈0.97→0.25 m。  
3. **在线距随接近缩短**：是（5→2→0.25）；VIEW_POINTS 同步降到 ~0.17。  
4. **到达条件卡在状态转换/软到达门**：目标确认曾成立且在线点合理；执行上转向被挡；**最早确定的 STOP 阻断**是 soft REACH 不认“转向卡住”。

## 最小修复

`soft_reach_on_any_stuck`（默认 false）：SEARCH + pose stuck + dist&lt;soft_reach 时，允许任意 last_action 触发 REACH→STOP。  
配对唯一变量；ObjectHold 保持 8.0。
