# Habitat ↔ RangerBox-CR10 adapter

独立适配层，**不修改** `baselines/*` 默认配置。

## 固定版本

| 项 | 值 |
|----|----|
| LocoManip 分支 | `rangercr10-teleop` |
| LocoManip commit | `1973cb4` |
| Teleop PPO 默认权重 | `.../2026-10-29_19-12-08_stage45j_ppo/model_5999.pt` |
| Habitat-Sim | **0.3.1 + Bullet**（专用镜像 `vln-rangercr10:bullet`） |
| 观测/动作 | 117-D / 8-D，3 帧历史，10 Hz（MuJoCo 侧） |

## 控制模式声明

本目录 Demo 默认是 **`kinematic_state_set`**（直接写底盘 SE(2)+臂关节），**不是** Ranger 四轮转向全身动力学。碰撞接触点仅作诊断。

## Catkin 重编（改 `astar2d` / `plan_env` 后必做）

容器 `vln-rangercr10` 中运行入口源码：`source /workspace/ApexNav/devel/setup.bash`  
（`/workspace/ApexNav` → `baselines/ApexNav` 软链）。改头文件成员布局后**必须**重编依赖包，否则会 ABI 错位 segfault（记为基础设施失败，不计入导航 SR）。

```bash
docker exec vln-rangercr10 bash -lc '
source /opt/ros/noetic/setup.bash
cd /workspace/ApexNav
# 改 path_searching/astar2d.h → 至少
catkin_make --pkg path_searching exploration_manager -DCMAKE_BUILD_TYPE=Release
# 改 plan_env/sdf_map2d.* / map_ros.* → 至少
catkin_make --pkg plan_env path_searching exploration_manager -DCMAKE_BUILD_TYPE=Release
'
# 确认入口加载的是该工作区产物：
#   rosrun / roslaunch 前 source /workspace/ApexNav/devel/setup.bash
#   exploration_node → /workspace/ApexNav/devel/lib/exploration_manager/exploration_node
```

冻结实验基线（启动）：`startup_prior_mode=initial_footprint`，`expand_m=0.3`（半轴外扩；0.7× F0 半轴≈0.756×0.604 m，地图分辨率 0.05 m）。  
障碍去噪：`obstacle_denoise=none|median3`（当前帧 OCC 投影，进持久地图/膨胀前）。

## 运行

```bash
# 0) EGL ICD（conda bullet 后可能被清空）
bash adapters/habitat_rangercr10/scripts/ensure_egl_icd.sh

# 1) 原生 Habitat URDF 运动学 Demo（推荐）
bash adapters/habitat_rangercr10/scripts/run_kinematic_demo.sh

# 2) ApexNav 动作 ID 有界闭环（运动学）
bash adapters/habitat_rangercr10/scripts/run_apexnav_loop.sh

# 3) PPO Habitat 探针（会写 probe_only，不宣称集成成功）
bash adapters/habitat_rangercr10/scripts/run_ppo_habitat_probe.sh

# 后备：混合 Demo / MuJoCo PPO smoke
bash adapters/habitat_rangercr10/scripts/run_hybrid_kinematic_demo.sh
bash adapters/habitat_rangercr10/scripts/run_mujoco_teleop_smoke.sh
```

证据：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/`  
报告：`reports/habitat_rangercr10_integration.md`
