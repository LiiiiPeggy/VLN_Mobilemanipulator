# Ranger target-discovery followup

## Scope
Improve 6-class ObjectNav SR on Ranger (`fixed_base_gimbal`, robot_scale=0.7, 150/100) by fixing the most common break among formal **84 spawn-ok → 36 ebe → 34 no SEARCH_BEST**.

## Cohort breakpoint (34)

| bucket | n | meaning |
|---|---:|---|
| A_no_label0 | 25 | primary never enters object map |
| B_label0_no_cluster | 1 | label0 seen, no new cluster |
| C_cluster_no_nav | 8 | cluster but no Navigation Mode |

**Most common fixable break:** A — detector primary path. Evidence: plants 8/8 A; near-goal XB4 flower shows green aux-only boxes; plant `llm_answer` is all-COCO so GroundingDINO never runs on the primary.

## Timeline cases
See `timelines/timelines.md` and `keyframes/`.

Fail path: visible → detect(aux green) → cloud fuse(label≥1) → **block: no label=0** → never SEARCH_BEST.

Success control ziup: red `potted plant` label=0 → Navigation → SEARCH_BEST → STOP.

## Minimal fix
1. `adapters/habitat_rangercr10/src/apexnav_real_episode.py`: `detect_label` expands plant → `potted plant|plant|flower|vase`, tv_monitor → `tv|television|monitor|screen` (llm/ITM key unchanged).
2. `baselines/ApexNav/vlm/utils/get_object_utils.py`: fuzzy phrase match so DINO near-matches count as primary.

## Paired before/after (@150/100, formal spawns)
Batch `paired_after_dinofix_v2_20261118_221046`. Details: `paired/paired_compare.md`.

| id | before label0 | after label0 | before SEARCH_BEST | after SEARCH_BEST | before sr | after sr |
|---|---:|---:|:---:|:---:|:---:|:---:|
| XB4GS9ShBRE_plant_2 | 0 | 83 | False | False | False | False |
| mv2HUxq3B53_plant_3 | 0 | 20 | False | True | False | False |
| MHPLjHsuG27_tv_monitor_1 | 0 | 4 | False | False | False | False |
| ziup5kvtCCR_plant_3 (control) | 46 | 150 | True | True | True | True |

- more primary label0: **4/4**
- newly gained SEARCH_BEST: **1/3** fail cases (mv2)
- XB4: label0↑ but plan only reaches `SEARCH_OVER_DEPTH_OBJECT` (not BEST)
- success control preserved

## One-line answer
**修「主目标检测→label=0 入 object map」；Ranger 能找到更多主目标（4/4 配对例 label0↑，1 例新进 SEARCH_BEST），但近距花盆仍常卡在 over-depth，SR 尚未系统性抬升。**

## Artifacts
- `formal_ebe_no_best_cohort.json`, `cohort_detection_presence.json`, `cohort_label0_vs_aux.json`
- `timelines/`, `keyframes/`, `lists/paired_focus.json`
- `paired/before_formal_metrics.json`, `paired/paired_compare.json`, `paired/paired_compare.md`
- code: detect_label + `_matches_label`（`################################` 标记）
- `dev24_regress/` — full dev24@150/100 after fix（见该目录 log）

## Dev24 regress status
- Batch `dev24_after_dinofix_20261119_011332` **running** (pid in `dev24_regress/dev24_pid.txt`).
- Historical short50 diag SR_proxy was 0.333 (see `reports/ranger_category_eval_20261116/tables/dev24_by_category.md`); this run is protocol 150/100 after fix.
