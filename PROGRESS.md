# PROGRESS.md — 当前状态

更新时间：2026-11-09（stop_not_near 评估口径：VIEW_POINTS）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：F0/Hold/LabelMap 冻结。**评估** `dtg` 改为 Habitat 默认 VIEW_POINTS 后，同轨迹 LabelMap 批 SR_proxy **8/24**（原 POINT 记录 5/24；非策略增益）。

## 当前卡点（主）

| 卡点 | 证据 | 不该再做 |
|------|------|----------|
| 真 stop_not_near：错误物体/实例（4）+ EXTREME 无 label=0（1） | `stop_near_viewpoint_20261109` | 用扩成功半径 / 改 F0 掩盖 |
| 有检不 SEARCH_BEST：仅辅助簇 label≠0（8/24）或 label=0 未达 BEST | LabelMap 分类表 | 把非零标签改成 0 |
| SPL **N/A** | 无 geodesic | 欧氏冒充 SPL |

## 机械臂 / ApexNav 适配（摘录）

| 项 | 状态 | 证据 |
|----|------|------|
| F0+expand0.3 / denoise=none / ObjectHold / LabelMap | **冻结** | 既有报告 |
| SR_proxy dtg 参考 | **VIEW_POINTS**（阈值仍 1.0 m） | `apexnav_real_episode.goal_distance` |
| LabelMap 批重算 | SR 5→**8**/24；原 5 成功保留；+sofa0/chair0/bed1 | `stop_near_viewpoint_20261109` |

## 下一步（最多 5）

1. 错误物体/实例追逐（真 stop_not_near）与 synonym-only 不进 SEARCH_BEST 分轨。  
2. 勿再改评估阈值、F0、Hold、映射。  
3. UniGoal / SG-Nav 旁路。  
4. 合并前确认不污染 1.0× 默认路径。  
5. （可选）官方 geodesic VIEW_POINTS 度量若可接再替换欧氏代理。
