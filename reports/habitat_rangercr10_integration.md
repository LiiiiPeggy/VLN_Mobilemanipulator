# Habitat ↔ RangerBox-CR10 集成报告

更新：2026-11-04（**Stage 4.10d** URDF/D455/默认关节/PPO 共钉扎）  
范围：`adapters/habitat_rangercr10/`；**不修改**六套 baseline 默认评测协议、**不修改** LocoManip 训练代码。  
大文件（权重/视频/轨迹）在 `/media/ubuntu/D/VLN_shared/`。

---

## 总表（本轮真实状态）

| 项 | 状态 | 证据 |
|----|------|------|
| LocoManip pin | **stage 4.10d @ `ec5fd65`** | HEAD 只读 `2d6d1f5`；策略 `2026-11-03_16-30-44_stage410d_ppo/model_5999.pt` |
| URDF / D455 | **顶装 AG95** | `d455_joint` xyz=`(0,0.10,0.14)` rpy=`(0.785,-1.571,-2.356)`；`VERSION_stage410d.json` |
| ARM_DEFAULT | `[0.236, 0.086, -2.398, -0.830, -1.335, 0]` | 与 `ranger_policy.py` 一致；**勿混** stage45j |
| MuJoCo PPO | **短测通过** | `ppo_stage410d_mujoco_20261104_113929/`（drift/modes/coverage/self_collision） |
| Habitat 直立 | **保持** | `Ry(-90)*Rx(-90)`；轮贴地 |
| D455 FK | Hab AGL≈**0.857 m**；MuJoCo≈**0.880 m** | `fk_compare_stage410d_20261104/`；角误差 ≈0°；near 遮挡 **0** |
| LOOK | joint3 ±0.6 rad | INIT/DOWN/UP near=0；DOWN pitch≈−26°；UP≈+33° |
| ApexNav 探索 | **多步**（开阔 ep） | `20261104_114652`：explore 24 步含 **MOVE_FORWARD×4** |
| PPO→Habitat | **探针仅** | 观测维不匹配；**非**全身 PPO 成功 |
| 控制模式（ApexNav） | `kinematic_state_set` | 与 PPO MuJoCo 分列验收 |

---

## 1. Stage 4.10d 版本钉扎

| 字段 | 值 |
|------|-----|
| 分支 | `rangercr10-teleop` |
| 特征提交 | `ec5fd6584bd3d562812c12ef2d8e2f87fba98175` |
| 同步时 HEAD | `2d6d1f526c32b0f2965fdf624840155cf96ad586` |
| 策略 | `logs/rsl_rl/ranger_cr10_teleop/2026-11-03_16-30-44_stage410d_ppo/model_5999.pt` |
| Habitat URDF pin | `/media/ubuntu/D/VLN_shared/robots/rangercr10/rangercr10lidar_habitat_stage410d_ec5fd65.urdf` |
| 适配层元数据 | `adapters/habitat_rangercr10/assets/VERSION_stage410d.json` |
| 历史对照 | stage45j `2026-10-29_19-12-08_stage45j_ppo/model_5999.pt`（**不覆盖、不混关节偏置**） |

---

## 2. MuJoCo PPO 短测（P0）

