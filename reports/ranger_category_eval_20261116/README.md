# Ranger 分类评测（接 bb89842）

评测：`adapters/habitat_rangercr10/evaluation/` · 报告目录：本目录  
执行基线：**bb89842**（`kinematic_collision_v1.1` + `fixed_base_gimbal`）  
评测提交：`464b962` / `de39709`（及后续 formal launcher 修复）

## 结论（优先）

1. **短预算 50 步（合并 recovery）**：SR_proxy **0/24**；失败主因是 **budget_exhausted**，不是历史 LabelMap 的 tv/plant 分布。  
2. **near_goal=5**：其中 **4 例 moved_m=0** → 禁止说「成功接近未停」；仅 1 例有平移且 SEARCH_BEST，仍无 STOP。  
3. **120 清单有效性**：**109 valid / 11 invalid**（不强凑）。无效主因：整机初始穿透 10 + adapted_start 失败/断言。  
4. 观测分层仍 **unknown**；杯子/主动臂 **未做**。  
5. 正式 **150/100** 在 smoke/全量 valid 上运行中或待接续；结果进 `formal_fixed_gimbal_v1/`。

## 归档与表

| 产物 | 路径 |
|------|------|
| 旧 8/24 归档 | `archives/00_hist_labelmap_vp_8of24.json` |
| short50 归档 | `archives/01_short50_exec_gimbal.json` |
| near_goal 表 | `tables/near_goal_5_detail.md` |
| short50 记账 | `tables/short50_accounting.json` |
| 有效性表 | `lists/independent_list_validity_v1.md` |
| valid-only | `lists/independent_valid_only_v1.json`（n=109） |
| 冻结协议 | `../adapters/.../protocols/freeze_protocol_v1.md` |
| 给 A 字段 | `../adapters/.../protocols/field_requests_for_cursor_a.md` |

## 正式跑

```bash
# smoke
SMOKE_N=2 MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 \
  bash adapters/habitat_rangercr10/evaluation/scripts/run_formal_independent_eval.sh

# full valid (host + docker)
SMOKE_N=0 MAX_STEPS=150 MAX_EXPLORE_ACTIONS=100 \
  bash adapters/habitat_rangercr10/evaluation/scripts/run_formal_independent_eval.sh
```
