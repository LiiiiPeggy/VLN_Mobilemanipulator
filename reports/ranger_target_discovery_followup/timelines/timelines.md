# Target-discovery timelines (formal before)

断点主因：主目标 `label=0` 未进 object map（plant/tv 仅 YOLO COCO 名，DINO 未覆盖主目标同义词）。

## XB4GS9ShBRE_plant_2 (fail_plant_near_goal_aux_only)
- breakpoint: `primary_label0_never_in_object_map`
- label_hist: `{'1': 145, '3': 12}` | nav_mode=0 | first_search_step=None
- first_det_step=0 | min_dtg=0.168 @ step 71 (ndet=0)
- detect path: visible(aux) → detect(green aux) → cloud fuse(label≥1) → **no SEARCH**

## mv2HUxq3B53_plant_3 (fail_plant_aux_only)
- breakpoint: `primary_label0_never_in_object_map`
- label_hist: `{'3': 23, '1': 68}` | nav_mode=0 | first_search_step=None
- first_det_step=0 | min_dtg=10.845 @ step 51 (ndet=1)
- detect path: visible(aux) → detect(green aux) → cloud fuse(label≥1) → **no SEARCH**

## MHPLjHsuG27_tv_monitor_1 (fail_tv_aux_only)
- breakpoint: `primary_label0_never_in_object_map`
- label_hist: `{'3': 300, '2': 141, '1': 8}` | nav_mode=0 | first_search_step=None
- first_det_step=0 | min_dtg=2.083 @ step 87 (ndet=2)
- detect path: visible(aux) → detect(green aux) → cloud fuse(label≥1) → **no SEARCH**

## ziup5kvtCCR_plant_3 (success_plant_control)
- breakpoint: `reached_nav_or_search`
- label_hist: `{'1': 72, '0': 46}` | nav_mode=17 | first_search_step=93
- first_det_step=5 | min_dtg=0.014 @ step 100 (ndet=3)
- detect path: label0 → Navigation → SEARCH @ 93
