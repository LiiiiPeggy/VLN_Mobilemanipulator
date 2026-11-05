# Demo：ApexNav Occupancy + Value Map 叠加

更新：2026-11-05  
分支：`cursor/habitat-rangercr10-scale070`  
范围：仅 Demo 合成层（`map_listener` / `map_style` / `demo_compose` / episode 发布时序 / 7fps 重渲染）  
**未改**：Frontier、A*、PPO、控制策略、占据规划输入、BLIP-2 部署、对象融合/新检测器。

---

## 目标

右下角地图 = 白底几何占据 + ApexNav 原生 `/grid_map/value_map` 黄→红热力叠加。

## 实现

| 项 | 做法 |
|----|------|
| 占据底图 | 白底；free 浅灰；occ 深色；unknown 白；蓝机器人；橙轨迹 |
| 价值图 | 订阅 `/grid_map/value_map`（PointXYZI `intensity`） |
| 配色 | 对齐 `ApexNav.rviz` `semantic_score_map`：Min `(250,255,203)@0.10` → Max `(204,0,0)@0.35` |
| 叠加规则 | 仅 free / 有效价值格；α≈0.62；**occupied 最后绘制，不被覆盖** |
| ITM | 现有 `get_itm_message_cosine` → `/blip2/cosine_score`；**先发 cosine 再发 RGB-D**，同帧融合 |
| 图例 | Target / Value Score / 色条 + occ 色块 |
| 坐标系 | 与 `/grid_map` 同 world；机器人箭头用 ROS yaw |

## 证据 run

`real_s070_pporaise_yr17_valuemap_20261105_210015`

| 指标 | 值 |
|------|-----|
| `has_value_map` | True |
| value_map 点数 / msgs | 1067 / 252（与 free 对齐） |
| `/blip2/cosine_score` msgs | 41 |
| ITM cosine | min 0.103 / mean 0.180 / max 0.404 |
| 探索 | FWD×1 + TURN；`step_budget_exhausted` |
| Demo 7fps | **1280×720，7/1，346 帧**；旧 2fps mp4 保留 |

路径：

- 地图/Demo：`.../valuemap_.../maps/`、`.../demo/`
- 7fps：`.../demo/apexnav_ranger_paper_demo_7fps.mp4`
- 抽样：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/valuemap_demo_overlay/`

## 复现

```bash
ROOT=/home/ubuntu/locomani/VLN_Mobilemanipulator
OUT=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real
RAISE=/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_raise_stage410d_z040.json
FORCE=$OUT/real_wide_yr17_openband_20261105_012302/start_pose.json
RUN_ID=real_s070_pporaise_yr17_valuemap_$(date +%Y%m%d_%H%M%S)

INFLATION_PROFILE=legacy018 SCENE_FILTER=yr17PDCnDDW CATEGORY_FILTER=chair EPISODE_ID=0 \
  MAX_STEPS=40 GPU=0 RUN_ID="$RUN_ID" ROBOT_SCALE=0.7 \
  FORCE_SPAWN_JSON="$FORCE" PPO_RAISE_JSON="$RAISE" \
  bash $ROOT/adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh

RUN_DIR=$OUT/$RUN_ID GPU=0 bash $ROOT/adapters/habitat_rangercr10/scripts/run_demo_7fps.sh
```

换目标类别：改 `CATEGORY_FILTER` / episode `object_category`；ITM 文本随 `label`/`room` 更新，value_map 用新 cosine 融合。

## 修改文件

- `adapters/habitat_rangercr10/src/map_listener.py` — 订 value_map + 热力/图例  
- `adapters/habitat_rangercr10/src/map_style.py` — RViz 价值色常量  
- `adapters/habitat_rangercr10/src/demo_compose.py` — 面板标题  
- `adapters/habitat_rangercr10/src/apexnav_real_episode.py` — ITM→深度同帧顺序；渲染参数  
- `adapters/habitat_rangercr10/src/demo_7fps_from_run.py` — 保留价值色，勿 legacy 重映射冲掉热力  
