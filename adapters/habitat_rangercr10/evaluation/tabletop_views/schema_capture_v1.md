# Capture schema v1 — Cursor A → B（桌边视点配对）

根目录：`reports/tabletop_views_pilot/captures/`

## 目录

```
captures/
  manifest_index.json          # 可选总索引
  <pair_id>/
    manifest.json
    fixed_base_gimbal/
      view_00/
        rgb.png                # 必填；检测器只读此图 + 任务类别
        gt_mask.png|.npy       # 指定实例真值掩膜（与 rgb 同分辨率）
        meta.json              # 见下
      view_01/ ...
      view_02/ ...             # 每模式最多 3 次观察
    arm_ee/
      view_00/ ...
```

## `manifest.json`

```json
{
  "pair_id": "sceneX_cup_inst12",
  "scene": "svBbv1Pavdk",
  "instance_id": "cup_12",
  "category": "cup",
  "category_raw": "mug",
  "notes": "optional"
}
```

`category` 或 `category_raw`：`mug`/`coffee mug`→`cup`，`remote control`→`remote`。  
允许：`cup|bowl|remote|bottle`。

## `view_*/meta.json`

```json
{
  "target_visible": true,
  "observation_index": 0,
  "unique_viewpoint": true,
  "action_rejected": false,
  "timestamp": null,
  "camera_mode": "fixed_base_gimbal",
  "instance_id": "cup_12",
  "rgb_hw": [480, 640]
}
```

- `target_visible`：A 判定该视角目标是否可见；缺省时 B 用 `gt_pixels≥32` 推断。  
- 掩膜必须对应**指定实例**（桌上两杯时不得给错杯）。  
- RGB 与 GT **同分辨率、同坐标系**（像素对齐）。

## `manifest_index.json`（可选）

```json
{"pairs": [{"pair_id": "sceneX_cup_inst12"}]}
```
