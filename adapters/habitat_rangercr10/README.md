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

## 运行

```bash
# 1) 最低验收（推荐）：混合运动学 Demo
#    MuJoCo 机器人网格 + Habitat EE RGB-D（借 vln-apexnav EGL）
bash adapters/habitat_rangercr10/scripts/run_hybrid_kinematic_demo.sh

# 2) MuJoCo Teleop PPO 短测（117/8/10Hz）
bash adapters/habitat_rangercr10/scripts/run_mujoco_teleop_smoke.sh

# 3) 纯 Habitat URDF Demo（需 vln-rangercr10:bullet 且 EGL 可用）
bash adapters/habitat_rangercr10/scripts/run_kinematic_demo.sh
```

证据输出：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/`  
报告：`reports/habitat_rangercr10_integration.md`
