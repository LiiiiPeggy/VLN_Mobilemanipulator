# 规划链生效参数核实（基线 `492f53f` / legacy018）

## 足迹（0.7×）

来源：`ranger_footprint.py` → `footprint_at_scale(0.7)`

| 量 | 值 |
|----|-----|
| `chassis_half_width_m` | **0.30429** (= 0.4347 × 0.7) |
| `chassis_half_length_m` | 0.4557 |
| `chassis_circumscribed_radius_m` | ≈0.548 |
| 直行建议走廊宽 | ≈0.709 m |

F0 `initial_footprint` 使用上述半长/半宽 + `expand_m=0.3`（仅地图查询豁免，**不**改执行碰撞）。

## 膨胀如何进规划

1. Overlay `apexnav_rangercr10_overlay_legacy018.yaml` 同时写：
   - `/habitat/simulator/agents/main_agent/radius: 0.18`
   - `/sdf_map/obstacles_inflation: 0.18`
2. `SDFMap2D::initMap`（非 real_world）若读到 habitat `radius`，**强制**  
   `obstacles_inflation_ = agent_radius`（覆盖 yaml 里的 inflation）。
3. `clearAndInflateLocalMap`：`inf_step = ceil(inflation / resolution)`。

## 实测默认（algorithm_rangercr10.xml + legacy018）

| 参数 | 生效值 |
|------|--------|
| `sdf_map/resolution` | **0.05 m** |
| `obstacles_inflation`（经 habitat radius） | **0.18 m** |
| `inf_step` | ceil(0.18/0.05) = **4** 格（圆形 inflatePoint） |
| `astar/resolution_astar` | 0.1 m |
| `optimistic` | **false**（UNKNOWN 在占用与 ESDF 中当障碍） |

## 关键结论

- 规划硬膨胀 **0.18 m ≪ 半宽 0.304 m** → 路径可合法贴到墙/家具，执行层整机碰撞才拒绝或擦边。
- Habitat `agent_radius` **会覆盖** `sdf_map/obstacles_inflation`；须加锁或把 inflation 与半径解耦后才能单独控规划膨胀。
- ESDF（`getDistance`）从 **`occupancy_buffer_inflate_`** 起算；`optimistic=false` 时 UNKNOWN 也参与距离 → 软代价若直接用该场会压制 frontier。P2 应对**已观测 inflate/OCC** 单独取距离。

## 执行侧（不变）

- 机器人几何 / spawn / `kinematic_collision_v1.2` 碰撞门控保持；本轮只改规划膨胀与边代价。
