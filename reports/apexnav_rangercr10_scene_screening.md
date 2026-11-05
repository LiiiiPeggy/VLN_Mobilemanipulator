# Ranger+CR10 场景筛选与 ApexNav 多步探索

更新：2026-11-05  
范围：`adapters/habitat_rangercr10/`（不改 baseline 默认配置 / 不改 ApexNav 规划算法）  
证据：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/scene_clearance/`、`apexnav_real/real_wide_*`

---

## 1. 已下载场景清单

| 资源 | 路径 | 数量 / 备注 |
|------|------|-------------|
| HM3D val 场景目录 | `.../scene_datasets/hm3d/val` | **100**（含 `.basis.glb` + `.navmesh` + semantic） |
| HM3D v0.2 镜像 | `.../scene_datasets/hm3d_v0.2/val` | 100（同结构） |
| ObjectNav-HM3D v2 val content | `.../objectnav/hm3d/v2/val/content/*.json.gz` | **36** 与场景对齐 |
| ObjectNav v1 | `.../objectnav/hm3d/v1/...` | 有 |
| MP3D 场景 | `.../scene_datasets/mp3d` | **11** 场景目录（部分仅 glb；本轮未跑 ApexNav） |
| 本轮分析集合 | 有 glb+navmesh+ObjectNav-v2 的交集 | **36** |

未重新下载数据。容器 `vln-rangercr10` 可直接加载上述 HM3D glb。

---

## 2. 机器人足迹（复核）

来源：MuJoCo `ranger_cr10.xml` `base_link_col` + URDF 转向轴原点（Stage 4.10d）。

| 量 | 值 |
|----|-----|
| 底盘半长 / 半宽 | **0.651 / 0.4347 m** |
| 底盘 L×W | **1.302 × 0.869 m** |
| 外接圆半径 | **≈0.783 m** |
| 轮距半宽 / 轴距半长 | 0.28 / 0.445 m |
| 轮胎网格半径 | 0.1531 m（滚动可视化）；地板贴合仍用历史 0.125 m |
| LOOK 默认臂水平外伸代理 | ≈1.05 m（未单独进入 ApexNav 膨胀） |

Habitat 原版 agent radius **0.18 m** 仅作历史对照；本轮**未**再扫各向同性膨胀。

---

## 3. 通行性筛选方法（GT 离线，不进规划器）

对每个 ObjectNav-v2 场景 **重算** navmesh：

- `r=0.18`（Habitat）
- `r=0.435`（半宽）
- `r=0.485`（半宽+5 cm）
- `r=0.783`（外接）

主指标：`retain_r485 = area(0.485)/area(0.18)`、绝对 `area@0.485`、定向拟合抽样、可用 ObjectNav 起点数。

完整表：`scene_clearance/ranking.md`；顶视对比：`scene_clearance/panels/*_r018_vs_r485.png`。

### Top-5 候选（几何）

| rank | scene | score | area@0.18 | area@0.485 | retain485 | oriented | starts@0.485 |
|------|-------|-------|-----------|------------|-----------|----------|--------------|
| 1 | **HY1NcmCgn3n** | 0.729 | 154.0 | 76.6 | 0.50 | 0.70 | 25 |
| 2 | **yr17PDCnDDW** | 0.724 | 235.2 | 120.1 | 0.51 | 0.81 | 20 |
| 3 | eF36g7L6Z9M | 0.704 | 209.8 | 89.3 | 0.43 | 0.75 | 25 |
| 4 | LT9Jq6dN3Ea | 0.698 | 225.3 | 97.5 | 0.43 | 0.73 | 24 |
| 5 | k1cupFYWXJ6 | 0.651 | 210.5 | 103.0 | 0.49 | 0.67 | 13 |

对照：先前「开阔」`Dd4bFSTQ8gi` 排 **#11**（area@0.485≈24.8）；「狭窄」`TEEsavR23oF` 排 **#15**（≈20.2）。

---

## 4. ApexNav 在线验证（真实 planner，`:11312`）

配置：Stage 4.10d + yaw 修 + `INFLATION_PROFILE=legacy018` + 26 步环视 + `kinematic_state_set`。

| Run | 场景 / ep | spawn | Explore | FWD 距离 | free | 终止 |
|-----|-----------|-------|---------|----------|------|------|
| `real_wide_yr17_chair0_*` | yr17 / chair0 | 原起点 | STOP×1 | 0 | 1354 | NO_PASSABLE |
| `real_wide_hy1_chair3_*` | HY1 / chair3 | 原起点 | STOP×1 | 0 | 570 | NO_PASSABLE |
| `real_wide_hy1_open_spawn_*` | HY1 | 最大 clearance（偏远） | STOP×1 | 0 | 388 | **NO_COVERABLE** |
| `real_wide_lt9_chair0_*` | LT9 | 偏远 open | STOP×1 | 0 | 0 | NO_COVERABLE |
| **`real_wide_yr17_openband_*`** | **yr17 / chair0** | **offset 0.5 m，clr≈0.55** | **L3/R2/F6/S1** | **1.50 m** | **931** | planner_stop（探索后） |
| `real_wide_hy1_openband_*` | HY1 / chair3 | offset 0.5 m，clr≈0.53 | STOP×1 | 0 | 524 | NO_PASSABLE/COVERABLE（场景相关） |
| `real_ctrl_dd4b_chair5_*` | Dd4b 对照 | adapted 0.5 m | R9/F5 | ~1.25 m | 184 | step_budget |

### Spawn 策略（适配层）

`spawn_utils.find_adapted_start(..., prefer_open_clearance=True)`：

- 在 ObjectNav 起点 **≤1.5 m** 内选接触合格位姿；
- 偏好 navmesh clearance **≈0.55 m**（避免贴墙，也避免空旷到无 frontier）；
- 标记 `adapted_episode`；**不**把 GT 传给 ApexNav。

根因摘要：大场景原起点常「接触 OK」但环视后 A* 无可达 Frontier；过度外移则无 coverable Frontier；**中等开放带 spawn** 后 yr17 出现多步 TURN/FWD。

---

## 5. 四轮运动学可视化

`kinematic_demo._update_wheels_from_base_delta`：按 LocoManip 4WS（`vx,wz`→steer/speed）+ URDF 左右轴符号 `(−1,+1,+1,−1)`，`steering_sign=−1`。

烟雾：`wheel_kinematics_smoke/summary.json` → **pass=true**（前进滚动、转向打角、仅动臂时轮胎冻结）。  
声明：仅运动学可视化，≠轮地动力学。

---

## 6. 复现命令

```bash
# 场景通行性（GT 离线）
GPU=0 bash adapters/habitat_rangercr10/scripts/run_scene_clearance_diag.sh

# 优选场景 ObjectNav（示例 yr17）
INFLATION_PROFILE=legacy018 SCENE_FILTER=yr17PDCnDDW CATEGORY_FILTER=chair EPISODE_ID=0 \
  MAX_STEPS=50 GPU=0 bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh

# 轮胎烟雾
bash adapters/habitat_rangercr10/scripts/run_wheel_kinematics_smoke.sh

# 7 FPS Demo（指定 RUN_DIR）
RUN_DIR=.../real_wide_yr17_openband_* bash adapters/habitat_rangercr10/scripts/run_demo_7fps.sh
```

---

## 7. 结论

1. 已盘点 HM3D×ObjectNav-v2 可用场景，并给出 Ranger 足迹下的 Top-5。  
2. **几何上更宽的场景 ≠ 自动多步探索成功**；环视后的 Frontier/A* 仍依赖出生点附近观测结构。  
3. 在 **yr17PDCnDDW** 上，用开放带 spawn + 既有 yaw 修，得到 **真实 ApexNav 多步探索（FWD×6，1.5 m）**，未缩小机器人、未关碰撞、未把 GT 喂给规划器。  
4. 轮胎滚动/转向可视化已接入 `set_base_pose`，可供 7 FPS 重渲使用。
