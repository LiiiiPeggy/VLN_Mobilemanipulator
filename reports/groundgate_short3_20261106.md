# 地面门控后三场景同条件短跑

日期：2026-11-06  
HEAD：`813827c` + 本报告  
条件：30° 环视、0.7× PPO raise、legacy018 膨胀、同 spawn、`MAX_EXPLORE=20`  
**不**改观察姿态。`blocked=0` **≠** 足迹安全。

证据：`reports/groundgate_short3_20261106/short3_summary.json`  
Runs：`real_s070_groundgate_{yr17,ef36,hy1}_20261106_182146`

## 结果表

| 场景 | 起点 raw（首→末） | free@0.3 | inflate@起点 | NO_PASSABLE | 探索 | 净位移 m（plan chassis） | 窗口 occ 首→末 | 窗口 inflate 首→末 |
|------|-------------------|----------|--------------|-------------|------|--------------------------|----------------|---------------------|
| yr17 | FREE→FREE | 112→111 | 0→0 | 0 | 20（R7/L5/F8） | ≈1.80 | 95→889 | 0→3139 |
| eF36 | UNKNOWN→FREE | 0→98 | 0→0 | 0 | 20（R5/L7/F8） | ≈0.85 | 231→2252 | 0→4386 |
| HY1 | UNKNOWN→UNKNOWN | 0→0 | 0→0 | **1** | 1×STOP | 0 | 903→1412 | 0→3745 |

## 解读

- **yr17**：对照保持；起点 FREE，全程 EXPLORATION。  
- **eF36**：首规划仍 UNKNOWN 且 `relied_near_start_exemption=1`，随后起点转 FREE，20 步探索完成。  
- **HY1**：首规划即 `NO_PASSABLE_FRONTIER`，`free_within_0.3=0`，`nearest_free≈0.52 m`；拒绝以 unknown 为主 → **仍属底盘侧地面覆盖不足**（与经典失败同型）。  
- 原始障碍 / 膨胀：三场景窗口 OCC/inflate 均随观测累积上升；起点 inflate 保持 0。  
- 足迹：未做 oriented 回放；不得用 STOP/blocked 代理宣称安全。

## 补视实验门槛

地图更新合并 ✓、地面几何门控单测 ✓、HY1 本批失败可明确归因覆盖不足 ✓ → **允许另立**「朝底盘侧补视」单变量（不要求看穿车体看正下方）。本提交**不含**补视改动。
