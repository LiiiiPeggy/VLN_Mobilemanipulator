# Wrong-stop / success audit (dev24_after_dinofix_20261119_011332)

## Answer: why 12 STOPs outside 1 m?
全部 12 例错误 STOP 的 `expl_result` 为 **4=NO_PASSABLE_FRONTIER** 或 **5=NO_COVERABLE_FRONTIER**。
FSM：`NO_FRONTIER`→`FINISH`→`ACTION::STOP`（`exploration_fsm.cpp`）。**不是** SEARCH_BEST 选错物体。
几乎全部 `label_hist={}`。

## Success 4/24 vs SEARCH_BEST 1/24
| id | spawn | moved_m | dtg@STOP | STOP 分支 | 正确物体证据 |
|---|---|---:|---:|---|---|
| ef36_bed_4 | ok | 0.5250000000000004 | 0.016 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 弱：NO_COVERABLE 碰巧近床 |
| lt9_tv_0 | invalid_initial_penetration | 0.0 | 0.320 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无：穿模零位移，起点≤1m |
| lt9_sofa_4 | invalid_initial_penetration | 0.0 | 0.231 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无：穿模零位移，起点≤1m |
| dd4b_plant_5 | ok | 2.3833333333333333 | 0.035 | SEARCH_BEST→REACH_OBJECT→STOP | 有：SEARCH_BEST；真实 plant/flower |

## Wrong stops 12
| id | cat | spawn | moved | dtg@STOP | STOP 分支 | 目标选择 | 物体证据 |
|---|---|---|---:|---:|---|---|---|
| yr17_plant_0 | plant | ok | 0.7500000000000006 | 5.174 | NO_PASSABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| yr17_chair_0 | chair | ok | 0.7500000000000006 | 3.949 | NO_PASSABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| yr17_sofa_0 | sofa | ok | 0.7500000000000006 | 10.640 | NO_PASSABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| yr17_tv_0 | tv_monitor | ok | 0.7500000000000006 | 2.622 | NO_PASSABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| ef36_plant_4 | plant | ok | 0.5250000000000004 | 8.331 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| ef36_tv_3 | tv_monitor | ok | 0.5250000000000004 | 7.730 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| ef36_toilet_3 | toilet | ok | 0.6666666666666672 | 16.575 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| hy1_plant_0 | plant | ok | 2.458333333333335 | 2.313 | NO_PASSABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| hy1_chair_3 | chair | ok | 2.458333333333335 | 6.258 | NO_PASSABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| hy1_plant_1 | plant | ok | 2.458333333333335 | 2.313 | NO_PASSABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| lt9_chair_1 | chair | invalid_initial_penetration | 0.0 | 5.049 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |
| lt9_toilet_2 | toilet | invalid_initial_penetration | 0.0 | 2.628 | NO_COVERABLE_FRONTIER→NO_FRONTIER→FINISH→STOP | 无 SEARCH | 无 |

## lt9_tv_0 / lt9_sofa_4
invalid_initial_penetration + moved=0，但仍 sr_proxy（STOP∧dtg≤1）。**保留 4/24 账本**。

## 检测抽查
dd4b：真实 plant；XB4：挂画假阳性 `potted plant plant`。12 错误 STOP 无 label0 → 非 vase/子串主因。

## 统计链
SEARCH_BEST 与 frontier-STOP 成功解耦；非解析遗漏。

## 最小修复
**NoFrontierLook**：NO_FRONTIER 时环视最多 24 步再 FINISH→STOP。
