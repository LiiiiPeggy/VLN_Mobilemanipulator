# Cursor D status — tabletop views pilot

更新：2026-11-18  
分支：`cursor/habitat-rangercr10-scale070` @ `492f53f`（共同起点）

## 已就绪

| 项 | 路径 |
|----|------|
| 类别映射 + 空 similar | `adapters/.../tabletop_views/category_map.py` |
| 生产 `get_object` 离线入口 | `detect_frame.py`（YOLOv7:12184 + SAM:12183；conf=0.3） |
| IoU≥0.5 实例命中 | `match_instance.py`（unit OK） |
| 配对确认 / 四格 / 归因 | `score_pairs.py` |
| 批处理 + 叠图 | `run_pilot.py` / `make_overlays.py` |
| 监听 C 样本 | `watch_captures.py` |
| 锁定配置 | `evaluation/configs/locked_detector_config.json` |
| 布局约定 | `CAPTURE_LAYOUT.md` |

## 已验证

1. **单元**：`test_match_unit.py` — hit / other_instance / miss / invisible。  
2. **生产链连通**：容器内 `detect_frame.py` 调通 `get_object`（k1cup 帧对 `cup` 返回 n_pred=0，与 YOLO 未检出 cup 一致）。  
3. **首个配对样本** `smoke_synth_cup_0`（合成 160×120）：已跑完整 `run_pilot`；对齐 480×640 后仍 **miss_visible**（合成块非真实杯，YOLO 不认）——用于验证「先检测后读 GT」与记账，**不计入真实桌边结论**。  
4. **接线夹具** `fixture_cupA`：`validate_fixture_match.py` → both 确认；叠图在 `overlays/fixture_cupA__*`。

## 等待 C（阻塞完整结论）

- 真实 HM3D/桌边 RGB + **指定实例** GT 掩膜，按 `schema_capture_v1.md` / `CAPTURE_LAYOUT.md` 放入 `captures/`（`manifest_index.json` 或 `pairing_index.json`）。  
- watcher 已在 `vln-rangercr10` 后台轮询（`watch_d.pid`）。  
- **当前无法回答**：哪些类稳定、臂载新增确认、可见性 vs 检测改善、下一阶段优先类——需真实清单，合成图仅验证管线。

## 重跑

见 `adapters/habitat_rangercr10/evaluation/tabletop_views/README.md`。
