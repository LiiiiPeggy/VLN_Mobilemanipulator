# 相机视场 / 环视角度 / 不可通行诊断报告

更新：2026-11-06  
分支：`cursor/habitat-rangercr10-scale070`  
性质：**诊断对照，非正式 ObjectNav 性能评测**；未改 ApexNav 规划器、0.7×、PPO、深度 NaN 策略、膨胀系数。

---

## 0. 交付索引

| 交付 | 路径 |
|------|------|
| 本报告 | `reports/habitat_rangercr10_lookaround_fov_passability.md` |
| Demo 去边框（上轮） | `reports/habitat_rangercr10_map_raster_fill.md` |
| FOV 离线诊断（mapfill 30° 正式环视） | `shared/runs_large/.../lookaround_fov_diag/.../REPORT.md` |
| 有界 yaw 对照 | `reports/lookaround_yawstep_compare_20261106/` + runs `.../lookaround_coverage_compare_20261106_071538` |
| 正式 episode 地图/Demo（保留） | `.../apexnav_real/real_s070_pporaise_yr17_mapfill_20261105_212419/` |

---

## 1. 地图显示（观感）

已保留 Occupancy + Value Map 配色（Occ 深灰 / Free 浅灰 / Unknown 白底 / Value 红黄仅盖自由格 / 蓝机器人 / 橙轨迹）。

**人为 cell 边框**：仅 Demo 栅格化改为按 `resolution=0.05 m` 实心足迹填充（`map_raster.py`），**不**改 `/grid_map`、不做插值/形态学膨胀。证据：同数据 Jaccard=1（见 `habitat_rangercr10_map_raster_fill.md`）。旧 Demo 未覆盖。

白色放射状扇区在原始点云中已存在，主因是 **unknown 夹在稀疏 free 射线扇区之间**，不是 1px 描边伪影。

---

## 2. 相机视场与环视角度

### 2.1 实测内参 → FOV（非拍脑袋固定角）

来源：ApexNav `exploration` launch `map_ros/fx,fy` @ 640×480，与 Habitat EE `HFOV=79°` 一致。

| 量 | 值 |
|----|-----|
| fx / fy | 388.191 / 422.048 |
| HFOV | **79.00°** |
| VFOV | **59.25°** |

### 2.2 正式环视（mapfill episode，ApexNav FSM）

证据 run：`real_s070_pporaise_yr17_mapfill_20261105_212419`  
离线：`lookaround_fov_diag.json` / `fov_rose_mapfill_30deg.png`

| 项 | 值 |
|----|-----|
| 环视 FSM | 1×TURN_DOWN + 12×TURN_LEFT + 1×TURN_UP + 12×TURN_LEFT（26 步） |
| 实测相邻 yaw 步 | **≈30.0°**（`TURN=π/6`） |
| 水平重叠 @30° | **49.0°（HFOV 的 62%）**；无负间隙 |
| 重叠表 | 15°→64°；20°→59°；30°→49°；45°→34° |
| 相机 pitch | −1.6° … +31.2°（TURN_DOWN/UP 经 joint3 FK） |
| 有效深度 | lookaround 帧 `frac_nan` ≈ 0.25–0.66（自遮挡几何 NaN，非改写成 5 m） |

**结论（FOV）**：当前 30° 步长 **不会**造成水平 FOV 楔形盲区；相邻视角重叠充足。白色径向空隙 ≠ 旋转过大留下的未覆盖角。

**姿态同步**：每帧 RGB-D 与 camera FK 同戳发布；环视中 pitch 随臂变，不是纯底盘 yaw。

---

## 3. 单帧 vs 多帧占据（同一 Episode）

mapfill lookaround 地图增长：

| 阶段 | occupied | free | unknown | value |
|------|----------|------|---------|-------|
| 单帧（step0 TURN_DOWN 后） | 40 | 57 | 21894 | 57 |
| 环视末（step25） | 584 | 1067 | 21478 | 1067 |
| 首规划快照 | 584 | 1067 | 21478 | 1067；inflate 1649 |

角向直方图（`angular_hist.json`）显示 occupied/free 呈扇区峰，与 30° 采样一致，而非均匀填满。

**无效深度**：NaN 像素在 C++ `map_ros` 中跳过，不再写成 max-range 假终点（上轮已修）。未知格不会因此被写成 occupied 终点。

---

## 4. 不可通行 / A* 分解（mapfill 首规划，GT 仅诊断）

