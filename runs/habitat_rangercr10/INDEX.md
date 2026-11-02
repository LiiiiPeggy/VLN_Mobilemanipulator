# habitat_rangercr10 run index

大文件在 D 盘：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/`

| 目录 | 含义 | 状态 |
|------|------|------|
| `kinematic_demo/` | **原生** Habitat URDF 运动学 + EE RGB-D | 本轮通过 |
| `apexnav_loop/` | ApexNav 动作 ID 有界闭环（运动学） | 本轮通过 |
| `ppo_habitat_probe/` | PPO 接口探针（未集成） | `probe_only` |
| `hybrid_kinematic_demo/` | 上轮混合路径（MuJoCo 网格 + ApexNav EGL） | 后备 |
| `mujoco_teleop_smoke/` | MuJoCo Teleop PPO 短测 | 上轮通过 |
| `apexnav_stub/` | 旧延期说明 | 已由 `apexnav_loop` 取代 |

报告：`reports/habitat_rangercr10_integration.md`
