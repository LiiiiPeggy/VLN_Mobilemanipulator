# HY1 初始足迹通行先验（startup_prior）冻结对照

日期：2026-11-07  
开关：`exploration/startup_prior_mode` = `none` | `initial_footprint`（**默认 none**）  
冻结 run：`real_s070_hy1_base_rep_v2_r1_20261106_191426`  
原生回放：`rosrun path_searching test_startup_prior_astar`  
产物：`reports/hy1_startup_prior_20261107/`

## 实现摘要

- F0：底盘位姿+朝向 × `footprint_at_scale` 半长/半宽；栅格只含**中心在足迹内**的格；每 episode 生成一次，不随运动更新；reset/`clearStartupPrior` 清除。
- 规划查询（`Astar2D::checkPointSafety` 及 silent 同判定）：越界/OCC/inflate 仍拒；FREE 不变；**UNKNOWN∈F0** 仅 `initial_footprint` 放行；UNKNOWN∉F0 仍拒。
- **不改写** `occupancy_buffer_`。
- `initial_footprint` 下 **关闭** 0.25 m near-start skip；`none` 保持旧行为。
- Launch/脚本：`STARTUP_PRIOR_MODE`（默认 none）+ half_l/w 由 `ROBOT_SCALE` 足迹计算。

## A/B 结果（同一冻结地图 / 位姿 / 26 候选）

| | A `none` | B `initial_footprint` |
|--|----------|------------------------|
| 可达候选 | **0 / 26** | **5 / 26** |
| 最终路径 | 无 | len≈0.626 m → (1.060, −24.060) |
| 路径上 F0 内 UNKNOWN 采样 | — | 22 |
| 路径上 F0 外 UNKNOWN（安全边） | — | **0** |
| 原始占据是否未变 | true | true |

B 路径节点（末点为 frontier 目标，由既有 `success_dist=0.25` 贴上，未走 `checkPointSafety`；统计已排除该点）：

`[(1.433,-23.717), (1.308,-23.934), (1.058,-23.934), (1.060,-24.060)]`

## 针对性检查（生产 `diagCheckPointSafety`）

| 检查 | B |
|------|---|
| F0 内 UNKNOWN 可放行 | PASS |
| F0 外 UNKNOWN 不放行 | PASS |
| F0 内 OCC 仍拒绝 | PASS |
| F0 内 inflate 仍拒绝 | PASS |
| 位姿变化后 F0 不跟随 | PASS |
| `clearStartupPrior` 后无残留 | PASS |

## 结束条件

- 产生路径且安全边未放行 F0 外 UNKNOWN → **启动先验接口有效**。
- 底盘执行与完整足迹安全 **另行验证**；本报告不宣称运动安全验收通过。
- 默认部署仍为 `startup_prior_mode=none`；未自动执行底盘动作。

## 复现

```bash
python3 adapters/habitat_rangercr10/scripts/prep_hy1_startup_prior_freeze.py
# in vln-rangercr10 after catkin_make --pkg plan_env path_searching exploration_manager
rosrun path_searching test_startup_prior_astar \
  _cells_csv:=.../hy1_startup_prior_20261107/cells.csv \
  _candidates_csv:=.../candidates.csv \
  _out_json:=.../ab_compare.json \
  _chassis_x:=1.4327 _chassis_y:=-23.7172 \
  _yaw:=-2.3315909698614945 _half_l:=0.4557 _half_w:=0.30429
```