`passability_summary.json`：

| 项 | 值 |
|----|-----|
| 起点 cell | **free** |
| 起点连通 free 分量 | 440 |
| Frontier seed / clusters | 468 / 16 |
| A* 试验 / 成功 | 16 / **4** |
| occupied / free / unknown / inflate | 584 / 1067 / 21478 / 1649 |

解读：

- **不是**「没有 frontier」；有 16 簇，其中 4 条 A* 通。
- 大量 **unknown** + **inflate(1649)** 压缩可走通道；白色观感区对规划是 unknown，不是误标 occupied。
- GT 探针（occ 点落在 navmesh 邻域比例高）表明许多 occupied 落在**可导航邻域薄障碍/高度带**附近——诊断用，**禁止入规划器**。不能直接等同「整片自由空间被标成障碍」。

---

## 5. 有界对照：同 spawn / 同 TURN_DOWN，仅改 yaw 步长

### 5.1 关键修复（对照脚本，非改规划）

映射-only 对照曾得到空地图。根因：**仅 PPO 抬臂、不做 TURN_DOWN** 时，ROS `camera_q`≈identity，光轴近似朝 **+Z（上）**，高度滤波清空点云。  
对齐正式环视：对照前施加 **joint3 −0.60（TURN_DOWN）**，pitch≈**31.2°** 后地图立即出现 occ=40/free=57（与 episode step0 一致）。

未改：规划器、0.7×、PPO 权重、深度 NaN、膨胀。

### 5.2 结果（yr17 同 start_pose，legacy018 inflation）

Run：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/lookaround_coverage_compare_20261106_071538`  
图：`reports/lookaround_yawstep_compare_20261106/yaw{15,30,45}_map_last.png`、`yawstep_occ_free_bars.png`

| yaw 步长 | 视角数 | H 重叠 | occupied | free | unknown |
|----------|--------|--------|----------|------|---------|
| **15°** | 24 | 64° | **1010** | **1275** | 20003 |
| **30°**（当前） | 12 | 49° | 584 | 954 | 21591 |
| **45°** | 8 | 34° | 281 | 550 | 23022 |

观察：

1. 更密的 yaw（15°）显著增加 occupied **与** free，缩小 unknown——覆盖更完整，不是「重复就更好看」的零和。
2. 更稀的 45° 覆盖明显变差（仍无水平 FOV 负间隙，但是射线扇区更疏）。
3. 30° mapping-only（固定俯视）occ=584 与正式 26 步环视后 occ=584 **同量级**；free 略少（正式环视含 TURN_UP 半圈，视角俯仰更多样）。
4. Value 在本对照中为 0：BLIP2 进程在驱动末被杀 / ITM 未稳定融合；**不影响**占据覆盖结论。正式 mapfill 有完整 value。

**是否应改环视步长？**  
证据表明 30° **不是**水平盲区根因；15° 能提高覆盖但成本更高。若后续要动环视，应**单独**改角度并重跑正式 episode，本轮不改 FSM。

---

## 6. 修改前后地图截图

| 说明 | 文件 |
|------|------|
| Demo cell-fill 去边框前后 | `reports/habitat_rangercr10_map_raster_fill.md` 引用 `map_raster_compare/` |
| mapfill 首规划 Occ+Value | `.../mapfill_first_plan_map.png` |
| 15/30/45° 对照末帧 | `yaw15/30/45_map_last.png` |
| FOV 楔形覆盖示意 | `fov_rose_mapfill_30deg.png` |

7fps Demo：沿用 mapfill `demo/apexnav_ranger_paper_demo_7fps.mp4`（未覆盖旧文件）。本轮无必要重生成。

---

## 7. 结论摘要

1. **白色栅格观感**：Demo 边框已用分辨率足迹消除；剩余白放射线主要是 unknown + 稀疏 free 扇区（原始数据），非插值可「抹掉」的问题。  
2. **D455 FOV 79°/59.25°**；30° 环视重叠 49°，**无**水平盲楔。  
3. **空地图对照故障**来自缺少 TURN_DOWN（光轴朝上），不是 sync 彻底坏掉。  
4. **不可通行**：起点 free、有 frontier 且部分 A* 通；主压力来自 unknown 连通与 inflate，而非「FOV 步长漏扫」。  
5. **15° vs 30° vs 45°**：覆盖随步长单调变好/变差；正式改步长留待单独决策。
