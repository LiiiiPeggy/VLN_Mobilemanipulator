# PROGRESS.md — 当前状态

更新时间：2026-11-06（分支 `cursor/habitat-rangercr10-scale070`：FOV/环视/不可通行诊断）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：深度 NaN + Value 叠加 + Demo cell-fill 保留。本轮完成 **D455 FOV / 环视重叠 / 同 spawn yaw 步对照 / 不可通行分解**（诊断，非正式评测）。标记 `scaled_robot_proxy_070`。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 0.7× + PPO 抬臂 / NO_PASSABLE / 深度 NaN | **OK** | 见前轮报告 |
| Demo Occ + Value Map | **OK** | `/grid_map/value_map` 叠加 |
| Demo cell-fill 去边框 | **OK** | `map_raster.py`；原始 cloud Jaccard=1 |
| 7fps Demo 1280×720 | **OK** | mapfill run 保留，本轮未重生成 |
| FOV / 环视诊断 | **OK** | H79°/V59.25°；30° 重叠 49° |
| yaw 步 15/30/45 对照 | **OK** | `lookaround_coverage_compare_20261106_071538`（须 TURN_DOWN） |
| 不可通行分解 | **OK** | 起点 free；frontier 16/A* 4；unknown+inflate 主导 |

## 下一步（最多 5）

1. 合并/评审前确认不污染 1.0× 默认路径。  
2. 若需更高覆盖：单独开环视步长实验（优先 15°–30°），勿与其它变量同改。  
3. eF36 进一步拉长探索。  
4. TCP 0.88 若需达标：训练侧扩 teleop 箱（禁 IK）。  
5. 停用后腾 GPU。
