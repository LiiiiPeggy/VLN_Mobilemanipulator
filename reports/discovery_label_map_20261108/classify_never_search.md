# 16 个从未 SEARCH_BEST 分类（Hold 批 `ab24_hold_20261107_231416`）

证据来源：`target_label.json`、`steps.jsonl`（`n_detections`）、`native_plan_diag.jsonl`、`llm_warn.txt`。  
人工视频未注入在线策略；本表仅离线诊断。

## 目标发现链路（生产代码）

| 阶段 | 函数 / 位点 | 筛选条件 |
|------|-------------|----------|
| RGB 观测 | `apexnav_real_episode` 步循环 `env.observe_ee_only` | EE RGB |
| 类别映射 | `apexnav_real_episode` label 初始化 | HM3D `object_category` → 检测/LLM 标签 |
| 检测/匹配 | `vlm.utils.get_object_utils.get_object` | COCO→YOLO；非 COCO→DINO；phrase∈`right_label`/`llm_answer` |
| 深度→目标点云 | mask + depth → `/detector/clouds_with_scores` | 有效深度像素；SAM mask |
| 候选维护 | ApexNav `exploration_manager` 目标云融合/置信 | 置信与生命周期 |
| 接近点/可达 | `planNextBestPoint` / object path | 可达接近点 |
| SEARCH | `SEARCH_BEST_OBJECT`（及 OVER_DEPTH / EXTREME） | 有有效目标云且路径 OK |

区分：检测未跑 / 检测无结果（`n_detections=0`）/ 结果被后续过滤（有 `n_detections` 但无 `SEARCH_BEST`）。

## 分类表

| episode | cat | label(旧) | sum_ndet | n_pos | plan | 类 | 依据 |
|---------|-----|-----------|----------|-------|------|----|------|
| yr17_plant_0 | plant | plant | 0 | 0 | EXPL only | **B** | 未映射；llm_warn；YOLO 不认 plant |
| yr17_sofa_0 | sofa | sofa | 0 | 0 | EXPL only | **B** | 同上（sofa∉COCO，键应为 couch） |
| yr17_tv_0 | tv_monitor | tv_monitor | 0 | 0 | EXPL only | **B** | 同上（应为 tv） |
| ef36_plant_4 | plant | plant | 0 | 0 | EXPL only | **B** | 同上 |
| ef36_tv_3 | tv_monitor | tv_monitor | 0 | 0 | EXPL only | **B** | 同上 |
| ef36_toilet_3 | toilet | toilet | 3 | 3 | EXPL only | **D** | 标签正确；有检无 SEARCH |
| hy1_plant_0 | plant | plant | 0 | 0 | EXPL only | **B** | 映射失败 |
| hy1_tv_0 | tv_monitor | tv_monitor | 0 | 0 | EXPL only | **B** | 映射失败 |
| hy1_plant_1 | plant | plant | 0 | 0 | EXPL only | **B** | 映射失败 |
| lt9_tv_0 | tv_monitor | tv_monitor | 0 | 0 | EXPL only | **B** | 映射失败 |
| lt9_sofa_4 | sofa | sofa | 0 | 0 | EXPL only | **B** | 映射失败 |
| k1cup_sofa_0 | sofa | sofa | 0 | 0 | EXPL only | **B** | 映射失败 |
| k1cup_plant_0 | plant | plant | 0 | 0 | EXPL only | **B** | 映射失败 |
| k1cup_sofa_1 | sofa | sofa | 0 | 0 | EXPL only | **B** | 映射失败 |
| dd4b_plant_5 | plant | plant | 0 | 0 | EXPL only | **B** | 映射失败 |
| dd4b_toilet_0 | toilet | toilet | 42 | 25 | EXTREME×12 | **E** | 有检；仅 SEARCH_EXTREME，未 BEST |

**计数**：B=14，D=1，E=1，A=0，F=0。

对照：同批 chair/bed/toilet（标签碰巧等于 COCO/答案键）可产生检测并进入 SEARCH；plant/sofa/tv_monitor 全批 `n_detections=0`。

## 主阻断

- **环节**：类别映射（RGB→检测前）。
- **函数**：`apexnav_real_episode.py` 中失效的 `from vlm.Labels import category_to_coco, id_to_name`（`Labels.py` 无此符号，ImportError 被吞）。
- **触发**：`object_category ∈ {plant, sofa, tv_monitor}` → 检测标签错误 → `read_answer` 键缺失 → `get_object` 无法命中 COCO YOLO 类 → 全剧 `n_detections=0` → 永不 SEARCH。
