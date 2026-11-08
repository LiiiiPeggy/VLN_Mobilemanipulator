# PROGRESS.md — 当前状态

更新时间：2026-11-08（HM3D→Apex 标签映射 + 24-ep 对照）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：启动已解封；ObjectHold 保留；**类别映射**修复后发现率显著上升。冻结：`initial_footprint`+`expand_m=0.3`+`denoise=none`+ObjectHold。同清单 SR_proxy **5/24**（Hold 4/24）。

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| 有检测/近义簇仍不进 SEARCH_BEST，或 SEARCH 后 `stop_not_near`（11 explore_no_goal + 8 stop_not_near） | `discovery_label_map_20261108` | 再改 HM3D 映射；盲目降置信/扩视野/改环视 |
| 曾选中未完成增多（stop_not_near 4→8） | 同上 | 与「从未检到」混谈 |
| SPL / 净位移 **N/A** | 无 geodesic | 用欧氏冒充 SPL |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| 启动先验 + expand0.3 | **冻结 OK** | start_blocked=0 |
| 障碍去噪 median3 | **可选；默认关** | A 3/24 vs B 4/24 |
| ObjectHold | **冻结 OK** | `87a233e`；Hold 4/24 |
| HM3D→Apex 标签映射 | **OK（本轮）** | 候选 10→24；SEARCH_BEST 8→13；SR 4→5；原成功保留 |
| ObjectNav e2e | **BATCH** | `ab24_labelmap_20261108_220204` |

## 下一步（最多 5）

1. **有检不 SEARCH / synonym-only 簇（label≠0）** 与 **SEARCH 后 stop_not_near** 分轨诊断（置信、目标类索引、接近闭合）。  
2. 勿再叠映射/Hold/F0/预算。  
3. UniGoal 更长步数；SG-Nav 小批量（旁路）。  
4. 合并前确认不污染 1.0× 默认路径。  
5. （可选）检测 jsonl 轻量落盘便于离线按阶段计数。
