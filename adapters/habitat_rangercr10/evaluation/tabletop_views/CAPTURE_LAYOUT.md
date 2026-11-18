# Cursor C → D 捕获布局（tabletop views pilot）

D 只读本布局；检测器**推理完成前不读** GT 掩膜。

## 根目录

`reports/tabletop_views_pilot/captures/`

## 索引（任一存在即可）

- `pairing_index.json` — 推荐
- 或 `pairing_index.jsonl` — 每行一个 pair

```json
{
  "protocol": "tabletop_views_pilot_v1",
  "camera_modes": ["fixed_base_gimbal", "arm_ee"],
  "max_views_per_mode": 3,
  "pairs": [
    {
      "pair_id": "sceneX_table0_cupA",
      "instance_id": "cup_01",
      "category": "mug",
      "scene": "hm3d-...",
      "reliable_gt": true,
      "notes": ""
    }
  ]
}
```

`category` 可用场景别名（`mug` / `coffee mug` / `remote control`）；D 映射到 `cup|bowl|remote|bottle`。

## 每个 pair 目录

```
captures/<pair_id>/
  meta.json                    # 可选；覆盖 index 字段
  fixed_base_gimbal/
    view_00/
      rgb.png                  # 必填（或 rgb.jpg）
      gt_mask.png              # 指定实例真值掩膜（png/npy）；可靠评测必填
      view_meta.json           # 可选
    view_01/ ...
    view_02/ ...
  arm_ee/
    view_00/ ...
```

### `view_meta.json`（可选字段）

| 字段 | 含义 |
|------|------|
| `gt_visible` | bool；缺省用 GT 像素数 ≥ 32 推断 |

**分辨率**：生产 `get_object` / MobileSAM 掩膜按 **480×640 (H×W)**。D 会在推理前把 RGB（及 GT）最近邻/双线性对齐到该尺寸；C 侧尽量直接导出 Habitat 分辨率。
| `action_rejected` | bool / int；该次观察动作被拒 |
| `viewpoint_id` | 有效视角标识（去重用） |
| `t_start` / `t_end` | ISO 或 epoch；有可靠时间戳才汇总耗时 |
| `instance_id` / `category` | 可覆盖 pair 级 |

## D 产物

`reports/tabletop_views_pilot/evaluation/`

- `configs/locked_detector_config.json`
- `tables/frames.jsonl` — 逐帧
- `tables/instances.jsonl` — 逐实例配对
- `tables/summary.json` + `summary.md`
- `overlays/` — 人工核验叠图
