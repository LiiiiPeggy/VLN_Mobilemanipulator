# 半宽硬膨胀 + 软代价（P0/P1/P2）— 离线结论与推荐

分支：`cursor/nav-inflation-halfwidth-softcost`（自 `492f53f`）  
日期：2026-11-18  
尺度：`robot_scale=0.7` → `footprint_at_scale` 半宽 **0.30429 m**（不写死 0.30）

## 1. 生效规划链（核实）

见 `BASELINE_PLANNING_CHAIN.md`。要点：

| 项 | 值 |
|----|-----|
| 地图分辨率 | 0.05 m |
| P0 硬膨胀 | 0.18 m → `inf_step=4`，圆形 `inflatePoint` |
| P1/P2 硬膨胀 | `half_w(scale)` ≈ 0.30429 → `inf_step=7` |
| Habitat `agent_radius` | 历史会覆盖 inflation；本轮加 `sdf_map/lock_obstacles_inflation` |
| ESDF `getDistance` | 自 inflate（+UNKNOWN if `optimistic=false`） |
| P2 距离源 | 新 `distance_buffer_obs_`：**仅 inflate 已知障碍**，UNKNOWN 不参与软代价 |
| 软代价 | `length × [1 + w × max(0, 1 − d/R)²]`，`d` 从硬膨胀边界起算（不减半宽） |
| 固定验证参 | **R=0.40 m，w=2.0**（未扫参） |
| F0 / 执行器 | 不变：`initial_footprint`+expand0.3；`kinematic_collision_v1.2`；gimbal |

可复现配置：

- P0：`INFLATION_PROFILE=legacy018`
- P1：`INFLATION_PROFILE=halfwidth`（launch 传入 `obstacles_inflation=$(half_w)` + `lock=true`）
- P2：`INFLATION_PROFILE=halfwidth_softcost`（同上 + `soft_R=0.40 soft_w=2.0`）

## 2. 案例来源（非用户视频）

找不到与用户视频一一对应的运行时，采用 formal150 / e2e 可复现 dump：

| 案例 | 来源 run | plan_seq | 用途 |
|------|----------|----------|------|
| 宽通道贴边 | `formalgimbal_…_TEEsavR23oF_sofa_0` | 9 / 15 | 原路径 `edge_min≈−0.13 m`（车身侵入 OCC 半宽） |
| 窄通仍可过 | `…_TEEsavR23oF_toilet_2` | 16 | P0 已过；验 P1/P2 可达性 |
| 窄通对照 | `e2e_…_dd4b_toilet_0` | 5 | 可达性略降（4→3）但路径仍在 |

规划模式：上述 dump 的 `stop_reason` 为 `frontier_path_ok` / `object_path_ok`，候选 `mode=active_frontier`；**未见 EXTREME 绕开硬检查**。末段接线仍会把 frontier 目标点 append 到 path（既有行为）。

## 3. 同图离线对照（主证据）

度量：相对 **原始 OCC** 的中心距 / **车身边缘净空** `edge = center − half_w`。

### 宽通道（sofa_0 seq9）

| | n_reach | path_len | edge_min | edge_p10 | center_min |
|--|---------|----------|----------|----------|------------|
| 原 selected_path | — | 2.59 | **−0.130** | −0.107 | 0.174 |
| P0 | 2 | 2.09 | **−0.125** | −0.094 | 0.180 |
| P1 | 2 | 2.27 | **+0.020** | +0.028 | 0.324 |
| P2 | 2 | 2.50 | **+0.025** | +0.072 | 0.329 |
| 实际执行轨迹 | — | — | −0.025 | — | — |

- **半宽硬膨胀（P1）单独**：把规划路径边缘净空从负值抬到约 +2 cm，中心距从 ≈0.18 提到 ≈0.32（≈半宽）。贴边/穿模级规划路径问题大部分由 P1 消除。
- **软代价（P2）额外**：edge_min 几乎不变；edge_p10 从 0.028→0.072，路径略绕（+10% 量级）。有助于“更居中”，但硬净空收益主要已在 P1。
- **执行**：同图 traj `edge_min≈−0.025` 仍劣于 P1/P2 规划 → **规划已离障时若仍贴边，应查跟踪/执行，而不是继续加大膨胀**。

seq15 同结论（P0 edge_min≈−0.12 → P1/P2 ≈+0.017；P2 p10 明显更高）。

俯视图：`case_wide_teesav_sofa0_seq9/p0p1p2_topdown.png`（及 seq15）。

### 窄门 / 窄通道

| 案例 | P0 reach | P1 | P2 | 备注 |
|------|----------|----|----|------|
| toilet2 seq16 | 4/6 | 4/6 | 4/6 | 长度几乎不变；P2 p10 略升 |
| dd4b toilet seq5 | 4 | 3 | 3 | 丢 1 个候选，最佳路径仍在 |

未见大规模 `NO_PATH`；窄通可达性损失有限（本批离线）。

## 4. 实现交付

- C++：`lock_obstacles_inflation`；`distance_buffer_obs_` + `getDistanceToKnownObstacle`；A* `edgeTraversalCost` + `astar/soft_cost_*`
- Adapter：`overlay_halfwidth*.yaml`；`run_apexnav_real_episode.sh` / launch 参数接线
- 离线：`adapters/.../offline_p0p1p2_inflation_compare.py`；`test_inflation_softcost_astar`（已编入容器）

## 5. 端到端短跑 / dev24

**本轮未跑**：GPU ≈40 GB 占用，且 `queue_after_formal` 仍挂起。  
SR / 碰撞率归因须等匹配执行器的短跑 + 候选 dev24；离线只支持规划路径结论。

## 6. 推荐

| 问题 | 结论 |
|------|------|
| 半宽膨胀单独解决多少贴边？ | 宽通道规划路径上，**负边缘净空 → 正净空**；贴边主因（0.18≪half_w）由 P1 直接修掉 |
| 软代价额外收益？ | **次要**：p10/居中更好，路径略长；硬碰撞边界仍靠 P1 |
| 窄门可达？ | 本批离线 **基本保留**；个别候选 −1 |
| 穿模/贴边仍在？ | 若规划已离障而 traj 仍贴边 → 跟踪/执行；矩形转弯扫掠未单独建模 |
| **推荐（离线半宽对照）** | 半宽硬膨胀对贴边有效；全半宽会堵窄通道。 |
| **当前采用候选（用户指定）** | **硬膨胀 0.20 m + 软代价 R=0.10 m / w=2.0**（`INFLATION_PROFILE=inf020_soft010`），兼顾净空与窄通道可达。 |

可复现：

```bash
INFLATION_PROFILE=inf020_soft010 ROBOT_SCALE=0.7 STARTUP_PRIOR_MODE=initial_footprint \
  CAMERA_MODE=fixed_base_gimbal MAX_EXPLORE_ACTIONS=100 MAX_STEPS=150 \
  bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
```

代表轨迹图：`reports/nav_inflation_softcost_20261118/case_wide_teesav_sofa0_seq9/`。  
半宽 P1/P2 对照仍保留作基线证据；短跑请用 `inf020_soft010`。
