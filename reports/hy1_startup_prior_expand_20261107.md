# 启动先验 F0 外扩（startup_prior_expand_m）

日期：2026-11-07  
同一冻结图：`reports/hy1_startup_prior_20261107/`  
原生回放：`test_startup_prior_astar`（含 A/B/C）

## 改动

- 新参数 `exploration/startup_prior_expand_m`（各向同性 margin，米）。
- 有效 F0 半轴 = 底盘足迹半轴 + `expand_m`；仍只放行 F0∩UNKNOWN；**不改写**占据；OCC/inflate/越界仍拒。
- Ranger 入口：`STARTUP_PRIOR_MODE=initial_footprint` 时默认 `STARTUP_PRIOR_EXPAND_M=0.3`；可显式设 `0` 回到精确足迹。
- 通用 launch 默认 `expand_m=0`；`mode=none` 不受影响。

0.7× 例：chassis half ≈ 0.456×0.304 → expand 0.3 → F0 half ≈ **0.756×0.604**。

## 冻结 A/B/C（expand sweep）

| 臂 | 配置 | 可达 /26 | F0 cells | best_len | 地图未改 |
|----|------|----------|----------|----------|----------|
| A | none | 0 | — | — | true |
| B | initial_footprint expand=0 | 5 | 221 | 0.626 | true |
| C | expand=0.3 | 5 | 729 | 0.531 | true |
| C | expand=0.5 | 5 | 1233 | 0.531 | true |
| C | expand=0.8 / 1.0 | 5 | （更大） | 0.531 | true |

C 安全检查（expand=0.3）：F0 内 UNKNOWN 放行、外 UNKNOWN 拒、OCC/inflate 拒、F0 不随动、clear 无残留 → **PASS**。

本冻结候选集上，外扩增大 F0 覆盖与略缩短路径，但**未增加可达候选数**（其余候选受 OCC/inflate 等约束，非「足迹外 UNKNOWN」单独导致）。端到端场景的环带 UNKNOWN 仍可受益；需在 live episode 再验 mid_stuck。

## 复现

```bash
# 容器内已 catkin_make --pkg path_searching
rosrun path_searching test_startup_prior_astar \
  _cells_csv:=.../hy1_startup_prior_20261107/cells.csv \
  _candidates_csv:=.../candidates.csv \
  _out_json:=.../hy1_startup_prior_expand_20261107/ab_expand_compare.json \
  _chassis_x:=1.4327 _chassis_y:=-23.7172 \
  _yaw:=-2.3315909698614945 _half_l:=0.4557 _half_w:=0.30429 _expand_m:=0.3

# 实验入口
STARTUP_PRIOR_MODE=initial_footprint STARTUP_PRIOR_EXPAND_M=0.3 \
  bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
# 精确足迹回退：STARTUP_PRIOR_EXPAND_M=0
```

产物：`ab_expand_compare.json`、`ab_expand_{0.5,0.8,1.0}.json`。

## Live 冒烟（rebuild 后，`smoke_exp03_20261107_164251`）

预算 150/100；`initial_footprint` + `expand_m=0.3`；HY1/eF36/yr17 各 1 ep。

| ep | 结果 | explore | fwd_m | n_expl | dtg |
|----|------|---------|-------|--------|-----|
| hy1_chair_3 | **success_proxy** | yes | 11.5 | 84 | 0.61 |
| ef36_chair_4 | **success_proxy** | yes | 9.5 | 73 | 0.93 |
| yr17_chair_0 | explore_no_goal | yes | 10.25 | 100 | 3.58 |

HY1 日志：`F0_half=0.7557x0.6043 expand_m=0.3000 cells=729`（与冻结一致）。

**注意**：仅重编 `path_searching`、未重编 `exploration_manager` 时，新增 `expand_m_` 成员会 ABI 错位 → `ensureStartupPrior` 空指针崩溃（首轮冒烟 3/3 `planner_action_timeout`）。两棵树（`/workspace/ApexNav` 软链）需同时 `catkin_make --pkg path_searching exploration_manager`。
