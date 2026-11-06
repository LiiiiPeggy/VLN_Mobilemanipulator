# 相机投影 / 内参 / 底盘里程计一致性修复

更新：2026-11-06  
基线提交：`9fb8ea4`  
分支：`cursor/habitat-rangercr10-scale070`  
验证：`reports/camera_coord_fix_20261106/`（analytic all_pass=True）

本轮**不**改：PPO、0.7×、膨胀、环视 30°、unknown 通行策略、其它 baseline。

---

## 1. 已独立复现的问题

| ID | 问题 | 证据 | 状态 |
|----|------|------|------|
| B1 | `hab_rot_to_ros=C@R@C.T` 用于 optical 局部位姿时错误；应对 `R_ros=C@R_optical` | `validate… optical_rot_map`：正确映射残差 0，旧式误差 ≫0.1 m | **已修复** |
| B2 | 发布 `sensor_pose` 时曾传 Habitat **render**（optical@Rxπ），而 map_ros 按 **optical** 反投影 | 代码路径 `apexnav_real_episode` / coverage compare | **已修复**（改发 optical） |
| B3 | 自遮挡：optical 位姿却用 `z=-depth`（render 约定） | `depth_validity.geometric_self_hit_mask` | **已修复**（optical→`z=+d`） |
| C1 | `fy` 用 `HFOV×H/W` → fy=422、VFOV≈59.25°；方像素应为 fx=fy≈388.19、VFOV≈63.45° | `intrinsics` / `ray_hfov` 测试 | **已修复** |
| D1 | `/habitat/odom` XY 使用相机地面代理，非真实底盘 | `ros_dynamic_publisher` | **已修复**（默认 `chassis`；旧行为 `legacy_camera_xy_proxy`） |
| E1 | Python A* 将起点 `ij==s` 恒视为可走，unknown 起点跳过近邻 snap | `planner_first_call_diag._astar_reachable` | **已修复** |
| GT1 | “false_occupied_rate” 实为 0.35 m 邻域 navmesh 命中率 | 探针改名 + 字段 | **已更正口径** |

未在本轮用完整 C++ 在线 episode **重新测完** NO_PASSABLE 拒绝码分布 → 见 §5（待验证）。

---

## 2. 坐标系约定（落地后）

| 帧 | 定义 |
|----|------|
| Habitat 世界 | Y-up |
| ROS 世界 | `(-hab_z, -hab_x, hab_y - floor_y)`，Z=AGL |
| D455 optical | +X 右 +Y 下 +Z 前（URDF `d455_depth_optical_frame`） |
| Habitat render | optical @ Rx(π)：+X 右 +Y 上 −Z 前 |

世界轴变换与相机局部轴变换**分开**：`hab_rot_to_ros`（世界轴）vs `hab_optical_rot_to_ros` / `mat4_hab_optical_to_ros_pose`（optical→map_ros）。

---

## 3. 内参

| | 旧（错误/launch） | 新（Habitat HFOV 方像素） |
|--|--|--|
| fx | 388.191 | 388.191 |
| fy | **422.048** | **388.191** |
| VFOV | ≈59.25°（HFOV×H/W） | ≈**63.45°** |

`exploration_rangercr10.launch` 已设 `fy_=fx_`。  
**撤回/降级**：此前报告中“从 launch 反算得到独立测得 VFOV=59.25°”的表述；那只是错误 fy 的推论，不是渲染器实测。

---

## 4. 底盘里程计

- 默认：`/habitat/odom` = 真实底盘 XY + 航向，Z=底盘 AGL。  
- `/habitat/sensor_pose` = 真实 optical。  
- 旧相机 XY 代理：`odom_xy_mode=legacy_camera_xy_proxy`（日志标明，不作真实 base_link）。

原地转向 / 只动臂时底盘 XY 应不变；MOVE_FORWARD 与底盘位移一致——**analytic 约定已写入代码**；完整运动回放待下一短跑验证。

---

## 5. 不可通行诊断口径

- `planner_first_call_diag`：**Python 近似**，不得再写成“真实 ApexNav 16 簇 / 4 条 A*”。  
- GT 探针：改称 `occ_navmesh_neighborhood_audit`；`precise_false_occupied_rate=null`。  
- **自由空间高度带缺口**：`filter_min_height=0.28` 可能丢掉近地地面点 → free 射线变少——机制存在，**是否主导 NO_PASSABLE 待 C++ 在线流水线统计证实**；本轮**未**改 free 更新策略。

---

## 6. 对旧结论的处理

| 旧结论 | 处理 |
|--------|------|
| VFOV=59.25° 为实测 D455 | **降级**：错误内参推论 |
| 30° 水平重叠「49%」 | **更正口径**：重叠 **49°**，约占 79° 水平视场的 **62%**（非 49%） |
| yaw15 覆盖 > yaw30（mapping-only） | **保留为旧投影链路下的诊断**；几何修复后需重跑才可外推正式探索 |
| “unknown+inflate 主导不可通行” | **降级为待用真实底盘 odom + 正确投影重测** |

---

## 7. 15° 正式环视

**尚不具备条件**：须先完成几何修复后的正式 30° episode 回归，再单独改 TURN 角与每圈次数/阶段计数。

---

## 8. 主要改动文件

- `src/camera_model.py`（新）
- `src/coord_habitat_ros.py`（optical 专用转换）
- `src/ros_dynamic_publisher.py`（optical pose + chassis odom）
- `src/depth_validity.py` / `pointcloud_dynamic.py`
- `src/apexnav_real_episode.py` / `lookaround_coverage_compare.py`
- `launch/exploration_rangercr10.launch`（fy）
- `scripts/validate_camera_coord_chain.py`
