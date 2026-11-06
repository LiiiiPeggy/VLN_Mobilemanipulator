# 底盘起点 UNKNOWN 根因诊断与单变量修复

更新：2026-11-06  
分支：`cursor/habitat-rangercr10-scale070`  
基准：`2057942` → 本轮补丁（ground free-ray）  
证据：`reports/base_start_unknown_20261106/`

---

## 1. 为什么相机附近 FREE，底盘却 UNKNOWN？

| 场景（修复前） | 底盘中心 | 相机 XY | 偏移 | 底盘 0.3 m 内 free | 最近 free |
|----------------|----------|---------|------|-------------------|-----------|
| yr17 | FREE | FREE | ≈0.65 m | 66 | ≈0.02 m |
| eF36 | UNKNOWN | FREE | ≈0.65 m | **0** | ≈0.53 m |
| HY1 | UNKNOWN | FREE | ≈0.65 m | **0** | ≈0.54 m |

臂载 D455 相对底盘前向水平偏移约 **0.65 m**。`map_ros` 的 free 由「深度终点 → 相机」射线雕刻，中心在**相机轨道**上。  
**不能**把相机邻域 free 数量当成底盘起点 free 的证据。

局部图：`local_map_{yr17,eF36,HY1}_{before,after}.png`（浅灰 free / 深灰 occ / 白 unknown / 蓝底盘 / 绿相机）。

---

## 2. 根因归类

逐阶段（修复前 pipeline）：

- 自遮挡：底盘在相机后方，前视本来看不到底盘脚下 → **不是主因**
- **地面高度过滤**：AGL ∈ [0, `filter_min_height=0.28`] 被计入 `height_other` **丢弃**（`height_ground_band` 全程 0；other 占 ~70%+）→ **主因**
- 坐标映射：运行时几何验收已通过 → **否**
- 障碍射线：仅障碍带 `[0.28,1.18]` 产生终点；难以稳定覆盖底盘中心 → 后果

**一句话**：地面带观测被过滤，臂载相机相对底盘偏移，障碍射线无法保证底盘 FREE。

---

## 3. 单变量修复

仅改地面处理接口（不改环视/PPO/0.7×/膨胀/规划器）：

- Launch：`map_ros/ground_free_ray_enable=true`（`algorithm_rangercr10.xml`）
- 代码：`SDFMap2D::inputFreeRayCloud2D` — AGL[0, filter_min_height] 点 **只打 free 射线、不写 OCCUPIED**
- 禁止项均未做（未强制 UNKNOWN→FREE、未清 unknown、未缩 inflation、未改回相机假 odom）

---

## 4. 修复前后正式回归（同 spawn / 30° / ≤20 探索）

| 场景 | 起点 occ | 0.3 m free | NO_PASSABLE | EXPLORATION 规划 | 探索步 | 净位移 m |
|------|----------|------------|-------------|------------------|--------|----------|
| yr17 前 | FREE(1) | 66 | 0 | 20 | 20 | 0.85 |
| yr17 后 | FREE(1) | 116 | 0 | 20 | 20 | 1.56 |
| eF36 前 | UNKNOWN(0) | 0 | 1 | 0 | 1 | 0 |
| **eF36 后** | **FREE(1)** | **85** | **0** | **20** | **20** | **3.17** |
| HY1 前 | UNKNOWN(0) | 0 | 1 | 0 | 1 | 0 |
| HY1 后 | UNKNOWN(0) | 0 | 1（第 4 次） | 3 次后失败 | 4 | 0.25 |

Run IDs：

- eF36：`real_s070_pporaise_ef36_groundfree_20261106_140100`
- HY1：`real_s070_pporaise_hy1_groundfree_20261106_172428`
- yr17：`real_s070_pporaise_yr17_groundfree_20261106_172630`

JSON：`before_after_summary.json`。

### 解读

- **eF36**：根因修复成立——起点 FREE，原生规划连续 20 次，无 NO_PASSABLE。
- **yr17**：对照未回归；free 更密、位移略增。
- **HY1**：**部分**——前 3 次仍能 EXPLORATION，但底盘中心仍 UNKNOWN，第 4 次再 NO_PASSABLE。该场景地面 free 候选虽多，却未在底盘 0.3 m 内落 free（走廊 free 偏相机侧）。属**同根因下的场景覆盖不足**，需另立单变量（例如 LOOK_DOWN 朝底盘侧地面可见性 / 自遮挡与地面带交互），**本轮不再叠改**。

足迹：未改 inflation；eF36/yr17 有多步 FWD，blocked 步未见异常飙升；**完整 oriented 足迹安全率未在本轮重跑专用探针**（标记为待专项），不能把规划成功当成足迹安全。

---

## 5. 是否开 15°？

**还不要。** eF36 已通，但 HY1 底盘 UNKNOWN/NO_PASSABLE 未彻底消除。先收口 HY1 覆盖，再独立 15°。

---

## 6. 最终六问

1. **为何相机 FREE、底盘 UNKNOWN？** 臂载相机偏移 + free 按相机射线更新；底盘不在相机邻域。  
2. **主因？** **地面高度过滤**丢弃 AGL[0,0.28] 观测（非自遮挡主因、非坐标、非膨胀）。  
3. **修改是否对准根因？** **是**（地面 → free-ray-only）；eF36 定量证实。  
4. **eF36/HY1 是否恢复原生规划？** **eF36 是**；**HY1 仅部分**（仍 UNKNOWN，稍后 NO_PASSABLE）。  
5. **足迹是否安全？** 未宣称；需专项 footprint 回放。  
6. **15°？** **否**，先处理 HY1 残余覆盖。
