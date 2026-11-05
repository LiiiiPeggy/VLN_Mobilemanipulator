# PROGRESS.md — 当前状态

更新时间：2026-11-05（分支 `cursor/habitat-rangercr10-scale070`：0.7× + MuJoCo teleop-PPO 抬臂交接）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：0.7× 代理保留（`897d58b`）；已接通 **MuJoCo stage410d teleop-PPO 抬臂 → Habitat 关节同步 → ApexNav**。D455≈0.88 m 水平；TCP≈0.81 m（teleop Z+0.40 饱和，未用 IK）。抬臂后 yr17/eF36/HY1 均进入探索但立即 `NO_PASSABLE`/STOP。全部标记 `scaled_robot_proxy_070`。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂 / ApexNav 适配

| 项 | 状态 | 证据 |
|----|------|------|
| 1.0× Top-5 / yaw / Stage4.10d | 保留于 `main` | `2214550` |
| 0.7× URDF + env 缩放 | **OK** | `897d58b`；`scale070_verify` |
| MuJoCo PPO 抬臂（非 IK） | **OK** | `ppo_mujoco_raise.py`；`ppo_raise_stage410d_z040.json` |
| Habitat FK：TCP / D455 AGL | TCP≈0.811（未达 0.88）；D455≈0.881 水平 | `ppo_raise_habitat_fk_070.json` |
| PPO→ApexNav 交接 | **OK** | `--ppo_raise_json`；三场景 `real_s070_pporaise_*` |
| yr17/eF36/HY1 抬臂后探索 | 进 explore，FWD=0，`planner_stop` | `ppo_raise_s070_batch_*.jsonl` |
| 7 FPS Demo（含抬臂姿态） | yr17/eF36/HY1 1280×720 7/1 | `real_s070_pporaise_*/demo/*_7fps.mp4` |

## 下一步（最多 5）

1. 合并/评审本分支前确认不污染 1.0× 默认路径。  
2. 评估抬高视场导致 NO_PASSABLE 的建图/Frontier 效应（对照无抬臂 0.7×）。  
3. 评估 legacy018 与 0.7× 半宽 0.304 的膨胀匹配（勿冒充安全）。  
4. TCP 0.88 若需达标：扩展训练 teleop 箱或新策略（禁止本仓 IK 凑数）。  
5. 停用后腾 GPU。
