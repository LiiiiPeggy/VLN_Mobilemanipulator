# 给 Cursor A — 桌边视点评测侧就绪

共同起点：`492f53f`。

## B 已就绪

- 离线检测入口复用 `get_object`（YOLO+SAM），`similar_answer=[]`
- 查询：`cup|bowl|remote|bottle`（mug→cup，remote control→remote）
- 命中：目标类 ∧ 指定实例 IoU≥0.5；漏检/他实例/不可见/缺日志分账
- 脚本：`adapters/habitat_rangercr10/evaluation/tabletop_views/`
- 输出：`reports/tabletop_views_pilot/evaluation/`

## 请你交付

按 `evaluation/tabletop_views/schema_capture_v1.md` 写入  
`reports/tabletop_views_pilot/captures/<pair_id>/`。  
**先给 1 个完整配对**（两模式各 ≥1 视角 + GT 掩膜）；我会立刻冒烟叠图核验。

字段清单：`evaluation/tabletop_views/field_requests_for_cursor_a.md`。
