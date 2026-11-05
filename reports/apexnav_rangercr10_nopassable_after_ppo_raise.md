# PPO 抬臂后 NO_PASSABLE_FRONTIER 根因与修复

分支：`cursor/habitat-rangercr10-scale070`（保留 `f19f076` PPO 抬臂交接）  
标记：`scaled_robot_proxy_070`  
更新：2026-11-05

---

## 1. 现象（修复前）

抬臂后 yr17 / eF36 / HY1：26 步环视完成 → 首次 `callActionPlanner` → 立即 `NO_PASSABLE_FRONTIER`（expl_result=4）→ STOP。  
对照：同 spawn 无抬臂 0.7× yr17 曾靠 `SEARCH_EXTREME` 多步前进。

证据：`real_s070_pporaise_yr17_20261105_171118`（FWD=0）。

---

## 2. 首次规划诊断（必须项）

适配层 `planner_first_call_diag/`（首次 explore 步落盘）：

| 项 | 修复前（抬臂+绝对 Z） | 中间（仅 AGL Z） | 修复后 |
|----|----------------------|------------------|--------|
| camera ROS Z | ≈−0.07（绝对 Habitat Y） | ≈0.881 AGL | ≈0.881 AGL |
| base 栅格状态 | （未系统 dump） | **unknown** | **free** |
| free 连通分量 | — | 1 | 24（yr17） |
| Frontier 簇 | 有（日志非 NO_COVERABLE） | 10 | 12 |
| 规划结果 | expl=4 STOP | expl=4 STOP | expl=0×N + FWD |

关键地图点云：`*/planner_first_call_diag/{free,occupied,unknown,occupied_inflate}_xy.npy` + `first_plan_map_diag.png`。

---

## 3. 根因链（适配层，非 ApexNav 算法 bug）

### 3.1 高度滤波与地板假设错位

`map_ros` 假定 `cur_floor_height=0`，障碍带 **AGL [0.28, 1.18]**（`algorithm.xml`）。  
适配层原发布 `ROS_z = hab_y`（yr17 floor≈−0.95）→ 家具落入 **AGL≈1.23–2.13** 才进 occupied。  
抬高相机后可见更多高处命中；同时 **机体近距点** 在错误 Z 下常被滤掉，掩盖自遮挡。

### 3.2 臂载相机 vs 底盘规划起点

建图射线原点 = `/map_ros/pose`（D455）；A* 起点 = `/odom_world`（底盘）。  
抬臂后二者水平距 ≈**0.65 m**。底盘格常为 **UNKNOWN**，超出 A* 0.25 m 起点松弛 → Frontier NORMAL 路径全失败。  
无抬臂时偶发靠 `SEARCH_EXTREME`（忽略占用）+ 目标点云续命。

### 3.3 臂载自遮挡（AGL Z 对齐后暴露）

AGL 对齐后，机体/臂在 FOV 内近距点（常 &lt;0.5 m）进入障碍带 → 相机旁 **OCCUPIED/inflate**。  
实测抬臂环视末 occupied 距相机可达 **≈0.03 m**；free 最近 ≈0.39 m。

注：`map_ros/depth_filter_mindist` 会被 Habitat `depth_sensor.min_depth=0.0` **覆盖**（日志 `depth_filter_range=[0.00,5.00]`），仅改 launch mindist **无效**。

---

## 4. 修复（仅适配层；未改 baselines/ApexNav 源码默认）

| 修复 | 位置 | 说明 |
|------|------|------|
| ROS Z = AGL | `coord_habitat_ros.hab_pos_to_ros(..., floor_y)` | 对齐 ApexNav 高度滤波 |
| 规划 odom XY = D455 XY | `ros_dynamic_publisher` | 起点落入建图 free；Z 仍为底盘 AGL；yaw 仍为底盘 |
| 近距自遮挡屏蔽 | 同文件 `self_hit_min_depth_m=0.65` | 发布前将 (0,0.65) m 深度改写为 max；保持 decode [0,5] |
| 首次规划诊断 | `planner_first_call_diag.py` | 地图/Frontier 代理/A* 回放落盘 |

**未做**：optimistic=true、关碰撞、缩小膨胀、改目标真值、scripted policy、重训 PPO、IK。

与原版 ApexNav 差异：上述三项为 **Ranger 臂载相机 + HM3D 非零地板** 的适配契约；上游 `algorithm.xml` 未改。

---

## 5. 修复前后探索结果

JSONL：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/ppo_raise_s070_nopassable_fix_20261105_183429.jsonl`

| 场景 | 修复前 | 修复后 | 证据 run |
|------|--------|--------|----------|
| yr17 | explore STOP×1，FWD=0，expl=4 | **EXPLORATION×8**，TURN×7，**FWD×1 (0.25 m)**，后 STOP | `..._yr17_fix_20261105_183316` |
| eF36 | STOP×1 | EXPLORATION×1（TURN）后 STOP；起点 free | `..._ef36_fix_20261105_183429` |
| HY1 | STOP×1 | **EXPLORATION×54**，FWD 0.25 m，step budget | `..._hy1_fix_20261105_183518` |

闭环已现：`Frontier → A* → plan_action → 执行 → 新 RGB-D → 地图更新 → 再规划`（yr17/HY1）。寻物未宣称成功。

Demo：`real_s070_pporaise_yr17_fix_20261105_183316/demo/apexnav_ranger_paper_demo_7fps.mp4`（1280×720，7/1，167 帧）。

---

## 6. 复现

```bash
# 已有 PPO 抬臂 JSON
export PPO_RAISE_JSON=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json
export ROBOT_SCALE=0.7 INFLATION_PROFILE=legacy018 MAX_STEPS=80
# 例：yr17
SCENE_FILTER=yr17PDCnDDW CATEGORY_FILTER=chair EPISODE_ID=0 \
FORCE_SPAWN_JSON=.../real_wide_yr17_openband_20261105_012302/start_pose.json \
RUN_ID=real_s070_pporaise_yr17_fix_rerun \
bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
```

或批跑：`bash adapters/habitat_rangercr10/scripts/run_ppo_raise_then_apexnav_s070.sh`（含 MuJoCo 抬臂）。

---

## 7. 结论

1. **根因**：非 Frontier 检测为空，而是 **AGL 高度错位 + 臂载相机/底盘起点不一致 + 自遮挡进 occupied**，导致抬臂后 A* 不可达并失去 EXTREME 兜底。  
2. **修复后**至少一个场景（yr17，且 HY1 更长）恢复真实多步 ApexNav 探索；保留 PPO 抬臂与 0.7× 代理标记。  
3. 1.0× 模型 / PPO 权重 / ApexNav 算法源码默认未改。
