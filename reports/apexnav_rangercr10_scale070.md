# Ranger+CR10 Habitat 整机 0.7× 缩放验证

分支：`cursor/habitat-rangercr10-scale070`  
更新：2026-11-05  
标记：所有 0.7× 结果为 **`scaled_robot_proxy_070`**，**不得**冒充真实 Ranger+CR10 实机安全成绩。  
1.0× 原始 URDF / Stage 4.10d PPO / 既有 ApexNav 跑数保持不变。

---

## 1. 实现（适配层 only）

| 项 | 说明 |
|----|------|
| 生成 URDF | `src/scale_urdf.py` → `assets/urdf/..._s070.urdf` |
| 缩放内容 | 全部 origin **xyz**、mesh `scale`、box/cyl/sphere 尺寸 |
| 不缩放 | rpy、关节轴、关节限位、相机 **内参** |
| 运行时 | `RangerCr10KinematicEnv(robot_scale=0.7)` |
| 接地 | `default_base_y`/`wheel_radius_snap` ×0.7，贴地误差 ~0 |
| 相机目标 | AGL 目标 **0.616 m**（0.88×0.7），实测 ≈0.600 m，容差内 |
| 足迹 | 半宽 0.435→**0.304 m**；直行通道需求 ≈0.71 m |

命令：

```bash
# 生成 URDF
python -m src.scale_urdf --scale 0.7 --force

# 几何/相机烟雾
docker exec -e PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10 \
  vln-rangercr10 bash -lc 'source /opt/ros/noetic/setup.bash; python -m src.scale070_verify'

# 同 episode + 强制 1.0× spawn 的 0.7× 短测
ROBOT_SCALE=0.7 bash adapters/habitat_rangercr10/scripts/run_scale070_compare_batch.sh
```

---

## 2. 模型对照（verify）

证据：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/scale070_verify/scale070_verify.json`

| 指标 | 1.0× | 0.7× |
|------|------|------|
| 视觉高度比 | 1.0 | **0.700** |
| 前轮 xz 距比 | 1.0 | **0.702** |
| 相机 AGL | 0.857 m | **0.600 m**（目标 0.616） |
| 直立 `up_dot` | 1.0 | 1.0 |
| 轮心贴地误差 | — | ~0 |
| 前进 0.25 m 轮转 | — | Δθ≈2.33 rad |
| pass | — | **true** |

---

## 3. ApexNav 对照（同 episode / 同 spawn XY，legacy018）

| 场景 | 尺度 | 进入探索 | 规划模式 | FWD m | 终止 | 足迹 safe_ratio* |
|------|------|----------|----------|-------|------|------------------|
| yr17 | 1.0 | ✓ | SEARCH_EXTREME×12 | **1.50** | planner_stop | **0.0** |
| yr17 | 0.7 | ✓ | SEARCH_EXTREME×5 | 0.50 | planner_stop | **1.0** |
| eF36 | 1.0 | ✓ | EXPLORATION×24 | 0.25 | step_budget | — |
| eF36 | 0.7 | ✓ | EXPLORATION×18 + NO_PASSABLE | **0.75** | planner_stop | **0.67** |
| Dd4b | 1.0 | ✓ | EXTREME+EXPL | 1.25 | step_budget | — |
| Dd4b | 0.7 | ✓ | SEARCH_EXTREME×10 | 1.00 | planner_stop | **0.67** |
| HY1 | 1.0 | ✓ | NO_PASSABLE | 0 | planner_stop | — |
| HY1 | 0.7 | ✓ | NO_PASSABLE | 0 | planner_stop | — |

\*定向足迹回放（半宽按当前尺度）；GT 仅评价。  
JSON：`apexnav_real/scale070_compare_batch_*.jsonl`；足迹：`footprint_path_safety/{yr17_openband_1x,yr17_openband_s070,...}`。

### 解读

1. **足迹安全明显改善**：yr17 路径 1.0× safe_ratio=0 → 0.7× **=1.0**（半宽门槛降低 + 同几何路径）。  
2. **探索距离未全面变长**：yr17 反而 1.5→0.5 m；eF36 前进 0.25→0.75 m。相机变矮改变观测/建图，规划行为会变。  
3. **HY1 仍早停**：缩小机体不能修复「环视后无 A\* 可达 Frontier」。  
4. **规划器仍用 legacy018（0.18 m）**：与 0.7× 半宽 0.304 m 仍不匹配；**规划成功 ≠ 足迹安全**（虽 0.7 下差距缩小）。

---

## 4. Demo

| 视频 | 规格 |
|------|------|
| yr17 0.7× 7fps | `real_s070_yr17_openband_*/demo/apexnav_ranger_paper_demo_7fps.mp4`（1280×720，7/1） |
| eF36 0.7× 7fps | `real_s070_ef36_openband_*/demo/..._7fps.mp4` |
| yr17 1.0× 7fps（对照） | `real_wide_yr17_openband_*/demo/..._7fps.mp4` |

布局不变：主画面整机 + 左下 D455 检测 + 右下白底地图。

---

## 5. 结论

- 适配层整机 0.7×（视觉/碰撞/关节平移/轮距/相机外参平移）已验证直立、贴地、FK 相机、四轮同步。  
- **安全通行（离线足迹）在 yr17 上由失败转为通过**；**多步探索距离与 HY1 早停问题不能单靠缩尺解决**。  
- 保留 1.0× 为真实设备基准；0.7× 仅作 `scaled_robot_proxy_070` 仿真代理。
