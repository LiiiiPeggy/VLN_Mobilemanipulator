# 独立清单有效性表 v1

- code_git_sha: `bb898421b12bef2bbda2295a0e0e50e8f1e875f0`
- n_checked: **120** / 120
- counts: `{'valid': 109, 'invalid': 11}`
- elapsed_sec: 6566.108300447464
- 原始清单未删条目；本表仅标注 valid/invalid。
- **未**按 SR/SEARCH/可见性筛选。

## 逐类

| category | valid | invalid | pending |
|----------|------:|--------:|--------:|
| bed | 19 | 1 | 0 |
| chair | 13 | 7 | 0 |
| plant | 19 | 1 | 0 |
| sofa | 19 | 1 | 0 |
| toilet | 19 | 1 | 0 |
| tv_monitor | 20 | 0 | 0 |

## 无效原因（可重复计）

```
{'initial_robot_env_penetration': 10, 'adapted_start_not_ok_flag': 2, 'exception:AssertionError:': 1}
```

## 逐例

| id | cat | status | reasons | spawn_source | init_pen |
|----|-----|--------|---------|--------------|----------|
| svBbv1Pavdk_chair_0 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| svBbv1Pavdk_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| svBbv1Pavdk_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| svBbv1Pavdk_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| svBbv1Pavdk_tv_monitor_0 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| cvZr5TUy5C5_chair_1 | chair | invalid | initial_robot_env_penetration | find_adapted_start | True |
| cvZr5TUy5C5_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| cvZr5TUy5C5_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| cvZr5TUy5C5_plant_4 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| cvZr5TUy5C5_toilet_2 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| cvZr5TUy5C5_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| ziup5kvtCCR_chair_0 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| ziup5kvtCCR_bed_1 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| ziup5kvtCCR_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| ziup5kvtCCR_plant_3 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| ziup5kvtCCR_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| ziup5kvtCCR_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| VBzV5z6i1WS_chair_1 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| VBzV5z6i1WS_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| q3zU7Yy5E5s_chair_0 | chair | invalid | initial_robot_env_penetration | find_adapted_start | True |
| q3zU7Yy5E5s_sofa_0 | sofa | invalid | adapted_start_not_ok_flag;initial_robot_env_penetration | find_adapted_start | True |
| q3zU7Yy5E5s_toilet_1 | toilet | invalid | adapted_start_not_ok_flag;initial_robot_env_penetration | find_adapted_start | True |
| wcojb4TFT35_chair_2 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| wcojb4TFT35_bed_1 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| wcojb4TFT35_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| wcojb4TFT35_toilet_4 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| wcojb4TFT35_tv_monitor_0 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| DYehNKdT76V_chair_0 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| DYehNKdT76V_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| DYehNKdT76V_plant_1 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| DYehNKdT76V_toilet_2 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| Nfvxx8J5NCo_chair_3 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| Nfvxx8J5NCo_bed_1 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| Nfvxx8J5NCo_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| Nfvxx8J5NCo_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| h1zeeAwLh9Z_chair_2 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| h1zeeAwLh9Z_bed_1 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| h1zeeAwLh9Z_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| h1zeeAwLh9Z_plant_3 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| h1zeeAwLh9Z_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 5cdEh9F2hJL_chair_1 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 5cdEh9F2hJL_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 5cdEh9F2hJL_sofa_1 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 5cdEh9F2hJL_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 5cdEh9F2hJL_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 5cdEh9F2hJL_tv_monitor_0 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bxsVRursffK_chair_0 | chair | invalid | initial_robot_env_penetration | find_adapted_start | True |
| bxsVRursffK_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bxsVRursffK_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bxsVRursffK_plant_1 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bxsVRursffK_toilet_4 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| a8BtkwhxdRV_chair_1 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| a8BtkwhxdRV_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| a8BtkwhxdRV_toilet_3 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| a8BtkwhxdRV_tv_monitor_2 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| p53SfW6mjZe_chair_0 | chair | invalid | initial_robot_env_penetration | find_adapted_start | True |
| p53SfW6mjZe_bed_4 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| p53SfW6mjZe_sofa_4 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| p53SfW6mjZe_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| p53SfW6mjZe_tv_monitor_0 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| mv2HUxq3B53_chair_3 | chair | invalid | initial_robot_env_penetration | find_adapted_start | True |
| mv2HUxq3B53_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| mv2HUxq3B53_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| mv2HUxq3B53_plant_3 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| mv2HUxq3B53_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| mv2HUxq3B53_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| BAbdmeyTvMZ_chair_1 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| BAbdmeyTvMZ_bed_5 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| BAbdmeyTvMZ_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| BAbdmeyTvMZ_toilet_3 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| BAbdmeyTvMZ_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| TEEsavR23oF_chair_4 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| TEEsavR23oF_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| TEEsavR23oF_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| TEEsavR23oF_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| TEEsavR23oF_toilet_2 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| TEEsavR23oF_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bCPU9suPUw9_chair_2 | chair | invalid | initial_robot_env_penetration | find_adapted_start | True |
| bCPU9suPUw9_bed_2 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bCPU9suPUw9_sofa_1 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bCPU9suPUw9_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| bCPU9suPUw9_toilet_1 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 6s7QHgap2fW_chair_0 | chair | invalid | initial_robot_env_penetration | find_adapted_start | True |
| 6s7QHgap2fW_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 6s7QHgap2fW_plant_1 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 6s7QHgap2fW_tv_monitor_0 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| QaLdnwvtxbs_chair_0 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| QaLdnwvtxbs_bed_1 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| QaLdnwvtxbs_sofa_1 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| QaLdnwvtxbs_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| QaLdnwvtxbs_tv_monitor_4 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| zt1RVoi7PcG_chair_0 | chair | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| zt1RVoi7PcG_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| zt1RVoi7PcG_plant_1 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| zt1RVoi7PcG_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| GLAQ4DNUx5U_bed_2 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| GLAQ4DNUx5U_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| GLAQ4DNUx5U_tv_monitor_3 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| y9hTuugGdiq_bed_3 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| y9hTuugGdiq_sofa_0 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| y9hTuugGdiq_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| y9hTuugGdiq_toilet_2 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| y9hTuugGdiq_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| CrMo8WxCyVb_bed_1 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| CrMo8WxCyVb_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| CrMo8WxCyVb_toilet_0 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 4ok3usBNeis_bed_2 | bed | invalid | initial_robot_env_penetration | find_adapted_start | True |
| 4ok3usBNeis_sofa_3 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 4ok3usBNeis_tv_monitor_0 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| q5QZSEeHe5g_bed_0 | bed | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| q5QZSEeHe5g_sofa_2 | sofa | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| q5QZSEeHe5g_plant_0 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| q5QZSEeHe5g_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| XB4GS9ShBRE_plant_2 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| 7MXmsvcQjpJ_plant_2 | plant | invalid | exception:AssertionError: | None | None |
| mL8ThkuaVTM_plant_1 | plant | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| mL8ThkuaVTM_toilet_3 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| qyAac8rV8Zk_toilet_1 | toilet | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| qyAac8rV8Zk_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
| MHPLjHsuG27_tv_monitor_1 | tv_monitor | valid | ok_scene_goal_spawn_camera_no_init_pen | find_adapted_start | False |
