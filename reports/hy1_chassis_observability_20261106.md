# HY1 近底盘地面可观测性与 free 更新缺口定位

**日期**：2026-11-06  
**基线**：`99ebb49`（A/B/C 负结果保留；默认部署 / 30° 环视 / 地面阈值 / 膨胀 / unknown / A* 未改）  
**方法**：固定构型帧探针（非批量导航）  
**证据目录**：`reports/hy1_chassis_observability_20261106/`

## 结论（唯一）

最早缺口阶段：**目标地面未被看到（观察覆盖）**。

B（budget_match / 抬高）与 C（joint3−0.60 LOOK_DOWN）在 HY1 固定 spawn 下，**车体周围 0–0.6 m 地面均未进入相机图像 FOV，也无有效深度点落在该环带**。因此下游「有效观测被过滤 / 射线未覆盖目标格 / 地图更新未生效」在本构型上**尚未被触发**（对 0–0.3 m UNKNOWN 格而言）。

**唯一优先下一步**：另立启动策略任务——设计并几何验证能覆盖车体周围目标地面的姿态/传感器策略；**不要**改地面过滤阈值、不要强制 FREE、不要注入 GT/navmesh、不要扩大起点豁免。

## 一、B/C 实际视角（非 LOOK_DOWN 标签）

| 项 | B `budget_match` | C `chassis_ground` (j3−0.60) |
|----|------------------|------------------------------|
| arm_q[2] | −1.819 | −2.419（Δ=−0.60） |
| camera ROS AGL xyz | (0.934, −24.138, **0.881**) | (0.977, −24.059, **0.561**) |
| optical 前向 (R col2) | (−0.704, −0.710, **+0.028**) 近水平前视 | (−0.631, −0.577, **−0.518**) 明显下俯 |
| \|cam−chassis\|_xy | 0.652 m | 0.569 m |
| 环带投影 0–0.3 / 0.3–0.6 `n_in_fov` | **0 / 0** | **0 / 0** |
| 环带 `n_in_front` | 0 / 0 | 12 / 93（光轴前，但投影落在图像外，v 中位 ≫ 480） |
| 点云落入 0–0.6 m | **0** | **0**（最近点 ≈ 0.85 m） |
| 自遮挡 | 臂体红区明显；不解释环带缺口（环带本就不在 FOV） | 同左 |

叠图：`B_*_chassis_ground_proj.png`、`C_*_chassis_ground_proj.png`；同步 RGB / raw depth / self-hit mask / `*_meta.json`。

C 帧实际看到的是前方织物/地面（最近点 ~0.85 m），**不是**底盘足迹地面。不能用 `CHASSIS_LOOK_MODE` / `applied=true` 代替覆盖证据。

## 二、逐阶段追踪（0–0.3 / 0.3–0.6 m）

生产门控镜像：`filter_min=0.28`，`ground_free_max_agl=0.03`，planar(r=0.12,z_tol=0.02,min_n=5)，voxel(0.04,0.04,0.1)，outlier ground(0.25,8)/obst(0.3,35)。

| 阶段 | B 0–0.3 | B 0.3–0.6 | C 0–0.3 | C 0.3–0.6 |
|------|---------|-----------|---------|-----------|
| 原始有效深度 → 世界点 | 0 | 0 | 0 | 0 |
| 降采样 / AGL / 平面 / 离群后地面端点 | 0 | 0 | 0 | 0 |
| 全图地面端点（全局） | ground_planar_ok=15 → outlier 后 **1** | | planar_ok=53 → outlier 后 **27** | |
| 射线 XY 穿过环带（任意端点） | 0 | 0 | 0 | ※见下 |
| 代表 UNKNOWN 格 miss 射线 | **0/全部** | — | **0/全部** | — |

※ C 的相机本身落在距底盘 ~0.57 m（0.3–0.6 环内），「任意端点射线穿过 0.3–0.6」会把**相机起点**算进去，**不能**解释为已覆盖底盘内侧；0–0.3 的射线穿过计数为 **0**（可靠）。

高度分布（相对 floor=0，暂不调阈值）：

- B：mean AGL≈1.13；`frac_0–0.03≈0.7%`；全局地面候选远离底盘（groundband dxy min≈2.18 m）。
- C：mean≈0.10；`frac_neg≈51%`（织物/近场）；groundband dxy min≈1.00 m，仍在 0.6 m 外。
- 负高度与降采样混合存在，但**不是**本缺口的最早原因（目标环带根本无点）。

代表性格子（0–0.3 m，res=0.05）：`skip_reasons=no_free_ray_segment_through_cell`；无 occupied 端点邻近；**未进入** miss 更新机会。生产 log-odds 前后差未仿真（无射线到达则更新路径不触发）。

## 三、原生测试覆盖

可执行：`rosrun plan_env test_map_pipeline_replay`（日志：`native_test_map_pipeline_replay.log`）→ **ALL_PASS**。

| Case | 验证范围（准确命名） | 结果 |
|------|----------------------|------|
| A | **XY-only** `SDFMap2D` 同帧 obstacle+free-ray **local_update 合并/膨胀**（**绕过** MapROS 高度分类） | PASS |
| B | **XY-only**：5/10/20 cm **仅作不同 Y 格标签**，非度量高度；MapROS classify **未行使** | PASS |
| C | **3D-keep-Z 生产路径**：真实 AGL z=5/10/20 cm 障碍 + 平面地面 → voxel/classify/outlier/`diagProcessCloud3DKeepZ` → 最终 OCCUPIED；输入输出保留高度 | PASS（low_obst=75, ground_after=49） |

→ 地图更新与低矮障碍分类在注入有效 3D 云时**工作正常**；本 HY1 缺口不在此层。

## 四、缺口归类与后续

| 假说 | 本轮证据 |
|------|----------|
| 目标地面未被看到 | **成立（最早）**：B/C 环带 FOV=0，点云 0–0.6 m=0 |
| 有效观测被过滤 | 未触发（环带无观测可过滤） |
| 射线没有覆盖目标格 | 对 0–0.3 m 成立，但是**无端点/无朝向底盘的观测**的后果，非独立根因 |
| 地图更新未生效 | 不支持；原生 Case C 证明 3D 路径可 OCC |

**禁止项遵守**：未强制底盘 FREE；未注 GT/navmesh；未扩起点豁免；未改默认部署参数。

**探针**：`adapters/habitat_rangercr10/scripts/hy1_chassis_ground_observability_probe.py`  
**原生诊断 API**：`MapROS::diagProcessCloud3DKeepZ`（observe-only）
