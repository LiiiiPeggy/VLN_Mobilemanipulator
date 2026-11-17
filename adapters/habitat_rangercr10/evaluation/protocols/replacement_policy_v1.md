# 替补规则 v1（与算法成绩无关）

原始清单 `independent_test_list_v1.json` **永不删改条目**。有效性表另记 status。

## 何时替补

仅当 status=`invalid` 且原因属于：

- `scene_glb_not_found` / `objectnav_json_missing` / `episode_not_found_in_objectnav`
- `missing_or_zero_view_points` / `missing_goal_position`
- `initial_robot_env_penetration`（整机初始接触；navmesh 可走不算有效）
- 不可恢复的环境异常（EGL/加载崩溃），同一条目重试 1 次后仍失败

**不**因：SR、是否 SEARCH、目标是否好看见、near_goal、预算耗尽。

## 如何替补

1. 在同 `category` 内，从未入选的 ObjectNav 池中选下一候选。  
2. 约束：`(scene, category, closest_goal_object_id)` 不与原清单或已替补重复。  
3. 优先非原清单场景。  
4. 记录 `replaces_id` / `replaced_by_id` 双向链接。  
5. 若无效过多：先报告 valid 数，**不强凑 120**。

当前策略开关：`replacement_policy=none`（先只出有效性表；替补待 valid 比例报告后再启用）。
