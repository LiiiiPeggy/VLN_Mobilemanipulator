# Startup prior → Ranger ObjectNav e2e（2026-11-07）

仿真任务效果验证（非实机安全认证）。分支：`cursor/habitat-rangercr10-scale070`；先验实现：`5860fc5`。

## 任务类型

**ObjectNav**（HM3D-v2 val），入口 `apexnav_real_episode` / ApexNav planner。  
**不是**指令 VLN。成功代理：`termination==planner_stop` ∧ `near_goal`（dtg ≤ 1.0 m）。  
官方 challenge SPL 本适配路径无 geodesic，**未计算（N/A）**；下表 SR 为 proxy。

## 复现配置与命令

```bash
# 固定清单
LIST=reports/startup_prior_e2e_20261107/episode_list.json

# 冒烟 B（已完成 smoke_B_20261107_015113）
SMOKE_ONLY=1 MODE_FILTER=initial_footprint BATCH_ID=smoke_B_YYYYMMDD_HHMMSS \
  bash adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh

# 短预算 A/B 24×2（已完成 ab24_20261107_015625）
# MAX_STEPS=50 MAX_EXPLORE_ACTIONS=20
SMOKE_ONLY=0 MODE_FILTER= BATCH_ID=ab24_YYYYMMDD_HHMMSS \
  bash adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh

# 预算100 全量 A/B（已完成 ab24_b100_20261107_123427）
bash reports/startup_prior_e2e_20261107/launch_ab24_b100.sh
# 等价：
# EPISODE_LIST=$LIST SMOKE_ONLY=0 MODE_FILTER= BATCH_ID=ab24_b100_YYYYMMDD_HHMMSS \
#   MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 SKIP_DEMO=1 \
#   bash adapters/habitat_rangercr10/scripts/run_startup_prior_e2e_eval.sh

# Ranger 实验显式启用先验（通用 launch 默认仍为 none）
STARTUP_PRIOR_MODE=initial_footprint \
  bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
```

- F0 固定初始底盘位姿；不改写原始占据图；保留 OCC/inflate/越界拒绝；无 0.25 m near-start skip。
- 本轮未改 15° / 臂姿 / 地面门控 / voxel / 目标识别 / 导航策略。
- 最小唯一改动（短预算→b100）：`MAX_EXPLORE_ACTIONS` 20→100，`MAX_STEPS` 50→150。

## 固定 episode 清单

`reports/startup_prior_e2e_20261107/episode_list.json`：24 ep，6 场景（yr17 / eF36 / HY1 / LT9 / k1cup / Dd4b），多类别；同一 `force_spawn_json` + 种子协议。

## 冒烟（B=`initial_footprint`）

| ep | explore | nopass | fail | fwd_m |
|----|---------|--------|------|-------|
| hy1_chair_3 | yes | 0 | explore_no_goal | 2.75 |
| ef36_chair_4 | yes | 0 | explore_no_goal | 1.25 |
| yr17_chair_0 | yes | 0 | explore_no_goal | 2.00 |

结论：能结束初始化并持续探索；无崩溃 / 无反复 NO_PASSABLE 启动阻断。

## 短预算 A/B 汇总（`ab24_20261107_015625`）

预算：`max_steps=50`，`max_explore_actions=20`。

| mode | n | SR_proxy | start_blocked | mid_nopass/stuck | explore_no_goal | mean_fwd_m | mean_n_explore | mean_t_s |
|------|---|----------|---------------|------------------|-----------------|------------|----------------|----------|
| none (A) | 24 | **1/24 = 4.2%** | **5/24 = 20.8%** | 1/24 | 17/24 | 1.39 | 15.3 | 78 |
| initial_footprint (B) | 24 | **0/24 = 0%** | **0/24 = 0%** | 5/24 | 19/24 | 1.70 | 18.9 | 77 |

SPL：N/A（无 geodesic）。

证据：`batch_ab24_20261107_015625.jsonl`、`aggregate_ab24_20261107_015625.md`、`pairwise_ab24.csv`。

## 近失探针（B only，`probe_b100_20261107_122305`）

| ep | 短预算 fail / dtg | 预算100 | 结论 |
|----|-------------------|---------|------|
| ef36_bed_4 | explore_no_goal / 1.46 | **ok_success_proxy** dtg=0.98 expl=28 | 近失闭合成功 |
| lt9_sofa_4 | explore_no_goal / 1.21 | explore_no_goal dtg=5.64 fwd=11.75 expl=100 | 走得更远但未锁目标 |
| dd4b_plant_5 | mid_stuck / 1.11 | mid_stuck dtg=1.11 expl=14 | 预算无助，仍中途停 |

## 全量预算100 A/B（`ab24_b100_20261107_123427`）— **最终**

预算：`max_steps=150`，`max_explore_actions=100`，`SKIP_DEMO=1`；48/48 完成，`AB24_B100_DONE`。

| mode | n | SR_proxy | start_blocked | mid_nopass/stuck | explore_no_goal | stop_not_near | mean_fwd_m | mean_n_explore | mean_t_s |
|------|---|----------|---------------|------------------|-----------------|---------------|------------|----------------|----------|
| none (A) | 24 | **2/24 = 8.3%** | **5/24 = 20.8%** | 3/24 | 10/24 | 3/24 | 7.01 | 61.7 | 157 |
| initial_footprint (B) | 24 | **3/24 = 12.5%** | **0/24 = 0%** | 5/24 | **14/24** | 2/24 | 8.25 | 74.8 | 192 |

SPL：**N/A**（无 geodesic）。

