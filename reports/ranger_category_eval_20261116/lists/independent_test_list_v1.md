# 独立测试清单 v1（HM3D ObjectNav 六类）

- 目标：每类 20 例，共约 120；实选 **120**。
- 与 dev24 episode 键重合：0；场景重合条目：0 / 120。
- `spawn_status=pending_validation`：合法 spawn 与任务可行性检查独立于算法成绩。
- 不重复同一 `closest_goal_object_id` 凑数；不足则在 `category_notes` 记 shortfall。

| category | selected | target | shortfall | unique_scenes | unique_instances |
|----------|---------:|-------:|----------:|--------------:|-----------------:|
| chair | 20 | 20 | 0 | 20 | 20 |
| bed | 20 | 20 | 0 | 20 | 20 |
| sofa | 20 | 20 | 0 | 20 | 20 |
| plant | 20 | 20 | 0 | 20 | 20 |
| toilet | 20 | 20 | 0 | 20 | 20 |
| tv_monitor | 20 | 20 | 0 | 20 | 20 |

JSON：`adapters/habitat_rangercr10/evaluation/lists/independent_test_list_v1.json`

