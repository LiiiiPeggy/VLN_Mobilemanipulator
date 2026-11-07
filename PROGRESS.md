# PROGRESS.md — 当前状态

更新时间：2026-11-07（ObjectHold 最小修复 + 24-ep 对照）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：启动已解封；**ObjectHold** 修复「接近中丢目标云立刻改探索」→ yr17 成功；同清单 SR_proxy **4/24**（基线 3/24）。冻结实验配置：`initial_footprint`+`expand_m=0.3`+`denoise=none`。

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| 多数 ep **从未进入 SEARCH** → 仍 `explore_no_goal`（Hold 后 16/24） | `object_approach_hold_20261107` | 再叠接近 hold / 再扩 F0 / 去噪 |
| 曾选中但未完成仍有 4/24（多为 `stop_not_near`） | 同上 | 与「从未选中」混为一谈 |
| SPL / 净位移 **N/A** | 无 geodesic | 用欧氏冒充 SPL |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| 启动先验 + expand0.3 | **冻结 OK** | start_blocked=0 |
| 障碍去噪 median3 | **可选；默认关** | A 3/24 vs B 4/24 |
| ObjectHold（接近丢云保持） | **OK（yr17 + 24-ep）** | yr17 成功；整批 4/24；`87a233e`；`reports/object_approach_hold_20261107.md` |
| ObjectNav e2e expand0.3 | **BATCH** | 基线 none 3/24 → Hold 4/24 |
| 默认 launch | prior none / expand 0 / denoise none | 实验入口 expand 0.3 |

## 下一步（最多 5）

1. **从未进入 SEARCH 的 explore_no_goal**（检测/置信/前沿策略）— 与接近 hold 分轨。  
2. `stop_not_near` 近失（曾选中）单独拆停止/接近点距离。  
3. UniGoal 更长步数；SG-Nav 小批量（旁路）。  
4. 合并前确认不污染 1.0× 默认路径。  
5. （可选）Hold 计数/阈值仅作诊断，不扩成锁定框架。
