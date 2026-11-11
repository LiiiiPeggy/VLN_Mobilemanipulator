# PROGRESS.md — 当前状态

更新时间：2026-11-11（ApexNav HM3D-v2 全量复现完成）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：原生 ApexNav HM3D-v2 val **1000-ep 已完成**（SR **74.4%** / SPL **37.65%**，论文 76.2/38.0，Δ −1.8/−0.35 pp）。Ranger 侧仍冻结 F0/Hold/LabelMap；评估 dtg=VIEW_POINTS。

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

## ApexNav 论文复现（HM3D-v2）

| 项 | 状态 | 证据 |
|----|------|------|
| 全量 1000-ep | **完成** | `.../hm3dv2_full_20261109_231528`；~13.1 h |
| SR / SPL | **74.4% / 37.65%**（论文 76.2 / 38.0） | log + `summary.json` |
| 失败主因 | **false positive 144（占失败 56%）** | `live_failures.md` |
| 报告 | 已写 | `reports/apexnav_hm3dv2_full_repro.md` |

## 下一步（最多 5）

1. Ranger：真 stop_not_near（错误物体）与 synonym-only 不进 SEARCH_BEST 分轨。  
2. 勿再改 F0/Hold/映射/评估阈值。  
3. UniGoal / SG-Nav 旁路。  
4. 合并前确认不污染 1.0× 默认路径。  
5. （可选）对照论文失败分布；false positive 是否可在不改协议下诊断。
