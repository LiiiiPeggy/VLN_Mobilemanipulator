# Habitat Ranger+CR10：环视占据放射状伪影修复

更新：2026-11-05  
分支：`cursor/habitat-rangercr10-scale070`  
场景：yr17（`robot_scale=0.7`，PPO 抬臂交接，真实 ApexNav planner）  
证据根：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/depth_radial_fix/`

---

## 1. 问题与假设

环视时右下角 `/grid_map` 出现大量从机器人原点外射的线条（示例 occ≈883 / free≈549），主画面空旷、D455 仍能看到地面与家具。

**待验证假设**：上一轮把近距自遮挡深度改写为最大量程（≈5 m），使虚假终点参与 ApexNav 占据更新与射线投射。

结论：**假设机制成立，且已修复**；但 Demo 面板上的“稀疏射线外观”不完全等于 5 m 伪终点——有效深度在 `skip_pixel`+体素+离群点滤波后，本身也会呈扇形散点。

---

## 2. 数据链核对（Habitat → `/grid_map`）

| 环节 | 结论 |
|------|------|
| Habitat Depth | 度量米；常见含 `0`、`>5`；yr17 step0 中 `<0.65 m` 可达 ~35% |
| Python 适配 | 旧：近距→`depth_max`；新：`prepare_depth_for_apexnav` → **NaN** |
| 归一化 | `depth_meters_to_normalized` **保留 NaN**，不 clip 成 0 |
| ROS Image | `32FC1`；无效像素为 NaN |
| `map_ros.cpp` | `convertTo` 前建 `depth_valid_mask_`；`processDepthImage` **跳过**无效像素（无终点、无自由射线） |
| `k_depth_scaling_factor` | 与归一化 `[0,1]→[mindist,maxdist]` 一致；Habitat 侧 mindist 覆盖为 0 |
| 相机位姿 | URDF FK `d455_depth_optical_frame`；odom XY=相机投影；Z=AGL |

---

## 3. 修复内容

### 3.1 无效深度：跳过，绝不写成 5 m / 0

- 新增 `adapters/habitat_rangercr10/src/depth_validity.py`
- `ros_dynamic_publisher` / episode dump：`invalid_depth_policy=nan_skip_not_max_range`
- ApexNav 局部补丁：`baselines/ApexNav/.../map_ros.{h,cpp}`（仅 NaN mask+skip；未改 Frontier/A*/成功条件）
- 需加载已重建的 `libplan_env.so`

### 3.2 自遮挡：几何优先

- 连杆球 + 骨骼胶囊 + link AABB（按 `robot_scale` 缩放）
- 反投影到 Habitat 相机系（look **-Z**）后做机体内点判定 → NaN
- 几何失败时才用极近 `fallback_near_m=0.35`（不是 0.65 一刀切）
- **禁止**为凑 free 删除真实障碍的膨胀/成功条件改动

### 3.3 合成测试

`adapters/habitat_rangercr10/scripts/test_depth_validity_synthetic.py`：全有效 / 含 NaN 区 / 近距块 → 无效变 NaN，有效保留。

---

## 4. yr17 对照实验（保留旧 Demo，不覆盖）

| 标签 | run_id | occ/free | explore | 备注 |
|------|--------|----------|---------|------|
| before（近距→max） | `real_s070_pporaise_yr17_fix_20261105_183316` | 1026 / 675 | FWD 0.25 + STOP | 无 depth_validity dump |
| after capsule | `..._depthfix3_20261105_191203` | 1098 / 494 | FWD 0.25 + STOP | self≈23%@step0 |
| **after capsule+AABB（采用）** | `..._depthfix4_20261105_201112` | **727 / 932** | **FWD 0.50**，满 50 步 budget | self≈56%@step0；近距 masked≈94% |

相对相机原点：占据点 `r_med≈1.7–2.0 m`，**无** `r∈[4.8,5.2]` 团簇 → 排除“全图改写到 5 m 终点”为主残差。

环视 step 1/9/18/26 地图与 depth raw/prep 对照见 `depth_radial_fix/`：

- `map_{before,after3,after4}_step{00,08,17,25}.png`
- `local_map_*.png`
- `depth_*_step*_raw.png` / `*_prep.png`（红=NaN）
- `demo_after4/`、`comparison_summary.json`

---

## 5. 验收对照

| 标准 | 结果 |
|------|------|
| 无效深度不产生虚假占据终点 | **通过**（NaN + C++ skip） |
| 无效深度不产生虚假自由射线 | **通过** |
| 真实家具/墙仍能建图 | **通过**（occ 保留；EE 可见植物/桌） |
| 26 步环视不再持续堆 5 m 放射伪终点 | **通过**（无 max-range 团）；Demo 仍呈稀疏扇形散点（PointCloud2 可视化特性） |
| 地图与末端 FK 一致 | **通过**（odom=cam XY + AGL Z） |
| 至少一场景进入真实 ApexNav 规划 | **通过**（depthfix4：MOVE_FORWARD×2，budget 耗尽） |

---

## 6. 复现命令

```bash
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
OUT=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real
RAISE=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json
FORCE=$OUT/real_wide_yr17_openband_20261105_012302/start_pose.json
RUN_ID=real_s070_pporaise_yr17_depthfix_$(date +%Y%m%d_%H%M%S)

# 若改过 map_ros.cpp：在 vln-rangercr10 内重建 plan_env 并确认 exploration_node 链到新 .so
INFLATION_PROFILE=legacy018 SCENE_FILTER=yr17PDCnDDW CATEGORY_FILTER=chair EPISODE_ID=0 \
  MAX_STEPS=50 GPU=0 RUN_ID="$RUN_ID" ROBOT_SCALE=0.7 \
  FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="$RAISE" \
  bash $ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh

python3 $ROOT/adapters/habitat_rangercr10/scripts/test_depth_validity_synthetic.py
```

---

## 7. 修改文件与原因

| 文件 | 原因 |
|------|------|
| `adapters/habitat_rangercr10/src/depth_validity.py` | 无效→NaN；几何自遮挡 |
| `adapters/.../ros_dynamic_publisher.py` | 发布前 prep；统计 |
| `adapters/.../coord_habitat_ros.py` | 归一化保 NaN |
| `adapters/.../apexnav_real_episode.py` | dump raw/prep/stats；挂 env 给几何掩码 |
| `adapters/.../scripts/test_depth_validity_synthetic.py` | 合成回归 |
| `baselines/ApexNav/.../map_ros.{h,cpp}` | 转换前有效掩码并跳过 |

未改：Frontier / A* / 探索策略 / 成功条件 / 膨胀 / robot_scale / PPO 权重。