目录：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/ppo_stage410d_mujoco_20261104_113929/`

复现：

```bash
bash adapters/habitat_rangercr10/scripts/run_ppo_stage410d_mujoco.sh
```

| Suite | 结果摘要 |
|-------|----------|
| drift | 零命令/近零命令持稳；写出 `mujoco_drift_stage410d.json` + traces |
| modes | 底盘 A1/A2、臂 B*、联合 C*；滤波 on 时臂跟踪 ee_pos 约 1–5 cm 量级 |
| coverage | `--coverage_box 4.10` 安全盒 |
| self_collision | `check_self_collision.py --box 4.10`；home_contacts=[]；轴安全盒与 LocoManip final 一致 |

**不能**把 Habitat `kinematic_state_set` 或全零观测动作当作 PPO 成功证据。

---

## 3. Habitat 相机 / 姿态（P1）

诊断：`camera_view_diag_stage410d_20261104_114102/`  
FK 对比：`fk_compare_stage410d_20261104/fk_compare.json`

| 构型 | AGL (m) | pitch (°) | near&lt;0.35 |
|------|---------|-----------|-------------|
| LOCOMANIP_ARM_DEFAULT_410d | 0.857 | ≈0 | **0.0** |
| TURN_DOWN (j3−0.6) | 0.605 | ≈−25.7 | **0.0** |
| TURN_UP (j3+0.6) | 1.301 | ≈+33.3 | **0.0** |

说明：MuJoCo 同关节 `d455_link` AGL≈0.880 m；Habitat FK 约低 2.3 cm（地板/基座偏置）。高度容差改为 ±2.5 cm，避免高度追逐破坏共钉扎默认构型。光学位姿来自 URDF FK，**未**伪造渲染相机。

---

## 4. ApexNav 真实探索（P2）

### 4.1 狭窄场景对照（TEEsav eid=4）

`apexnav_real/20261104_114357/`：free≈**169**（旧遮挡时代 free≈6）；仍 `NO_PASSABLE_FRONTIER` → 1 步 explore STOP。  
诊断：`frontier_diagnosis.json`（膨胀后无可通行 frontier，非伪造）。

### 4.2 开阔场景主结果（Dd4bFSTQ8gi chair eid=5）

`apexnav_real/20261104_114652/`

| 字段 | 值 |
|------|-----|
| status | ok |
| termination | **step_budget_exhausted**（max_steps=50） |
| n_init_lookaround | 26 |
| n_explore_planner | **24** |
| explore 动作 | TURN_LEFT×20 + **MOVE_FORWARD×4** |
| entered_callActionPlanner | true |
| online free / occ / inflate | 182 / 909 / 1768 |
| camera | ARM_APEXNAV_INIT；all_ok；AGL≈0.857 |
| spawn | ok；offset≈0.5 m；adapted_episode |
| scripted_policy_used | false |
| Demo | `demo/apexnav_ranger_paper_demo.mp4`（16:9） |

复现：

```bash
MAX_STEPS=50 SCENE_FILTER=Dd4bFSTQ8gi CATEGORY_FILTER=chair EPISODE_ID=5 \
  bash adapters/habitat_rangercr10/scripts/run_apexnav_real_episode.sh
