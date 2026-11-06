# 地面 free-ray 几何判据（低矮障碍）

日期：2026-11-06  
前置：`6df8ceb`（同帧 local_update 合并）  
本提交：独立收紧地面候选；不改膨胀半径 / unknown / A* / 环视姿态。

## 问题

将 AGL ∈ [0, `filter_min_height=0.28`] 整段当地面 free-ray，会把 **5/10/20 cm** 低矮障碍顶面也当成 FREE 终点并沿射线雕刻可通行，且不写 OCCUPIED。

## 判据

| 条件 | 处理 |
|------|------|
| AGL ∈ [0, `ground_free_max_agl=0.03`] 且局部平面 | free-ray 候选 |
| 同上但平面邻域不足 | **拒绝**（保持 UNKNOWN，不 free） |
| AGL ∈ (0.03, 0.28] | **低矮障碍 → OCCUPIED** |
| AGL ∈ (0.28, 1.18) | 原障碍带（不变） |

平面：XY 半径 0.12 m 内 ≥5 个邻点且 `|Δz|≤0.02`。

## 验证

`adapters/habitat_rangercr10/scripts/test_ground_free_geometry.py`  
→ `reports/ground_free_geometry_20261106/test_ground_free_geometry.json`

- 1 cm 平面地板 → `GROUND_FREE`
- 5/10/20 cm 盒顶 → `LOW_OBSTACLE`，终点 **OCCUPIED**；naive 整段策略会标 **FREE**（对照）
- 孤立 1 cm 尖点 → `PLANAR_REJECT` → UNKNOWN
- 未改膨胀、未放宽 unknown
