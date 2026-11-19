# Paired before/after — primary DINO synonym fix

After batch: `paired_after_dinofix_v2_20261118_221046` @150/100 fixed_base_gimbal robot_scale=0.7

Fix: `detect_label` expands plant/tv with non-COCO synonyms + fuzzy phrase match in `get_object`.

| id | before label0 | after label0 | before SEARCH_BEST | after SEARCH_BEST | before sr | after sr | notes |
|---|---:|---:|:---:|:---:|:---:|:---:|---|
| XB4GS9ShBRE_plant_2 | 0 | 83 | False | False | False | False | over_depth,more_primary |
| mv2HUxq3B53_plant_3 | 0 | 20 | False | True | False | False | more_primary,gained_SEARCH_BEST |
| MHPLjHsuG27_tv_monitor_1 | 0 | 4 | False | False | False | False | more_primary |
| ziup5kvtCCR_plant_3 | 46 | 150 | True | True | True | True | more_primary,success_control |

## Verdict on discovery
- Cases with more primary label0: 4/4
- Cases newly entering SEARCH_BEST: 1/3 fail-cohort (excl. control check)
