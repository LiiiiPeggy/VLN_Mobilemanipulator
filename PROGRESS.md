# PROGRESS.md — 当前状态

更新时间：2026-11-06（30° 几何回归+原生归因完成；VLFM 全量 RUNNING；MSGNav luna QUEUED）
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：Ranger 几何修复保留。本轮：**VLFM 全量 2000ep 评测进行中**；MSGNav 20ep 改用 **gpt-5.6-luna**，排队等 VLFM 全量结束后启动。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM | `BATCH_OK` → **全量 RUNNING** | `VLFM_full/full_val_20261106_120908`；目标对照论文 SR52.5/SPL30.4 |
| ApexNav / MSGNav | `BATCH_OK` | MSGNav 20ep luna **QUEUED** after VLFM |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 评测复现（2026-11-06）

| 项 | 状态 | 证据 |
|----|------|------|
| VLFM full 2000ep（无录像） | **RUNNING** | `runs/VLFM/full_val_status.md`；ETA ~17h |
| MSGNav 20ep gpt-5.6-luna | **QUEUED** | `runs/MSGNav/luna_20ep_status.md`；`scripts/run_msgnav_20ep_luna.sh` |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 0.7× + PPO / 深度 NaN / Demo Value+cell-fill | **OK** | 见前轮；本轮未覆盖旧 Demo |
| optical→ROS / map_ros 位姿 | **已修** | `hab_optical_rot_to_ros`；发 optical 非 render |
| 内参 fx=fy≈388.19，VFOV≈63.45° | **已修** | `camera_model`；launch fy |
| `/odom` 真实底盘 XY | **已修** | 默认 `chassis`；legacy 可开关 |
| 离线坐标/内参验证 | **OK** | `reports/camera_coord_fix_20261106` all_pass |
| 运行时几何验收（投影/odom/自遮挡） | **OK** | `geometry_accept_20261106_post_a5e291b` |
| 正式 30° 短程回归（yr17/eF36/HY1） | **已跑** | `reports/habitat_rangercr10_geomreg_30deg_native_plan.md` |
| 原生 C++ NO_PASSABLE 归因 | **部分** | yr17 无；eF36/HY1=起点 UNKNOWN+unknown 阻断 |
| 15° 正式环视 | **未开** | 2/3 仍 NO_PASSABLE，优先 free/底盘覆盖 |

## 下一步（最多 5）

1. 盯 VLFM 全量：`progress.txt` / 结束后对照论文 SR52.5 / SPL30.4。  
2. VLFM 结束后确认 MSGNav luna 20ep 自动开跑；看 SR/SPL + API token。  
3. **单变量**：eF36/HY1 底盘起点 free 缺口（覆盖/掩码/地面高度带）；勿绑 15°。  
4. yr17 仅作日后 15° 候选场景，另立项。  
5. 合并前确认不污染 1.0× 默认路径。
