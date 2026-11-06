# 同帧 local_update 合并修复

日期：2026-11-06  
基线：`5953120`  
范围：仅 `inputFreeRayCloud2D` 对 `local_update_*` 的写回策略；不改环视/膨胀半径/unknown/A*。

## 缺陷

同帧顺序：`inputDepthCloud2D` → `inputFreeRayCloud2D` → `clearAndInflateLocalMap()`。  
后者只用 `md_->local_update_min/max_`。旧实现在 free-ray 末尾**赋值覆盖**该 AABB，障碍若落在地面更新盒外，本帧局部膨胀会漏掉这些 OCCUPIED（相对全图重建少膨胀格）。

帧间：`MapROS` 在 inflate 后将 `local_updated_=false`；下一帧首个写入者应赋值，不应继承上帧盒。

## 修复

`inputFreeRayCloud2D`：若 `map_ros_->local_updated_` 已为 true（本帧障碍已写过）则 **merge AABB**；否则赋值。全局 `update_*` 仍按点累积。

## 验证

脚本：`adapters/habitat_rangercr10/scripts/test_local_update_merge.py`  
产物：`reports/local_update_merge_20261106/test_local_update_merge.json`

| 案例 | overwrite vs 全图重建 | merge vs 全图重建 |
|------|----------------------|-------------------|
| 障碍在地面盒外 | 漏 49 inflate 格 | 一致 |
| 仅障碍 | 一致 | 一致 |
| 仅地面 | 一致 | 一致 |
| 混合 | 可漏（盒被地面子集覆盖时） | 一致 |
| 帧重置 | — | 次帧赋值 ≠ 上帧盒 |

`pass=true`。`libplan_env.so` 已在 `vln-rangercr10` 重建。
