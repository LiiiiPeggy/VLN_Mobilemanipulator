# Tabletop views pilot — evaluation outputs

冻结共同起点：`492f53f` @ `cursor/habitat-rangercr10-scale070`。

| 路径 | 内容 |
|------|------|
| `tables/frames.*` | 逐帧检测 + IoU 桶 |
| `tables/instances.jsonl` | 逐实例配对确认 |
| `tables/summary.*` | 分类「桌边目标确认率」+ 四格 |
| `overlays/` | 人工核验叠图 |
| `configs/run_config.json` | 实际查询词 / 阈值 / similar=[] |

采集输入：`../captures/`（schema：`evaluation/tabletop_views/schema_capture_v1.md`）。

当前状态：检测与计分入口已就绪；等待 A 首个完整配对后冒烟，再跑全清单。
