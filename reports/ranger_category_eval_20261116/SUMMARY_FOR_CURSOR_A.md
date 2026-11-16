# 给 Cursor A 的结果摘要（可并入 MEMORY/PROGRESS）

- 分支工作：新增 `adapters/habitat_rangercr10/evaluation/` + `reports/ranger_category_eval_20261116/`。
- 历史 24 例（LabelMap+VIEW_POINTS）：micro SR_proxy **8/24=0.333**；最差 **tv_monitor 0/4（全 no_SEARCH_BEST）**、**plant 1/6**；chair/bed 相对好。诊断 only，可能穿模，0.7×。
- 独立清单 v1：**120** ep（六类×20，实例/场景不重复凑数）；与 dev24 episode/场景重合 **0**；spawn 待验证。
- 杯子等小目标：**语义有、ObjectNav 目标无** → 未进 120 清单；需单独数据建设。
- ApexNav 基线 A / 臂 B·C：**协议已写**；跑数等你冻结执行与日志字段。
- 请你接入字段：`field_requests_for_cursor_a.md`；公共记忆文件请你汇总。
