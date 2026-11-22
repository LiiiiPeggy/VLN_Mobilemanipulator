# Runtime config confirmation — inf020_soft010 vs legacy018

更新：2026-11-19（在线配对前实测）

## Native planner binaries

- Tree：`/workspace/ApexNav` → `baselines/ApexNav`（bind mount）
- 分支：`cursor/nav-inflation-halfwidth-softcost` @ `6ec6b20`
- 重建：`plan_env` + `path_searching`（含 `test_inflation_softcost_astar`）
- 二进制字符串已含：
  - `[Astar2D] soft_cost enabled: R=%.3f m  w=%.3f (d from inflate-only ESDF)`
  - `lock_obstacles_inflation=true: keep obstacles_inflation_=...`
  - `[SDFMap2D] effective obstacles_inflation_=... resolution=... → inf_step≈%d`

## Profiles（launch / overlay）

| profile | obstacles_inflation | lock | soft R | soft w | Habitat radius |
|---------|---------------------|------|--------|--------|----------------|
| `legacy018` | 0.18 m | false | 0 | 0 | 0.18 |
| `inf020_soft010` | 0.20 m | **true** | **0.10 m** | **2.0** | 0.18（仿真碰撞不变）|

## Inflation grid math（resolution = 0.05 m）

`inf_step = ceil(r / resolution)`，再按连续圆盘过滤 `hypot(i,j)*res ≤ r`：

| r (m) | inf_step | 圆盘格数 |
|-------|----------|----------|
| 0.18  | **4**    | 37       |
| 0.20  | **4**    | **49**   |

**结论**：硬膨胀格步数相同（均为 4），但 0.20 m 多填充对角/边缘格（37→49），再叠加 soft band，两组并非“同图”。在线 `exploration.log` 应打印 `inf_step≈4`；差异靠圆盘半径与 soft_cost 体现。

## Online protocol（本批）

- robot_scale `0.7`，`CAMERA_MODE=fixed_base_gimbal`，executor v1.2
- F0 `startup_prior_mode=initial_footprint`，`expand_m=0.3`
- 预算 `MAX_STEPS=150` / `MAX_EXPLORE_ACTIONS=100`
- 目标检测：沿用本分支 / 容器稳定 VLM（yolov7/dino/blip2/sam，ports 12181–12184）
- ROS_PORT 默认 `11313`（避开稳定 VLM 的 11312）
