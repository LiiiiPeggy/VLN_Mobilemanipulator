# Ranger 分类评测（固定相机 vs 机械臂主动观察）

独立于 baseline 核心执行链。**不**修改 `kinematic_demo.py` / `apexnav_real_episode.py` / 传感器发布。

| 路径 | 用途 |
|------|------|
| `lists/` | 开发回归集引用 + 独立测试清单 |
| `protocols/` | 评测协议、对照设计、给 Cursor A 的日志字段需求 |
| `scripts/` | 诊断 / 清单构建 / 分类统计（只读历史 JSON + ObjectNav 数据） |
| `schemas/` | 结果行 JSON schema（期望字段） |

报告产物：`reports/ranger_category_eval_20261116/`。

## 边界

- 当前 **0.7×** 代理机：不得称为真实尺寸实机成绩。
- 臂仅主动观察；夹爪固定；不抓取、不开柜。
- 主比较：同平台部署成绩；论文数字仅背景。
- 本轮优先 ApexNav；六套大规模不同时铺开。
- 公共 `MEMORY` / `PROGRESS` / `PROCESS` 由 Cursor A 汇总；本目录提供结果摘要。

## 两层对照

1. **算法部署对照**：同 Ranger 与执行规则；各算法保留自身相机能力（披露差异）。
2. **机械臂收益对照（ApexNav）**：A 固定位姿云台 → B 规则臂观察 → C 主动观察（后两者协议先冻结，实现跟 A）。
