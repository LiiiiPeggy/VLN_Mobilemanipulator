# 目标发现：HM3D→Apex 类别映射最小修复（2026-11-08）

仿真 ObjectNav（非实机）。冻结：`initial_footprint` + `expand_m=0.3` + `obstacle_denoise=none` + ObjectHold 不变。  
基线 Hold：`ab24_hold_20261107_231416`（SR_proxy 4/24）；本批：`ab24_labelmap_20261108_220204`。

## 发现链路与主阻断

详见 `discovery_label_map_20261108/classify_never_search.md`。

| 阶段 | 位点 | Hold 批 16 从未 SEARCH 的主因 |
|------|------|------------------------------|
| RGB | `observe_ee_only` | 非主因（B 类未证「无视角」） |
| **类别映射** | `apexnav_real_episode` label 初始化 | **主阻断**：`category_to_coco` ImportError 被吞 |
| 检测 | `get_object` / YOLO+DINO | plant/sofa/tv_monitor 不在 COCO / 答案键 |
| 点云→SEARCH | clouds → `SEARCH_BEST_OBJECT` | 映射失败时全剧 `n_detections=0` |

**触发条件**：`object_category ∈ {plant, sofa, tv_monitor}` → 标签未改为 `potted plant` / `couch` / `tv` → LLM 答案键缺失 + YOLO 无目标类 → 永不 SEARCH。

## 16 失败分类（Hold 批，修复前）

| 类 | 数 | 含义 |
|----|----|------|
| **B** | **14** | 类别映射/匹配失败（plant×6、tv×4、sofa×4）；`n_detections=0` + `llm_warn` |
| **D** | 1 | `ef36_toilet_3`：有检（3）但无 SEARCH |
| **E** | 1 | `dd4b_toilet_0`：有检；仅 `SEARCH_EXTREME`，无 BEST |
| A/F | 0 | — |

完整表见同目录 `classify_never_search.md`。

## 最小修复（单点）

`adapters/habitat_rangercr10/src/apexnav_real_episode.py`：用 `HM3D_ID_TO_NAME`（或静态回退）将 HM3D 六类映射为 ApexNav 检测/LLM 标签；写入 `target_label.json`（`label_mapped`）。

不改：置信阈值、视野、15° 环视、探索策略、ObjectHold、预算、SR 定义、F0/expand/denoise。

## 代表样本（`reps_labelmap_20261108_213600`）

| ep | 映射后 label | sum_ndet | SEARCH_BEST | 终局 |
|----|--------------|----------|-------------|------|
| yr17_plant_0 | potted plant | 51 | 19 | stop_not_near |
| ef36_tv_3 | tv | 163 | 0 | explore_no_goal（多为近义类簇，无 label=0 目标云） |
| lt9_sofa_4 | couch | 67 | 10 | stop_not_near |

## 同清单 24-ep 对照

| 指标 | Hold | LabelMap |
|------|------|----------|
| 曾产生有效目标候选（sum_ndet>0） | **10/24** | **24/24** |
| 曾进入 SEARCH_BEST | **8/24** | **13/24** |
| 任一类 SEARCH | 9/24 | 16/24 |
| 首次有效检→首次 SEARCH 平均步 | 37.8（n=8） | 39.0（n=15） |
| **SR_proxy** | **4/24** | **5/24** |
| explore_no_goal | 16 | 11 |
| stop_not_near | 4 | 8 |
| 原成功 4 个 | — | **全部保留** |
| 新增成功 | — | **dd4b_plant_5**（原从未 SEARCH） |

证据：`ab24_compare.json`；聚合 `aggregate_ab24_labelmap_20261108_220204.*`。

耗时均值略降（349→330 s）；SEARCH 拍数均值未升高（20.1→16.9）；未见系统性错误目标反复 SEARCH 恶化。

## 结论与下一项

- **主因是处理链路丢掉（B：标签映射），不是「探索从未看到目标」的笼统结论。**
- 映射修复后发现率显著上升；最终成功 +1/24；原成功无回归。
- **下一项最值得处理**：有检测/近义簇但仍不进 SEARCH_BEST，或进 SEARCH 后 `stop_not_near`（如 tv 全为 synonym label≠0；部分 plant/sofa 同型）。属候选置信/目标类索引/接近闭合，**勿再改映射或盲目降阈值**。

SPL：N/A。SR_proxy 定义不变：`planner_stop ∧ dtg≤1.0`。