证据：
- `reports/startup_prior_e2e_20261107/batch_ab24_b100_20261107_123427.jsonl`
- `reports/startup_prior_e2e_20261107/aggregate_ab24_b100_20261107_123427.md`
- `reports/startup_prior_e2e_20261107/pairwise_ab24_b100.csv`
- 运行根：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/e2e_sp_ab24_b100_20261107_123427_*`

### Pairwise（同 ep，A→B）

| 对照 | 计数 |
|------|------|
| 双方成功 | 2（`ef36_bed_4`，`lt9_chair_1`） |
| 仅 B 成功 | 1（`hy1_chair_3`：A=`start_blocked` → B success dtg=0.70） |
| 仅 A 成功 | 0 |
| 双方失败 | 21 |

A 五个 `start_blocked` → B：1 成功（hy1_chair_3）、3×`explore_no_goal`（HY1 其余）、1×`mid_stuck`（dd4b_plant_5，dtg≈1.11）。

### 成功 episode（b100）

| mode | ep | dtg | fwd_m | n_explore |
|------|-----|-----|-------|-----------|
| A | ef36_bed_4 | 0.75 | 1.0 | 14 |
| A | lt9_chair_1 | 0.86 | 13.5 | 83 |
| B | ef36_bed_4 | 0.98 | 2.75 | 28 |
| B | hy1_chair_3 | 0.70 | 11.0 | 96 |
| B | lt9_chair_1 | 0.83 | 13.5 | 90 |

### 与短预算对比

| 指标 | 短 A | 短 B | b100 A | b100 B |
|------|------|------|--------|--------|
| SR_proxy | 1/24 | 0/24 | 2/24 | **3/24** |
| start_blocked | 5/24 | 0/24 | 5/24 | **0/24** |
| explore_no_goal | 17/24 | 19/24 | 10/24 | 14/24 |
| mean_fwd_m | 1.39 | 1.70 | 7.01 | 8.25 |
| mean_t_s | 78 | 77 | 157 | 192 |

拉长预算后：A/B 都能走得更远、SR 略升；先验仍消除启动阻断，并把 1 个 HY1 阻断题转为成功。B 主失败类仍是 `explore_no_goal`（14/24≈58%），mean dtg≈5.4 m；b100 下 B 的 explore_no_goal 已无 dtg≤1.5 近失（短预算近失已被预算或其它类吸收）。

### 失败分类（B，b100）

1. **探索未找到/未到达目标** `explore_no_goal`：**14/24（58%）** — 主瓶颈；多数 `explore_budget_exhausted`。
2. 途中规划中断 `mid_plan_nopassable_or_stuck`：5/24（21%）。
3. 停止但不在目标 `stop_not_near_goal`：2/24。
4. 启动仍被 UNKNOWN 阻断：0/24。
5. 运行接口错误：0。

A 另有 `other` 1 例（`k1cup_plant_0`：dtg≈0.81 却预算耗尽未 `planner_stop`）— 属目标锁定/停止链路信号，非启动问题。

## 代表视频

短预算已打包：`reports/startup_prior_e2e_20261107/videos/`

| 文件 | 含义 |
|------|------|
| A_hy1_start_blocked.mp4 | A：HY1 启动阻断 |
| B_hy1_explore_ok.mp4 | B：同 spawn 可探索 |
| A_ef36_success.mp4 | A：短预算成功 proxy |
| B_ef36_near_miss.mp4 | B：短预算近失（b100 已闭合成功） |
| B_lt9_near_miss.mp4 | B：dtg≈1.21 耗尽 |
| B_k1cup_mid_stuck.mp4 | B：途中卡住 |

b100 成功 run（帧目录，SKIP_DEMO 无新 mp4）：
- `.../e2e_sp_ab24_b100_20261107_123427_initial_footprint_hy1_chair_3/demo/`
- `.../e2e_sp_ab24_b100_20261107_123427_initial_footprint_ef36_bed_4/demo/`
- `.../e2e_sp_ab24_b100_20261107_123427_initial_footprint_lt9_chair_1/demo/`

## 对三个优先问题的回答（含 b100 终表）

1. **启用初始足迹先验后，是否更容易开始并持续探索？**  
   **是。** 启动阻断 5/24→0/24（短预算与 b100 一致）；mean 前进 7.01→8.25 m；mean 探索步 61.7→74.8；HY1 阻断题可进入探索，其中 1 题成功。

2. **任务成功率与 SPL 是否改善？**  
   **SR_proxy 略改善（b100：2/24→3/24）；SPL 仍 N/A。** 短预算下先验未抬 SR（预算过短掩盖）；拉长预算后先验多兑现 1 个 HY1 成功。改善幅度有限，不是数量级跃迁。

3. **当前限制任务效果的第一大问题？**  
   **目标搜索/到达闭合不足（`explore_no_goal` 仍为 B 主失败 14/24），不是脚下 UNKNOWN，也不是探索预算本身。** 最小预算修复（100）已做完；下一步应攻目标搜索与停止决策，**不回头扩 F0**，不开并行几何/感知重构。

## 下一步（最值得）

1. **目标搜索 / 停止链路**：检测锁定、何时 `planner_stop`、near-goal 闭合（含 A 的 dtg≈0.81 却未停案例）。  
2. 次要：途中 `mid_plan_nopassable_or_stuck`（k1cup / dd4b）。  
3. 不做：扩 F0、恢复半径豁免、同时开 voxel/门控/15° 大改。

本阶段交付：ObjectNav 端到端 A/B（短预算 + 探针 + **b100 全量终表**）+ 下一步依据。
