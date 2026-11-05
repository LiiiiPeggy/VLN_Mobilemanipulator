# Top-5 场景 ApexNav 探索对照与足迹安全

更新：2026-11-05  
保留：`4e9d1d7` Stage4.10d / yaw 修 / 开放带 spawn / 四轮可视化  
证据：`apexnav_real/real_wide_*`、`explore_failure_diag/`、`footprint_path_safety/yr17_openband/`

---

## 1. 跨场景短测（开放带 spawn，legacy018）

统一：`INFLATION_PROFILE=legacy018`，MAX_STEPS=50，26 步环视，`adapted_episode` 均标记。  
**不作为原版 ObjectNav benchmark 成绩。**

| 场景 | Run | entered_explore | 规划模式 | Explore 动作 | FWD m | free | 终止 |
|------|-----|-----------------|----------|--------------|-------|------|------|
| yr17PDCnDDW | `real_wide_yr17_openband_*` | ✓ | **SEARCH_EXTREME×12** | L3/R2/F6/S1 | **1.50** | 931 | planner_stop |
| HY1NcmCgn3n | `real_wide_hy1_openband_*` | ✓ | NO_PASSABLE×1 | STOP | 0 | 524 | planner_stop |
| eF36g7L6Z9M | `real_wide_ef36_openband_*` | ✓ | **EXPLORATION×24** | R16/L7/F1 | 0.25 | 2151 | step_budget |
| LT9Jq6dN3Ea | `real_wide_lt9ep0_openband_*` | ✓ | NO_PASSABLE×1 | STOP | 0 | 489 | planner_stop |
| k1cupFYWXJ6 | `real_wide_k1cupep3_openband_*` | ✓ | NO_COVERABLE×1 | STOP | 0 | 0 | planner_stop |
| Dd4b（对照） | `real_ctrl_dd4b_chair5_*` | ✓ | EXTREME×8 + EXPL×6 | R9/F5 | 1.25 | 184 | step_budget |

JSON：`apexnav_real/top5_openband_compare.json`。

### 三层验收区分

| 层级 | 含义 | 本轮结果 |
|------|------|----------|
| A 进入正式探索 | `entered_callActionPlanner` | **Top-5 全部 ✓**（另 Dd4b ✓） |
| B 算法能规划多步 | 非 STOP 的 planner 动作 ≥2 | **yr17、eF36、Dd4b** |
| C 机器人足迹安全 | 定向底盘扫掠间隙 ≥ 半宽 | yr17 路径 **不通过**（见 §3） |
| D 寻物成功 | `success_claimed` | **全部 false**（未宣称成功） |

---

## 2. yr17 vs HY1 差异

几何 Top 分接近（retain485≈0.50），开放带 spawn clearance 也接近（≈0.53–0.55 m），但：

| 信号 | yr17 | HY1 |
|------|------|-----|
| 环视后 online free | 931 | 524 |
| 首轮 explore | SEARCH_EXTREME → 持续 12 步 | 立即 NO_PASSABLE |
| `To the next point` 日志 | 11 | 0 |
| 前进 | 1.50 m | 0 |

**结论（有证据）**：

1. yr17 的「多步」主要来自 ApexNav **SEARCH_EXTREME**（可疑目标 / 宽松搜索），不是经典 Closest-Frontier `EXPLORATION`。  
2. HY1 在同类 spawn 下 Frontier/Extreme 均不可达 → 立即 STOP；不是评分脚本算错，而是**环视后局部地图上无 A\* 可达目标**。  
3. 开放带 spawn 必要但不充分；场景局部观测结构决定能否进入可执行规划。  
4. eF36 同策略下出现真正的 `EXPLORATION×24`（以转向为主），说明 Top 几何场景中**可以**出现经典 frontier 规划。

细节：`explore_failure_diag/yr17_vs_hy1.json`。

---

## 3. yr17 路径 · 真实足迹离线安全（GT 仅评价）

方法：对 explore 段 `MOVE_FORWARD/TURN_*` 插值 SE(2)，在 **重算 r=0.05 navmesh** 上检查底盘矩形角点 + 中心 clearance；准则：

- 中心 clearance ≥ half_width **0.435 m**  
- 角点可导航且 min_clearance ≥ 0.02 m  

结果（`footprint_path_safety/yr17_openband/`）：

| 指标 | 值 |
|------|-----|
| explore 底盘动作数 | 11 |
| oriented_safe_ratio | **0.0** |
| unsafe_count | 11 |
| 起步中心 clearance | ≈0.61 m（尚 ≥0.435） |
| 后续中心 clearance | 降至 ≈0.25–0.40 m（**< 半宽**） |
| 角点 | 几乎全程 `corners_ok=false` |

**解释**：`legacy018`（0.18 m）下 ApexNav **能规划并执行**，但按 Ranger 定向足迹回放，路径**不能**称为安全通行。`ranger_safe=0.485` 仍未在本轮用作在线规划，也不宣称任意朝向安全。臂外伸扫掠未计入多边形（仅备注）。

---

## 4. Demo

- yr17 7 FPS：`real_wide_yr17_openband_*/demo/apexnav_ranger_paper_demo_7fps.mp4`（ffprobe **7/1**，205 帧，1280×720）。  
- 四轮可视化已在 `set_base_pose` 接入；烟雾 `wheel_kinematics_smoke` pass。插值帧不伪造检测/地图。

---

## 5. 复现

```bash
# Top-3 短测批跑
MAX_STEPS=50 GPU=0 bash adapters/habitat_rangercr10/scripts/run_top5_openband_batch.sh

# yr17 vs HY1 诊断
docker exec -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  vln-rangercr10 bash -lc 'source /opt/ros/noetic/setup.bash; python -m src.explore_failure_diag'

# yr17 足迹安全
docker exec -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  vln-rangercr10 bash -lc 'source /opt/ros/noetic/setup.bash; python -m src.footprint_path_safety'
```

---

## 6. 结论

1. **五个 Top 场景均稳定进入正式探索阶段**（`entered_callActionPlanner`）。  
2. 多步可规划：**yr17（EXTREME）**、**eF36（EXPLORATION）**、对照 **Dd4b**；HY1/LT9/k1cup 仍早停。  
3. **规划成功 ≠ 足迹安全 ≠ 寻物成功**；yr17 路径足迹回放失败，寻物均未宣称成功。  
4. 未改 ApexNav baseline / PPO / Stage4.10d；ROS `:11311` 未动。
