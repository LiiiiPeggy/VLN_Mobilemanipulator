# HY1 前进/倒车路径规划三方案对比

**研究问题**：在 ApexNav 逐步视觉目标导航中，加入倒车执行与朝向感知的运动规划，能否降低狭窄环境碰撞、提高脱困效率并改善导航进展？

**工作分支**：`cursor/habitat-rangercr10-scale070`  
**任务开始 HEAD**：`0ef0f8f`  
**正式默认**：仍为 `REVERSE_PLANNING_MODE=A`（本轮未改部署默认）

## 1. 背景与故障现象

原始方案 A run：  
`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real_integrate/ppo_chassis_hy1_20261123_220210_hy1_plant_0`

- 终止 `explore_budget_exhausted`；`sum_moved_m≈0.85`；blocked=29。
- step 27–28 连续前进 ≈0.27 m 后贴墙；局部目标侧后；反复 `TURN_RIGHT` 因 `base_link`/`box_link` 碰撞截断/拒绝；legacy recovery 左右摆动无净进展。

细节：`reports/hy1_reverse_planning/phase1_source_review.md`。

## 2. 原始 ApexNav 规划与执行

- `Astar2D` → 二维点列；`decideNextAction` 仅前进/左右转。
- `KinoAstar`：Dubins shot + 非负 arc；自行车模型；**不是** Reeds–Shepp，且与 Ranger/PPO 原地转向不匹配。
- 执行层：`ppo_chassis` 回放 MuJoCo `vel_cmd` 片段 + Habitat `probe_base_motion`。

## 3. 三方案结构

| 方案 | 开关 | 要点 |
|------|------|------|
| A | `REVERSE_PLANNING_MODE=A` | 基线：二维 A* + 离散前进/转向 |
| B | `=B` | 保留二维 A*；路径引导 PPO 倒车（adapter） |
| C | `=C` | 全局 A* + **PPO 基元 Hybrid A\***（非 KinoAstar/非 RS） |

实现：`adapters/habitat_rangercr10/src/reverse_planning.py`，接入 `apexnav_real_episode.py`。  
入口：`reports/hy1_reverse_planning/run_abc_hy1.sh`。

## 4. PPO 倒车能力验证

`model_9999`，`vx=-0.25`，z_hold=0.40（真实 MuJoCo，非前进取负）：

| 目标 | 实际 d_forward | yaw 漂移 | 横向 |
|------|----------------|----------|------|
| 0.15 m | −0.194 | ~0.001 | ~0.002 |
| 0.25 m | −0.290 | ~0.002 | ~0.002 |
| 0.40 m | −0.417 | ~0.002 | ~0.002 |

证据目录：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_reverse_validation_model9999/`  
导航 unit：`ppo_chassis_bundle_model9999/move_backward.json`。

## 5. 公平实验配置

- HY1 plant eid0；`FORCE_SPAWN_JSON=.../hy1_plant_0_start_pose.json`
- `EXEC=ppo_chassis`，`LOOK=ppo_ee_rpy`，raise z040，scale 0.7
- 预算 orig：`max_steps=50`，`max_explore=20`（三方案相同）
- 倒车/恢复计入探索预算

## 6. 实验结果表

### 6.1 原始预算（max_explore=20）

| 方案 | run | sum_moved_m | blocked | reverse 次数 / m | hybrid 调用 | 终止 |
|------|-----|-------------|---------|------------------|-------------|------|
| A | `ppo_chassis_hy1_20261123_220210_...` | **0.85** | **29** | 0 / 0 | — | explore_budget_exhausted |
| B | `hy1_rev_B_orig_r1_20261124_050148_...` | **2.92** | **23** | 4 / 1.16 | 0 | explore_budget_exhausted |
| C | `hy1_rev_C_orig_r3_20261124_065931_...` | **4.23** | **13** | 6 / 1.74 | 4 | explore_budget_exhausted |

### 6.2 扩展预算（max_explore=60）

| 方案 | run | sum_moved_m | blocked | reverse / m | 终止 |
|------|-----|-------------|---------|-------------|------|
| B | `hy1_rev_B_ext_r1_20261124_070540_...` | **3.84** | 60 | 6 / 1.74 | explore_budget_exhausted |
| C | `hy1_rev_C_ext_r1_20261124_071619_...` | **5.27** | 50 | 6 / 1.74 | explore_budget_exhausted |

说明：C 的 orig r1/r2 因容器残留 `exploration_node` 出现 handshake timeout（已记录）；清理后 r3 成功。  
倒车累计上限约 1.6–1.7 m 后后期仍易再卡住。  
均未完成 ObjectNav STOP；**SR_proxy 未改定义**。证据支持该 HY1 案例中倒车改善位移/碰撞，**不外推普适 SR**。

机器可读：`reports/hy1_reverse_planning/metrics.csv`、`aggregate.json`。

## 7. 轨迹与碰撞

图（仅 PNG）：`reports/hy1_reverse_planning/figures/fig{1..4}_*.png`

- A：贴墙后大量 TURN_* blocked/truncated。
- B：step 31/35/39/44 路径引导 `MOVE_BACKWARD`，位移与档位切换上升。
- C：hybrid 在 explore 起点附近即插入倒车+转向组合；blocked 进一步下降。

## 8. 脱困成功与失败

- Escape（操作性）：B/C 均出现有效倒车并恢复部分前进（相对 A）。
- ObjectNav：三者均 budget exhausted；不能把脱困写成导航成功。
- C 环境失败（handshake）保留在 index，不作成功样例。

## 9. 方法代价与局限

- B：启发式触发，依赖 blocked streak + 路径几何；可能在开阔区误触发（有预算/累计上限）。
- C：状态格子依赖 PPO 基元与在线占用点；无图时碰撞剪枝弱，靠 turn_penalty/prepend_reverse。
- 未接入 DWA/DWB；未改 STOP；未用 GT 障碍助规划。
- 单场景 HY1 案例，**不宣称普适 SR 优势**。

## 10. 后续论文实验建议

1. 扩展预算（60 explore）配对 + 重复一致性。
2. 开阔/另一狭窄场景小回归。
3. Demo 7fps 仅作轮胎可视化点名复查；组会默认 2fps paper demo。
4. 在线 map footprint 碰撞检查加分辨率/膨胀标定后再谈 lattice 统计优势。

## Demo 索引

| 方案 | 2fps Demo |
|------|-----------|
| A | `.../ppo_chassis_hy1_20261123_220210_hy1_plant_0/demo/apexnav_ranger_paper_demo.mp4` |
| B | `.../hy1_rev_B_orig_r1_20261124_050148_hy1_plant_0/demo/apexnav_ranger_paper_demo.mp4` |
| C | `.../hy1_rev_C_orig_r3_20261124_065931_hy1_plant_0/demo/apexnav_ranger_paper_demo.mp4` |
