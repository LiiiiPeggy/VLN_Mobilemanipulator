# HY1：物理空旷但占据图包围底盘、无法通行——根因定位

日期：2026-11-06  
诊断脚本：`adapters/habitat_rangercr10/scripts/hy1_surround_nontraversable_diag.py`  
证据目录：`reports/hy1_surround_nontraversable_20261106/`

## 0. 冻结证据（禁止用旧 7fps 视频推断）

| 项 | 值 |
|----|-----|
| 工作区 HEAD | `99ebb496023470b27b254fede0a867dce3681f0f`（`cursor/habitat-rangercr10-scale070`） |
| 冻结运行 | `real_s070_hy1_base_rep_v2_r1_20261106_191426` |
| spawn | `FORCE_SPAWN` ← `real_wide_hy1_openband_20261105_113724/start_pose.json` |
| 尺度 / 抬臂 | 0.7× + PPO teleop raise；`CHASSIS_LOOK_MODE` 默认 none |
| odom | `odom_xy_mode=chassis`，`odom_xy_source=chassis_base_link`（**非** legacy 相机 XY 代理） |
| 首规划 | 原生 `plan_seq=1` → **`NO_PASSABLE_FRONTIER`** |
| 环视地图 | `.../maps/frame_0000.png` … `frame_0026.png` |
| 规划局部图 | `native_diag/plan_seq_1_local_map.json` + 本报告分层图 |
| 旧 7fps demo | `real_s070_pporaise_hy1_20261105_171252` **仅观赏**；本结论不依赖它 |

工作区另有未提交记忆/探针/`map_ros` 诊断辅助；**本冻结 run 的默认环视 / 地面门控 / 膨胀 / A\* 行为未改**。

## 1. 交付结论（六问）

| 问题 | 答案 |
|------|------|
| 包围底盘的主要是？ | **UNKNOWN**（0–0.3 m 全 UNKNOWN；非近场 OCC/膨胀） |
| 相机偏置是否正确进入链路？ | **是**。`sensor_pose` 相对底盘 XY≈0.57–0.65 m；规划 odom=底盘；射线起点=`camera_pos_`；legacy 代理未开 |
| 空旷区未成 FREE 的最早原因？ | **近底盘外环缺观测**（默认抬臂+30° 环视覆盖不到车外近环）。车下 0–0.3 m 在足迹内，**不是**必须看到的空地。另：cand05/C 若把走廊地面送进 FOV，门控最早损失在 **voxel Z 混合** |
| 是否有真正假障碍（包围环）？ | **否**。最近 raw OCC≈0.87 m；候选拒绝 **occupied=0, inflate=0, unknown=3943** |
| 针对已证实原因的改动？ | **观测覆盖重做**（车外环带）。可选独立：voxel Z-mix 最小复现。禁止强制 FREE / 扩豁免 / GT 注入 |
| 是否仍靠不安全起点豁免？ | 本帧豁免**救不了**：最近 FREE=0.52 m > 0.25 m 豁免半径；`path_relied_near_start_exemption=0` |

## 2. 地图中的「不可通行」分层

分层图：`plan_seq1_layered_local_map.png`（FREE 白 / UNKNOWN 灰 / OCC 黑；品红=inflate；蓝=足迹；红*=相机；绿虚线=0.25 m A\* 豁免）。

### 2.1 以足迹区分

0.7× `half_l=0.4557 m`, `half_w=0.3043 m`。

| 带 (m) | 区域 | UNKNOWN | FREE | OCC | inflate |
|--------|------|---------|------|-----|---------|
| 0–0.3 | **全部在车下** | 111 | 0 | 0 | 0 |
| 0.3–0.6 | 车外 | 187 | 34 | 0 | 0 |
| 0.6–1.0 | 车外 | 60 | 748 | 3 | 40 |
| 车外目标 0.3–1.0 | exterior | 247 | 782 | 3 | 40（其中 inflate-only 37） |

- **UNKNOWN moat 半径 ≈ 0.5 m**（车外连续无 FREE 的径向厚度）。  
- 最近 FREE **0.522 m**；最近 OCC **0.873 m**；0–0.3 内 **occ=0, inf=0**。  
- 车下 UNKNOWN **不算**「物理空旷却被判障」——相机几何上就看不到车底。

### 2.2 原生规划拒绝（非 Python 近似）

`native_plan_diag.jsonl` plan_seq=1：

- `start_raw_occ=0`（底盘 **UNKNOWN**），`start_inflate=0`
- `free_within_0p3=0`，`unk_within_0p3=111`，`occ/inf_within_0p3=0`
- 26 次候选全部 `NO_PATH`；拒绝合计 **unknown=3943, occupied=0, inflate=0**
- 近起点豁免 counterfactual：`near_start_skip_would_fail ≈ accepted`，且无成功路径

**注意**：`map_pipeline_diag.start_raw_occ` 量的是 **相机格**（常为 FREE），**不是**底盘起点。二者不可混读（`map_ros.cpp` 对 `camera_pos` 取 occupancy）。

