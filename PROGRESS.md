# PROGRESS.md — 当前状态

更新时间：2026-11-06（地面 free-ray 正确性收口；HY1 仍覆盖不足；可另立补视）
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：地面 free-ray 正确性已分提交验证；下一步仅 **朝底盘侧补视**（单变量）。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / MSGNav | 见各自 status | 本轮未改评测队列 |
| ApexNav 适配 | 进行中 | 几何门控 + merge |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 同帧 local_update 合并 | **OK** | `6df8ceb`；`reports/local_update_merge_20261106` |
| 地面几何门控（≤3 cm 平面；5/10/20 cm→OCC） | **OK** | `ef70acd`；`reports/ground_free_geometry_20261106` |
| HY1 失败帧诊断 | **OK** | `813827c`；经典 NO_PASSABLE=覆盖不足；豁免 observe-only |
| 三场景 short3（门控后） | **已跑** | yr17/eF36 20×探索；**HY1 首规划 NO_PASSABLE** |
| 朝底盘侧补视 | **未开** | 门槛已满足，另立提交 |
| 15° / 足迹专项 | **未开** | — |

## 下一步（最多 5）

1. **单变量**：朝底盘侧补视（连通可见地面证据；不要求看穿车体）。  
2. 可选：yr17/eF36 oriented 足迹回放。  
3. 盯 VLFM/MSGNav status。  
4. yr17 日后 15° 另立。  
5. 合并前确认不污染 1.0× 默认路径。
