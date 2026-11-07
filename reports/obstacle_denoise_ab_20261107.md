# 障碍去噪 A/B + 冻结启动基线（2026-11-07）

仿真 ObjectNav 效果验证（非实机安全验收）。**AB24 已收完。**

## 冻结启动基线

| 项 | 值 | 说明 |
|----|-----|------|
| `startup_prior_mode` | `initial_footprint` | 查询放行 F0∩UNKNOWN |
| `expand_m` | **0.3** | **各向同性半轴外扩**（不是整边长） |
| 0.7× 底盘半轴 | 0.4557 × 0.3043 m | `footprint_at_scale` |
| **有效 F0 半轴** | **0.7557 × 0.6043 m** | chassis_half + expand |
| F0 整边长（参考） | 1.511 × 1.209 m | = 2 × 半轴；报告主用半轴 |
| 地图分辨率 | **0.05 m** | `sdf_map/resolution` |
| HY1 F0 cells（expand0.3） | **729** | 冻结/冒烟一致 |
| 环视 / 相机 / 门控 / 膨胀 / 策略 | 不变 | legacy018 inflate 0.18 |

`half_l`/`half_w`/`F0_half` 一律为**半轴**；完整边长仅作对照。

### 基础设施失败（不计 SR）

| 批次 | 原因 | 处置 |
|------|------|------|
| `smoke_exp03_20261107_162922` | 仅重编 `path_searching`，未重编 `exploration_manager` → ABI segfault | **infra_fail**，不计入算法成功率 |
| `smoke_exp03_20261107_164251` | 双包重编后有效基线冒烟 | **可用 A（denoise=none）** |

重编命令见 `adapters/habitat_rangercr10/README.md`。

### 可复用 A 冒烟（denoise=none，expand=0.3）

`batch_smoke_exp03_20261107_164251.jsonl`：hy1/ef36 **success**；yr17 explore 预算耗尽。

## 去噪开关

`obstacle_denoise=none|median3`  
- 仅过滤**当前帧**障碍投影再写入持久 OCC / 膨胀前。  
- 不改 FREE/UNKNOWN/OCC 三值编码本身、不改地面 free-ray、剔除命中不自动变 FREE、不延长射线。  
- 关闭 = 原流程。参考 HomeRobot `cv2.medianBlur(..., 3)`。

## A/B 协议

- A：`initial_footprint` + expand 0.3 + **none**  
- B：同上 + **median3**  
- 预算：MAX_STEPS=150 / MAX_EXPLORE=100；空地图起步  
- 清单：`reports/startup_prior_e2e_20261107/episode_list.json`（24 ep）  
- 成功代理：`planner_stop` ∧ dtg≤1.0 m；SPL N/A（无 geodesic）  
- 批次：`ab24_A_none_20261107_172219` / `ab24_B_med3_20261107_185105`

## 终表（n=24）

| 臂 | denoise | SR_proxy | start_blocked | mid_nopass | explore_no_goal | stop_not_near | mean_fwd_m | mean_n_explore | mean_inflate | mean_denoise_rm | fwd/(fwd+turn) |
|----|---------|----------|---------------|------------|-----------------|---------------|------------|----------------|--------------|-----------------|----------------|
| A | none | **3/24 (0.125)** | 0 | 0 | 18 | 3 | 10.65 | 90.1 | 475891 | 0 | 0.364 |
| B | median3 | **4/24 (0.167)** | 0 | 0 | 16 | 4 | 10.61 | 88.8 | 343056 | 17612 | 0.368 |

证据：`reports/obstacle_denoise_ab_20261107/aggregate_ab24_*.md`；`ab24_compare_summary.json`。

**路径长度 vs 净位移**：本适配路径无位姿轨迹 / geodesic → **N/A**（同 SPL）。代理：`forward_m`（累计前进米）与动作比 `FORWARD/(FORWARD+TURN)`；两臂几乎相同。

### 成功集

| 臂 | 成功 ep |
|----|---------|
| A | `ef36_bed_4`，`hy1_chair_3`，`lt9_chair_1` |
| B | `hy1_chair_3`，`lt9_chair_1`，`dd4b_chair_5`，`dd4b_toilet_0` |

### 跨臂翻转（fail_class）

| ep | A | B |
|----|---|---|
| `dd4b_chair_5` | stop_not_near (dtg≈4.90) | **ok** (dtg≈0.72) |
| `dd4b_toilet_0` | stop_not_near (dtg≈4.57) | **ok** (dtg≈0.62) |
| `ef36_bed_4` | **ok** (dtg≈0.98) | stop_not_near (dtg≈1.14，近失) |
| `lt9_toilet_2` | explore_no_goal | stop_not_near |
| `k1cup_chair_0` | explore_no_goal | stop_not_near |

## yr17 失败归类

见 `obstacle_denoise_ab_20261107/yr17_failure_class.md`：曾进 `SEARCH_BEST_OBJECT`，接近未闭合后退回探索至预算耗尽；**非**纯未找到，**非**停止门控单独失败。median3 冒烟未改善。

## 推荐配置

| 项 | 推荐 | 理由 |
|----|------|------|
| 启动先验 | **`initial_footprint` + `expand_m=0.3`** | 本批 start_blocked=0；与冻结 F0（半轴 0.756×0.604，729 cells）一致 |
| 障碍去噪 | **默认 `none`；`median3` 保留可选** | ΔSR 仅 +1/24，在 n=24 噪声内；inflate↓~28% 有地图变稀信号，但 `ef36_bed_4` 近失回归；主失败仍 `explore_no_goal`（A 18 / B 16）→ **去噪不是下一主攻** |
| 下一步 | 目标搜索 / 接近 / 停止链路 | 启动已解封后的主导瓶颈 |

**禁止宣称**：median3 已证明显著提升 ObjectNav；先验/去噪 = 实机安全。

## 样例视频

（`*.mp4` gitignore；落盘 D 盘，报告目录为符号链接）

路径：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/obstacle_denoise_ab_20261107_videos/`  
或 `reports/obstacle_denoise_ab_20261107/videos/`

| 文件 | 说明 |
|------|------|
| `A_ok_hy1_chair3.mp4` | A 成功 |
| `A_ok_ef36_bed4.mp4` | A 成功（B 近失） |
| `B_ok_dd4b_chair5.mp4` | B 相对 A 多出的成功 |
| `B_ok_dd4b_toilet0.mp4` | B 相对 A 多出的成功 |
| `A_fail_yr17_chair0.mp4` | yr17 接近未闭合 / 预算耗尽 |

## 产物索引

| 文件 | 用途 |
|------|------|
| `batch_ab24_A_none_*.jsonl` / `batch_ab24_B_med3_*.jsonl` | 逐 ep 行 |
| `aggregate_ab24_*.{md,json}` | 分臂汇总 |
| `ab24_compare_summary.json` | A/B 对照数字 |
| `yr17_failure_class.md` | yr17 归类 |
| `launch_ab24.sh` / `ab24_host.log` | 复现入口与主机日志 |
