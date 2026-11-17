# Ranger 分类评测（接 bb89842 执行基线）

评测代码：`adapters/habitat_rangercr10/evaluation/`  
执行基线 SHA：**bb89842**（`kinematic_collision_v1.1` + `fixed_base_gimbal`）  
**未**修改 A 核心执行文件 / 公共 MEMORY。

## 结论（当前证据）

1. **历史 8/24** 仅归档诊断；**不能**用其 tv/plant 分布解释新协议失败。  
2. **短预算 50 步批（合并 recovery）**：micro SR_proxy **0/24**；主失败为 **budget_exhausted (22)** + wrong_stop (2)；初始穿透 4。  
3. **near_goal=5**：其中 **4 例 moved_m=0** → 是「出生点已近」或静止近目标，**不是**「成功接近未停」。仅 `dd4b_plant_5` 有平移(1.6 m)且进过 SEARCH_BEST，仍无 STOP。  
4. **120 清单有效性**：冒烟 2 例 → 1 valid / 1 invalid(初始穿透)；全量检查进行中（按场景复用 env）。不强凑 120。  
5. 观测高度/遮挡/歧义：**unknown**（无标注证据）。杯子任务 / 主动臂策略：**本轮不做**。

## 归档

| ID | 路径 | 说明 |
|----|------|------|
| hist 8/24 | `archives/00_hist_labelmap_vp_8of24.json` | 旧协议诊断 |
| short50 | `archives/01_short50_exec_gimbal.json` | 新执行器短预算 + recovery 合并 |
| near_goal 表 | `tables/near_goal_5_detail.md` | 分列解释 |
| 短预算记账 | `tables/short50_accounting.json` | spawn/run/fail 分账 |

## 冻结与字段

- `protocols/freeze_protocol_v1.md`（建议正式预算 150/100）  
- `protocols/field_requests_for_cursor_a.md`（一次性：git_sha、max_steps 等写入 run 产物）  
- `protocols/replacement_policy_v1.md`

## 正式评测状态

| 步骤 | 状态 |
|------|------|
| 日志接入与统计修正 | **done** |
| 120 有效性表 | **running / partial** → `lists/independent_list_validity_v1.json` |
| 接口冒烟（valid 子集） | 待有效性表 |
| 正式 150/100 全有效清单 | 待有效性 + 与 A 确认预算字段落盘 |

SPL=N/A；SR_proxy 与 near_goal 分列。
