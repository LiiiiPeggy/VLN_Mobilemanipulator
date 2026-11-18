# 给 Cursor A — 桌边视点配对采集字段（一次性）

评测侧（B）只读 RGB 做检测，**推理结束后**才读你的 GT 掩膜做 IoU。

## 必须交付

| 项 | 说明 |
|----|------|
| 目录布局 | 见 `schema_capture_v1.md` |
| 每模式 ≤3 次观察 | `view_00..02`，含 `rgb.png` + **指定实例** `gt_mask` |
| `manifest.json` | `pair_id` / `instance_id` / `category`（或 raw 别名） |
| 配对完整性 | 同一 `instance_id` 在 `fixed_base_gimbal` 与 `arm_ee` 都有条目（不可见也保留，标 `target_visible=false` + 空/近空掩膜） |

## 建议写入 meta

`target_visible`、`unique_viewpoint`、`action_rejected`、`timestamp`（有则报耗时）、`rgb_hw`。

## 不要

- 不要按检测结果筛样本。  
- 不要把 LLM 六类家具答案塞进小物体标签。  
- 不要改 B 的 `evaluation/tabletop_views/` 计分阈值。

## 首样本

请先落 **1 个完整配对**（两模式各 ≥1 视角）到  
`reports/tabletop_views_pilot/captures/<pair_id>/`；B 的 `watch_first_pair.sh` 会立即冒烟。
