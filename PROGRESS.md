# PROGRESS.md — 当前状态

更新时间：2026-11-05（Top-5 短测 + yr17/HY1 诊断 + 足迹安全）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Top-5 场景开放带短测完成；**五景均进入正式探索**；多步规划：yr17（SEARCH_EXTREME）、eF36（EXPLORATION）、Dd4b；yr17 路径足迹回放表明 legacy018 **不安全**。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| Top-5 entered_explore | **5/5** | `top5_openband_compare.json` |
| yr17 多步 | EXTREME FWD 1.5 m | `real_wide_yr17_openband_*` |
| eF36 多步 | EXPLORATION R16/L7/F1 | `real_wide_ef36_openband_*` |
| HY1 / LT9 / k1cup | 早停 | NO_PASSABLE / NO_COVERABLE |
| yr17 足迹安全回放 | **safe_ratio=0** | `footprint_path_safety/yr17_openband/` |
| yr17 7 FPS | 保持 7/1×205 | `.../7fps.mp4` |
| spawn 探针禁轮累积 | 已修 | `spawn_utils update_wheel_joints=False` |

## 下一步（最多 5）

1. 改善 LT9/k1cup 建图空/早停（出生观测与楼层）。  
2. 在不改 baseline 的前提下评估定向足迹约束 vs 可达 Frontier。  
3. eF36 代表性 7 FPS（可选）。  
4. PPO→Habitat（不阻塞）。  
5. 停用后腾 GPU。
