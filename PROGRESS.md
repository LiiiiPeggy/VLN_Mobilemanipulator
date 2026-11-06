# PROGRESS.md — 当前状态

更新时间：2026-11-06（HY1 重复性+补视 A/B/C 完成；朝向补视未改善）
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：HY1 固定姿态下首规划 NO_PASSABLE 可复现；A/B/C 补视对照显示 **朝向无效**。

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| triad 证据 + 豁免静默计数 + C++ 回放 | **OK** | `4969fe6`；`hy1_triad_evidence_20261106` |
| HY1 基线 5× 复测 | **OK** | `391e96e`；v2：NO_PASSABLE 5/5，深度帧 54–57 |
| A/B/C 补视对照 5× | **OK** | 三组均 NO_PASSABLE 5/5；C 相对 B 无改善 |
| 默认部署补视 | **未开** | `CHASSIS_LOOK_MODE=none` |
| 15° / 足迹专项 | **未开** | — |

## 下一步（最多 5）

1. 另立：底盘侧地面覆盖的其他单变量（非本 LOOK_DOWN burst 方案）。  
2. 可选：yr17/eF36 oriented 足迹回放。  
3. 盯 VLFM/MSGNav status。  
4. 15° 仍缓开。  
5. 合并前确认不污染 1.0× 默认路径。
