# Demo 地图：取消 cell 边框（分辨率足迹填充）

更新：2026-11-05  
分支：`cursor/habitat-rangercr10-scale070`（基于深度 NaN 修复 `4db6ba2` + Value 叠加）  
范围：**仅 Demo 栅格化**；不改地图分辨率、占据概率、膨胀、规划输入。

---

## 1. 问题

右下角 Occ+Value 图每个 cell 呈独立小方块/栅格边框；环视仍见放射状结构。

## 2. 原始 `/grid_map` vs Demo 渲染

同一 yr17 spawn 下两轮 run 的 `planner_first_call_diag`：

| | prior (1px) | after (cell fill) |
|--|--|--|
| occupied 点数 | 584 | 584 |
| free 点数 | 1067 | 1067 |
| 量化 cell 集合 | **完全相同**（Jaccard=1.0） |

结论：

1. **真实深度观测**：occupied/free 来自 ApexNav `/grid_map` cell 中心（res≈**0.05 m**），非 Demo 伪造。  
2. **环视稀疏采样**：角速度覆盖 + 射线终点 → 扇区状 free/occ，**已在原始点云中**（occ `ang_peakiness≈7`）。  
3. **可视化伪影**：面板 12 m / 320 px 时，0.05 m cell ≈1.3 px；**单像素绘制**在相邻 cell 间留白，看起来像栅格边框/碎裂射线。

未删除任何放射状点；未做大范围平滑/形态学开闭运算。

## 3. 修复

`map_raster.py`：按 `sdf_map/resolution` 将每个 cell 画成轴对齐实心足迹（相邻边共边、无描边）。Value 热力同样按 cell 填充；occupied 仍最后绘制。

## 4. 对照产物

根目录：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/map_raster_compare/`

| 文件 | 说明 |
|------|------|
| `..._valuemap_.../same_data_before_after_side_by_side.png` | **同一** occ/free dump：1px vs cell-fill |
| `.../radial_raw_vs_render.json` | 放射度量 + 解读 |
| `live_step25_before_after/step{00,08,17,25}_*.png` | 实机 Demo 同时刻前后 |
| `live_step25_before_after/raw_grid_map_equality.json` | 原始 cloud 一致证明 |

采用 run：`real_s070_pporaise_yr17_mapfill_20261105_212419`  
7fps：`.../demo/apexnav_ranger_paper_demo_7fps.mp4`（1280×720 @ 7fps；旧 Demo 保留）

## 5. 复现

```bash
# 离线同一数据 A/B
python3 adapters/habitat_rangercr10/scripts/compare_map_raster_styles.py \
  --run_dir /media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_s070_pporaise_yr17_valuemap_20261105_210015

# 在线 Demo（cell-fill）
# …同既有 run_apexnav_real_episode.sh + run_demo_7fps.sh
```

## 6. 修改文件

- `adapters/habitat_rangercr10/src/map_raster.py`（新）
- `adapters/habitat_rangercr10/src/map_listener.py`
- `adapters/habitat_rangercr10/src/planner_first_call_diag.py`（dump `value_xyi.npy`）
- `adapters/habitat_rangercr10/scripts/compare_map_raster_styles.py`
