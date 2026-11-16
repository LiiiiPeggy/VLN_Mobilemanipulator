# Ranger 分类评测体系（2026-11-16）

仓库：`VLN_Mobilemanipulator` @ `cursor/habitat-rangercr10-scale070`（起始核对 `d2f3200`）。  
评测代码：`adapters/habitat_rangercr10/evaluation/`。  
**未**修改 Cursor A 负责的核心执行文件；**未**改公共 `MEMORY`/`PROGRESS`/`PROCESS`（交 A 汇总）。

## 结论（优先回答）

1. **哪些类别或观测条件限制成功？**（基于历史 24 例诊断，穿模风险未排除）  
   - **tv_monitor**：4/4 失败且全部 `no_SEARCH_BEST`（多数甚至无 label=0）→ 主瓶颈在**目标确认/检测簇**，不是到点距离。  
   - **plant**：6 例仅 1 成功；4 例未进 SEARCH_BEST（含有 label=0 仍不 BEST）→ 确认策略与观察质量问题突出。  
   - **toilet / sofa**：混有错误停止与未确认；sofa 2/4 为 `wrong_stop`（错误物体/实例）。  
   - **chair / bed**：相对最好（4/5、2/2），样本仍极小。  
   - 观测条件（高度/遮挡/尺度/多实例）**尚未在历史日志中系统标注** → 条件层结论证据不足。

2. **改变机械臂视点有望解决哪类具体失败？**  
   - **有望（假设，待 A/B 配对验证）**：`no_SEARCH_BEST` 且疑似固定相机俯仰/高度导致目标在帧内过小、过偏或被家具遮挡的 plant / tv / 部分 toilet——即「看不清 / 确认不了」而非「停错点」。  
   - **不太像单靠抬臂能解决**：已 SEARCH_BEST 仍 `wrong_stop` 的错误物体/实例（sofa/chair 等）——更偏检测/语义消歧与 STOP 决策。  
   - **不能**把动臂本身设为成功条件；需 A vs B 同清单配对。

3. **现有证据是否足够支持这一判断？**  
   - **不够作为部署结论**：n=24、每类 2–6、0.7×、历史链可能穿模、无观测条件标注、无冻结 `camera_mode` 日志。  
   - **足够启动协议**：失败形态已可分轨；独立 120 清单与统计脚本已就绪；等 A 冻结执行后再跑 ApexNav 基线 A。

## 交付物

| 项 | 路径 |
|----|------|
| 历史 24 例逐类诊断 | `tables/dev24_by_category.md`，`dev24_per_episode.csv`，`dev24_category_diag.json` |
| 指标汇总（micro/macro/Wilson） | `tables/dev24_metrics_summary.json` |
| 独立测试清单 ~120 | `lists/independent_test_list_v1.md`（实选 120；与 dev24 episode/场景键重合 **0**） |
| 小目标可行性 | `tables/small_object_feasibility.md`（cup **非** ObjectNav 任务） |
| 协议 | `../adapters/habitat_rangercr10/evaluation/protocols/` |
| ApexNav 新部署基线结果 | `tables/apexnav_baseline_A/`（**待 A 冻结后填写**） |

## 数据审计摘要

- HM3D ObjectNav v2 val：六类 goals + view_points 充足；本清单每类 20 景 20 实例，无 shortfall。  
- cup/mug：少数场景有语义网格，但**无** ObjectNav goals/view_points → **NOT_TASK_READY**；禁止只加类别字符串。  
- Spawn：清单中 `pending_validation`；可行性门禁与算法分分开记账。

## 下一步（等 A）

1. A 交付运动测试通过的 commit、`camera_mode`、日志字段（见 `field_requests_for_cursor_a.md`）。  
2. 固定版本后先少样本核对统计。  
3. 再跑 `independent_test_list_v1` 得 ApexNav 基线 A；再谈 B/C。  
4. GPU/ROS 与 A 排队，不抢占。
