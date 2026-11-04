# ApexNav × Ranger+CR10：膨胀 / Frontier / 频繁转向诊断

更新：2026-11-04（补齐狭窄验证、中档膨胀、对照表与面板图）  
范围：`adapters/habitat_rangercr10/`（**不改** `baselines/ApexNav` 默认源码）  
证据：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/frontier_inflation_diag/`  
对照 Episode：见 §4 `episode_compare.json`

---

## 1. 机器人尺寸 vs 原版膨胀

| 量 | 值 | 来源 |
|----|-----|------|
| Habitat / ApexNav 默认 agent radius | **0.18 m** | `habitat_eval_hm3dv2.yaml`；运行日志 `obstacles_inflation_=0.18` |
| `sdf_map/obstacles_inflation`（XML） | 0.18 m | `algorithm.xml`；可被 Habitat radius **覆盖** |
| `sdf_map/optimistic` | **false** | 未知格在 ESDF 中当作障碍（`sdf_map2d.cpp`） |
| Ranger `base_link_col` 半长/半宽 | **0.651 / 0.435 m** | MuJoCo Stage4.10d |
| 底盘外接圆半径 | **≈0.783 m** | \(\sqrt{0.651^2+0.435^2}\) |
| 建议定向行驶规划半径 | **0.485 m** | half_width + 0.05 |
| 建议全向安全半径 | **≈0.83 m** | circum + 0.05 |

**结论**：0.18 m **远小于** Ranger 底盘占用，对真实碰撞安全不足；**不是**“膨胀过大”导致转向，而是规划按小车体在走。

机械臂 LOOK 时水平外伸随姿态变化（home 外接可达 ~1.0 m+）；当前 ApexNav 仅各向同性底盘膨胀，臂外伸未单独建模。

生效机制：`rosparam get .../obstacles_inflation` 可能仍显示 0.18，但 C++ 以 Habitat `main_agent.radius` 覆盖运行时膨胀（足迹档 inflate 像素显著变大可证）。

---

## 2. 频繁转向的主因（已修复）

对开阔 `Dd4bFSTQ8gi` chair/5 的 `MOVE_FORWARD`：

| 指标 | 修复前（114652） | 修复后（`hab_yaw_to_ros = hab_yaw+π`） |
|------|------------------|----------------------------------------|
| ROS 位移航向 vs odom 航向 | **恒为 180°** | **≈0°** |
| Explore `TURN_LEFT` 最长连击 | **6**（≈180°空转） | **0**（legacy018） |
| Explore 动作 | L×20 + FWD×4 | R×9 + FWD×5（legacy018） |

根因：适配层把 odom 航向发成 Habitat yaw，但位置用 `(-z,-x)`，运动学前进在 ROS 下航向为 `hab_yaw+π`。规划器以为车头反了，持续 `TURN_LEFT` 才能对准。

修复：`coord_habitat_ros.hab_yaw_to_ros` + `ros_dynamic_publisher.py`（**仅适配层**）。

左右符号：修复后同时出现 `TURN_RIGHT`，与 `decideNextAction`（`yaw_diff>0 → LEFT`）一致，无额外符号反转问题。

---

## 3. Frontier / 自由空间 / optimistic

### 3.1 离线 PNG 再膨胀代理（开阔 114652 终局图）

| 变体 | inflation | free_after_inflate_px |
|------|-----------|------------------------|
| A 基线 | 0.18 | 270 |
| M 中档 | 0.25 / 0.30 / 0.35 / 0.40 | 182 / 125 / 102 / 99 |
| B 定向安全 | 0.485 | 98 |
| B2 全向安全 | 0.83 | 98 |
| C 过小诊断 | 0.05 | 270 |

面板：`frontier_inflation_diag/open_*/map_panel_raw_018_030_0485.png`（raw / 0.18 / 0.30 / 0.485）。

### 3.2 在线实测（Habitat radius → 膨胀）

| Episode | radius 生效 | free | inflate | 结果 |
|---------|-------------|------|---------|------|
| 114652 修复前 | 0.18 | 182 | 1768 | 预算耗尽；左转刷屏 |
| yawfix + **0.485** | **0.485** | **0** | 3518 | 早停 STOP |
| yawfix + **0.30** | **0.30** | **1** | 2864 | 早停；FWD 1.0 m 后 STOP |
| yawfix + **0.18** | 0.18 | 182 | 1768 | 预算耗尽；FWD 1.25 m |
| 窄 114357 / yawfix 窄 | 0.18 | 169 | 979 | **expl_result=4 NO_PASSABLE**；仅 STOP×1 |

`optimistic=false`：未知参与 ESDF。窄场景在 yaw 修复后仍立即 `NO_PASSABLE_FRONTIER` → **不是航向问题**，而是稀疏 free + 未知障碍 + 出生走廊导致无可达 Frontier。  
**未**为刷前进次数而把 optimistic 改 true。

---

## 4. 对照表（验收）

完整 JSON：`frontier_inflation_diag/episode_compare.json`。

| 配置 | 场景 | yaw 误差 | Explore | FWD 距离 | 左连续 | free | 备注 |
|------|------|----------|---------|----------|--------|------|------|
| A 原版 | 开 114652 | 180° | L20/F4 | 1.00 m | 6 | 182 | 基线 |
| B 足迹 0.485 + yaw | 开 | ≈0° | R5/F4/L1/S1 | 1.00 m | 1 | **0** | 安全半径；自由空间被吃光 |
| M 中档 0.30 + yaw | 开 | ≈0° | R5/F4/L1/S1 | 1.00 m | 1 | **1** | 仍不安全；在线几乎无 free |
| C′ yaw + 0.18 | 开 | ≈0° | R9/F5 | **1.25 m** | 0 | 182 | Habitat 演示推荐；**对实机底盘仍不安全** |
| 窄 原版 | 窄 114357 | — | S1 | 0 | 0 | 169 | NO_PASSABLE |
| 窄 yaw + 0.18 | 窄 | — | S1 | 0 | 0 | 169 | 同 NO_PASSABLE；yaw 无关 |

**最佳安全适配（实机）**：`ranger_safe=0.485`，接受 Frontier/探索大幅变差，除非改为非圆足迹或单独处理未知区。  
**最佳 Habitat 演示（保留探索）**：`legacy018` + 已修 yaw；须在报告中标明对 Ranger 底盘不安全。

---

## 5. 适配配置（独立于 baseline）

| 文件 | 作用 |
|------|------|
| `config/apexnav_rangercr10_overlay.yaml` | `radius/inflation=0.485`，`optimistic=false` |
| `config/apexnav_rangercr10_overlay_mid030.yaml` | 0.30 灵敏度（仍标不安全） |
| `config/apexnav_rangercr10_overlay_legacy018.yaml` | 0.18 诊断/Habitat 演示 |
| `launch/exploration_rangercr10.launch` | 加载上游 algorithm + overlay |
| `INFLATION_PROFILE=legacy018\|mid030\|ranger_safe` | `run_apexnav_real_episode.sh` |

默认 Habitat 闭环：`legacy018` + **已修 yaw**。实机/安全验收：`ranger_safe`。

Demo：原 7 FPS（`20261104_114652`）保留；yaw 修复后可选重渲  
`real_yawfix_legacy018_*/demo/apexnav_ranger_paper_demo_7fps.mp4`。

---

## 6. 结论

1. **优先根因是 odom 航向 π 偏差**，不是“膨胀过大”。已在适配层修复并验证。  
2. **0.18 m 对 Ranger 足迹不安全**；0.30 / 0.485 在线都会把 free 压到 ≈0–1，无法靠单纯加大膨胀同时保住安全与可达 Frontier。  
3. 窄场景 `NO_PASSABLE` 在 yaw 修复后依旧 → 地图/未知/足迹几何问题，需后续非圆足迹或未知区策略（本轮不改规划器）。  
4. 未改 ApexNav 规划算法 / PPO / Stage4.10d 模型；ROS 仍用 `:11312`。
