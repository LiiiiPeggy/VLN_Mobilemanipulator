# Tabletop views pilot — fixed_base_gimbal vs arm_ee

共同起点：`492f53f`。离线复用 ApexNav 生产 `get_object()`（YOLOv7:12184 + MobileSAM:12183）。

- 查询锁定：`cup|bowl|remote|bottle`（`mug`→`cup`，`remote control`→`remote`）
- `similar_answer=[]`（不用六类家具 LLM 表）
- 命中：目标类 ∧ 与**指定实例** GT IoU ≥ 0.5
- 实例确认：该相机模式 ≤3 次观察中 ≥1 次命中 →「桌边目标确认率」

## 采集布局

见 [`CAPTURE_LAYOUT.md`](CAPTURE_LAYOUT.md)（A 交付）。字段：[`field_requests_for_cursor_a.md`](field_requests_for_cursor_a.md)。

## 重跑

```bash
# YOLO+SAM
bash adapters/habitat_rangercr10/evaluation/tabletop_views/ensure_vlm_yolo_sam.sh

# 全量（必须在容器内，才能连 localhost VLM）
docker exec vln-rangercr10 bash -lc '
  source /opt/ros/noetic/setup.bash
  source /workspace/ApexNav/devel/setup.bash
  cd /workspace/ApexNav
  export PYTHONPATH=/workspace/ApexNav:/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/evaluation/tabletop_views:${PYTHONPATH}
  python3 /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/evaluation/tabletop_views/run_pilot.py
'

# 等待 A 首个真实配对并立即冒烟（跳过 fixture_/smoke_synth_）
python3 adapters/habitat_rangercr10/evaluation/tabletop_views/watch_captures.py
```

## 产物

`reports/tabletop_views_pilot/evaluation/`：`tables/frames|instances|summary`、`overlays/`、`configs/locked_detector_config.json`。

## 单测

```bash
python3 adapters/habitat_rangercr10/evaluation/tabletop_views/test_match_unit.py
```
