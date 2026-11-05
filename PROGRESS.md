# PROGRESS.md — 当前状态

更新时间：2026-11-05（分支 `cursor/habitat-rangercr10-scale070`：整机 0.7× 代理）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：在独立分支实现 Habitat 适配层 **整机 0.7×**（`scaled_robot_proxy_070`）；几何/相机验证通过；yr17 足迹 safe_ratio 0→1；探索距离与 HY1 早停未因缩尺全面改善。`main` 上 1.0× 成果保留。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 1.0× Top-5 / yaw / Stage4.10d | 保留于 `main` | `2214550` |
| 0.7× URDF + env 缩放 | **OK** | `assets/urdf/..._s070.urdf`；`scale070_verify` pass |
| 相机 AGL≈0.60 m（目标 0.616） | **OK** | verify / camera_init |
| ApexNav 同 ep 对照 | 完成 | `scale070_compare_batch_*.jsonl` |
| yr17 足迹 0.7× | **safe_ratio=1.0** | `footprint_path_safety/yr17_openband_s070` |
| yr17/eF36 7 FPS（0.7×） | 已生成 | `real_s070_* /demo/*_7fps.mp4` |
| HY1 @0.7× | 仍 NO_PASSABLE | 非尺寸单因 |

## 下一步（最多 5）

1. 合并/评审本分支前确认不污染 1.0× 默认路径。  
2. 评估 legacy018 与 0.7× 半宽 0.304 的膨胀匹配（记录差异，勿冒充安全）。  
3. HY1 建图/Frontier 专项（不靠继续缩尺）。  
4. PPO→Habitat（不阻塞）。  
5. 停用后腾 GPU。
