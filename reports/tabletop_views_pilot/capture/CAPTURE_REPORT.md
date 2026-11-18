# Tabletop capture final report (Cursor C)

- Baseline SHA pin: `492f53f`
- Branch: `cursor/habitat-rangercr10-scale070`
- Robot: RangerBox-CR10 scale 0.7, gripper fixed, executor `kinematic_collision_v1.2`
- Pairs captured: **12** (reliable GT views: **9**)
- Modes: `fixed_base_gimbal` + `arm_ee` (alias arm_view); 3 views each incl. shared init
- Data root: `/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/tabletop_views_pilot/captures`
- D index: `reports/tabletop_views_pilot/captures/pairing_index.json`

## Coverage

| pair_id | cat | reliable_gt | fg_pixels | arm_pixels | init_mae | notes |
|---------|-----|-------------|-----------|------------|----------|-------|
| `5cdEh9F2hJL_bowl_395` | decorative bowl | True | [5089, 6731, 5089] | [5089, 4457, 0] | 0.0015776909422129393 |  |
| `7MXmsvcQjpJ_bottle_389` | bottle of detergent | True | [9369, 6586, 9369] | [9369, 9369, 9369] | 0.0006401909631676972 |  |
| `7MXmsvcQjpJ_bowl_791` | bowl | True | [6878, 6319, 6878] | [6878, 6878, 6878] | 0.0010069444542750716 |  |
| `CrMo8WxCyVb_cup_423` | coffee mug | True | [4047, 4683, 4047] | [4047, 676, 0] | 0.0003200954815838486 |  |
| `QaLdnwvtxbs_remote_189` | remote control | True | [949, 0, 949] | [949, 704, 0] | 0.00019314236124046147 |  |
| `a8BtkwhxdRV_cup_598` | mug | True | [203, 174, 203] | [203, 250, 63] | 0.002132161520421505 |  |
| `bxsVRursffK_cup_381` | cup | True | [351, 350, 351] | [351, 351, 351] | 0.0009179687476716936 |  |
| `eF36g7L6Z9M_bowl_161` | bowl | True | [3703, 0, 3703] | [3703, 3703, 3703] | 0.0006445312756113708 |  |
| `q5QZSEeHe5g_bottle_9` | bottle | False | [0, 0, 0] | [0, 0, 0] | 0.0006955295102670789 | no_ee_view_with_gt_pixels>=32_after_visibility_ranked_spawn |
| `q5QZSEeHe5g_remote_919` | remote control | False | [0, 0, 0] | [0, 0, 0] | 0.0004177517257630825 | no_ee_view_with_gt_pixels>=32_after_visibility_ranked_spawn |
| `wcojb4TFT35_bottle_706` | bottle of detergent | False | [0, 0, 0] | [0, 0, 0] | 0.00527235260233283 | no_ee_view_with_gt_pixels>=32_after_visibility_ranked_spawn |
| `y9hTuugGdiq_remote_232` | remote control | True | [1633, 0, 1633] | [1633, 907, 0] | 0.0005674913409166038 |  |

## Failed / empty-mask notes

- Observation actions do not aim with GT; empty masks mean target out of view / occluded.
- Pairs with max_gt_pixels=0 marked `reliable_gt=false`.
- Gimbal/arm motion failures recorded without retries.

## Reconstruct

See `README.md` in this folder.