### 2.3 代表格

| 角色 | XY | 状态 | 为何不可通行 |
|------|-----|------|----------------|
| 底盘起点 | (1.433, −23.717) | UNKNOWN | 无 free-ray/端点；optimistic=false；距 FREE 0.52 m>0.25 m 豁免 |
| 最近车外 UNKNOWN | (1.183, −23.517) d=0.32 m | UNKNOWN | 从未观测，不是 OCC/膨胀 |
| 最近 raw OCC | (0.583, −23.517) d=0.87 m | OCC+inflate | 远处真实几何；**不是**包围环 |
| 最近 inflate-only | (0.733, −23.567) d=0.72 m | FREE+inflate | 远处 OCC 的 0.18 m 晕 |

## 3. 相机偏置链路

| 检查项 | 证据 | 结果 |
|--------|------|------|
| 深度反投影内参 | HFOV=79° → fx=fy≈388.2；`camera_frame_published=optical` | 一致 |
| `T_world_camera` | 发布 `sensor_pose`=optical FK；环视中 cam−base XY mean≈0.61 m（0.57–0.65，随臂构型变） | 偏置在位 |
| 底盘不动、相机绕行 | base XY std=0；base drift=0；cam 轨迹成偏心弧 | 符合臂载相机 |
| 规划起点 | odom≡chassis；`d(odom,chassis)=0` | 未用相机 XY 冒充底盘 |
| 射线起点 | `inputDepthCloud2D` / `inputFreeRayCloud2D(..., camera_pos_)` | **未**替换为底盘中心 |
| 深度无效策略 | invalid→NaN skip；非 max-range | 无径向假终点政策 |
| legacy 代理 | 全程 `chassis` | **未启用** |
| 同戳发布 | 同 `rospy.Time` 发 odom/sensor/depth/rgb | 消息级同步；非独立时钟审计 |

**多视角静态一致性**（同世界种子，帧0→帧1 ≈30°）：

- seed uvd≈(200,152,1.62 m)
- 重投影深度误差：mean≈0.9 mm，max≈1.8 mm
- 大角度帧 behind/out_of_fov（预期，非漂移）

→ **无**「随朝向重影/弧形假障」量级的外参或同步错误信号。不支持「相机偏置算错导致包围底盘」假说。

## 4. 与 cand05 / C 门控的关系（不重复无据加 LOOK_DOWN）

| 姿态 | 走廊 raw 地面 (AGL≤0.03) | 最早损失 | 端点 |
|------|--------------------------|----------|------|
| C LOOK_DOWN | 62 | **voxel 62→0** | 0 |
| cand05 | 27 | **voxel 27→3** | 2 |

- 默认 PPO 抬臂环视：近底盘外环 **观察覆盖不足** → UNKNOWN moat（本报告主因）。  
- 即使几何上把走廊地面送进相机（cand05/C），生产门控仍会在 **voxel Z 混合** 丢掉地面端点——这是**独立、可选**的地图侧问题，**不是**当前首规划包围环的直接原因（包围环根本没观测）。  
- 禁止用「再加 LOOK_DOWN 帧」掩盖；C 相对 B 已证无效（`hy1_look_abc_20261106`）。

## 5. 根因分流（本轮只诊断，不并行改多机制）

| 假说 | 判定 |
|------|------|
| 投影/同步错误 | **不支持**（偏置链路 + 0→1 重投影 mm 级） |
| 自身点云残留成假 OCC 包围 | **不支持**（0–0.6 m OCC=0；自遮挡→NaN） |
| 有效地面被过滤导致包围 | 默认构型下目标环**无点可滤**；cand05/C 另见 voxel |
| 膨胀/足迹错误导致包围 | **不支持**（0–0.3 inflate=0；拒绝非 inflate） |
| 真实观测盲区 → UNKNOWN | **成立（主因）** |
| 车外已 FREE 但起点 UNKNOWN | 尚未：最近 FREE 仍在 0.52 m 外；若将来走廊 FREE 贴到足迹仍起点 UNKNOWN → **另立** start-state 任务 |

## 6. 下一步（按证据单独立项）

1. **优先**：车外环带（足迹外 0.3–1.0 m）观测方案重做——以分层图/corridor FREE 宽度为验收，不把车下 0–0.3 m 当必须 FREE。  
2. **可选独立**：voxel Z-mix 最小复现修复（保留低矮障碍 Case C）。  
3. 仅当车外通路 FREE 且起点仍 UNKNOWN → start-state / planner-interface（不改地图、不扩豁免）。  
4. **不做**：强制底盘 FREE、UNKNOWN 全放行、GT 注入、并行 15°/PPO 训练、为过测试缩小膨胀。

## 7. 产物

- `summary.json` — 全量数值  
- `plan_seq1_layered_local_map.png` — 分层局部图  
- `camera_traj_xy.npy` — 环视相机轨迹  
- 交叉：`hy1_chassis_observability_20261106`、`hy1_cand05_static_multiframe_20261106`、`hy1_baseline_repeats_20261106`