```

ROS：隔离 master `:11312`（保留 NBV `:11311`）。

**诚实边界**：寻物未宣称成功；后期日志仍有 `Maybe no passable frontier` 警告；探索以转向为主、前进 4 步。已严格区分 init 环视 / 正式 explore / 终止原因。

---

## 5. PPO–Habitat 接口（P3）

`ppo_habitat_probe_stage410d/summary.json`：加载 stage410d actor、117/8/3 维接口烟雾测试。  
**blocked_by_observation_mismatch**（缺动力学观测、轮组映射、10 Hz 滤波未接入 Habitat）。  
全身控制验收继续以 MuJoCo 为准。

---

## 6. Demo 布局与 7 Hz 视频

布局（1280×720）不变：

- 主画面：第三人称跟随  
- 左下：D455 RGB + 检测  
- 右下：ApexNav `/grid_map/*`（非 Habitat GT）  
- 标注：策略 pin / control_mode / phase / action  

### 7 FPS 同步版（本轮）

| 项 | 值 |
|----|-----|
| 输出 | `.../20261104_114652/demo/apexnav_ranger_paper_demo_7fps.mp4` |
| ffprobe | **7/1 FPS**，1280×720，300 帧，时长 ≈42.86 s（≈真实 episode） |
| 原 2 FPS | **保留** `apexnav_ranger_paper_demo.mp4`（非用 ffmpeg 加速冒充 7 FPS） |
| 主画面/EE 渲染 | 按 `actions.jsonl` 时间戳 7 Hz 插值底盘+臂，Habitat FK 重渲染 |
| 检测内容 | 真实 VLM 结果；显示 7 Hz，内容 hold；实测 ≈**1.17 Hz** |
| 地图内容 | 真实 `/grid_map` PNG；显示 7 Hz；内容更新 ≈**0.30 Hz**；白底纸质配色 |
| 地图配色 | 白底/未知白、自由浅灰、障碍深灰黑、机器人蓝箭头、轨迹橙 |
| 复现 | `bash adapters/habitat_rangercr10/scripts/run_demo_7fps.sh` |
| 频率记录 | `demo/demo_7fps_rates.json` |

---

## 7. 根因对照（相对 2026-11-03）

| 旧问题 | 4.10d 后 |
|--------|----------|
| 侧装/中间默认 → 光学 ~0.78 m 或高度追逐姿态 | 顶装 + ARM_DEFAULT；水平；near=0 |
| TURN_DOWN near≈56% | TURN_DOWN near=0（俯仰约 −26°，臂适配非 Habitat look） |
| free≈6 → 立即 NO_COVERABLE | free≈170–180；开阔 ep 进入多步 explore + FWD |
| PPO 仍 stage45j | MuJoCo 已切 stage410d；Habitat 运动学寻物与 PPO 分列 |

---

## 8. 转向 / 膨胀（2026-11-04）

详见 `reports/apexnav_rangercr10_frontier_inflation.md`。

- **主因**：odom 航向曾与 ROS 位移差 π → 已修。  
- **足迹**：0.18 m << Ranger 半宽 0.435 m；`ranger_safe=0.485` / `mid030=0.30` 可选（在线 ≥0.30 即近乎吃光 free）。  
- 窄场景 yaw 修后仍 `NO_PASSABLE`（与膨胀主因无关）。  
- Habitat 演示默认 `INFLATION_PROFILE=legacy018`（标不安全）。

## 9. 深度有效性 / 环视放射伪影（2026-11-05）

详见 `reports/habitat_rangercr10_depth_radial_fix.md`。

- **根因**：近距自遮挡曾改写为 max-range（≈5 m）→ 虚假终点参与占据/射线；Habitat mindist 覆盖使 launch 近距滤波无效。  
- **修复**：无效/机体像素 → **NaN**（永不写 5 m/0）；`map_ros` 跳过 NaN；几何自遮挡（球+胶囊+AABB）。  
- **证据**：`.../depth_radial_fix/`；采用 run `real_s070_pporaise_yr17_depthfix4_20261105_201112`（occ/free=727/932，FWD 0.50 m）。  
- Demo 稀疏扇形仍可能出现（`/grid_map` PointCloud2 散点可视化），但已无 r≈5 m 伪终点团簇。

## 10. Demo Occupancy + Value Map（2026-11-05）

详见 `reports/habitat_rangercr10_valuemap_demo.md`。

- 右下角：白底 `/grid_map` 占据 + `/grid_map/value_map` 黄→红热力（ApexNav.rviz 配色）。  
- ITM：现有 BLIP-2 `/blip2/cosine_score`；同帧先 cosine 后深度。  
- 证据：`real_s070_pporaise_yr17_valuemap_20261105_210015`；7fps 1280×720。  
- 仅 Demo 层；未改规划/PPO/检测后端。

## 11. 未解决问题

1. Habitat↔MuJoCo 光学 AGL 仍差 ≈2.3 cm（可接受；勿用乱搜关节凑 0.88）。  
2. 安全足迹与可达 Frontier：需非圆足迹/未知区策略，不能只调各向同性半径。  
3. PPO 未进 Habitat 动力学闭环。  
4. `env.close()` 偶发 `malloc_consolidate` abort（任务摘要已落盘；rc 134 可接受）。  
5. 几何 AABB 在部分帧自遮挡比例偏高（~50%+）；若近距真家具被误掩，可收紧 pad 或仅用胶囊。
