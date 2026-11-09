# 24-ep 目标候选标签分类（LabelMap 批）

来源：`ab24_labelmap_20261108_220204` 的 `exploration.log` 簇标签 + `steps.jsonl` ndet + `native_plan_diag`。

| episode | cat | ndet | label0 | 非零簇 | SEARCH_BEST | SEARCH_EXTREME | 类别桶 |
|---------|-----|------|--------|--------|-------------|----------------|--------|
| yr17_plant_0 | plant | 51 | ✓ | ✓ | ✓ | | 有 label=0 |
| yr17_chair_0 | chair | 22 | ✓ | ✓ | ✓ | | 有 label=0 |
| yr17_sofa_0 | sofa | 32 | | ✓ | | | 仅辅助 |
| yr17_tv_0 | tv | 333 | | ✓ | | | 仅辅助 |
| ef36_plant_4 | plant | 68 | | ✓ | | | 仅辅助 |
| ef36_tv_3 | tv | 163 | | ✓ | | | 仅辅助 |
| ef36_bed_4 | bed | 43 | ✓ | | ✓ | | 有 label=0 |
| ef36_toilet_3 | toilet | 7 | | ✓ | | | 仅辅助 |
| hy1_plant_0 | plant | 105 | ✓ | ✓ | | | 有 label=0 但未 SEARCH_BEST |
| hy1_tv_0 | tv | 205 | | ✓ | | | 仅辅助 |
| hy1_chair_3 | chair | 24 | ✓ | ✓ | ✓ | | 有 label=0 |
| hy1_plant_1 | plant | 105 | ✓ | ✓ | | | 有 label=0 但未 SEARCH_BEST |
| lt9_tv_0 | tv | 248 | ✓ | ✓ | | | 有 label=0 但未 SEARCH_BEST |
| lt9_chair_1 | chair | 72 | ✓ | ✓ | ✓ | | 有 label=0 |
| lt9_toilet_2 | toilet | 48 | ✓ | ✓ | ✓ | | 有 label=0 |
| lt9_sofa_4 | sofa | 67 | ✓ | ✓ | ✓ | | 有 label=0 |
| k1cup_sofa_0 | sofa | 12 | ✓ | ✓ | ✓ | | 有 label=0 |
| k1cup_chair_0 | chair | 13 | ✓ | | ✓ | | 有 label=0 |
| k1cup_plant_0 | plant | 69 | | ✓ | | | 仅辅助 |
| k1cup_sofa_1 | sofa | 17 | ✓ | ✓ | ✓ | | 有 label=0 |
| dd4b_chair_5 | chair | 63 | ✓ | ✓ | ✓ | | 有 label=0 |
| dd4b_plant_5 | plant | 44 | ✓ | ✓ | ✓ | | 有 label=0 |
| dd4b_toilet_0 | toilet | 42 | | ✓ | | ✓ | 仅辅助→EXTREME |
| dd4b_bed_1 | bed | 57 | ✓ | ✓ | ✓ | | 有 label=0 |

合计：label=0 出现 16；仅辅助 8；SEARCH_BEST 13（均属 label=0 桶）。
