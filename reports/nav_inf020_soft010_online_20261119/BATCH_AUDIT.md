# Batch audit — `navinf020_20261119_210100` (refined)

| tag | verdict | intended | actual | infl | inf_step | soft | lock | n_steps | planned | pair_usable |
|-----|---------|----------|--------|------|----------|------|------|---------|---------|-------------|
| sofa_legacy018 | **0步或握手失败** | legacy018 | legacy018 | 0.18 | 4 | off | False | 0 | False | False |
| sofa_inf020 | **有效** | inf020_soft010 | inf020_soft010 | 0.2 | 4 | R=0.1/w=2.0 | True | 126 | True | True |
| toilet_legacy018 | **有效** | legacy018 | legacy018 | 0.18 | 4 | off | False | 82 | True | True |
| toilet_inf020 | **配置串线** | inf020_soft010 | legacy018 | 0.18 | 4 | off | False | 82 | True | False |
| dd4b_legacy018 | **有效** | legacy018 | legacy018 | 0.18 | 4 | off | False | 126 | True | True |
| dd4b_inf020 | **配置串线** | inf020_soft010 | legacy018 | 0.18 | 4 | off | False | 126 | True | False |

## 结论

- 可复用 inf 臂：`sofa_inf020`（有效，配置正确）。
- 需重跑：`sofa_legacy018`（0步/节点 abort）。
- 作废（配置串线）：`toilet_inf020`、`dd4b_inf020`（intended inf020，actual legacy018）。
- 单臂有效但无配对：`toilet_legacy018`、`dd4b_legacy018`（actual=legacy，不可与串线 inf 对比）。

