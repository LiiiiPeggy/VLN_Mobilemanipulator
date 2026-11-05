# 0.7× 代理：MuJoCo Teleop-PPO 抬臂 → ApexNav

分支：`cursor/habitat-rangercr10-scale070`（保留 `897d58b` 缩放实现）  
标记：全部 **`scaled_robot_proxy_070`**  
更新：2026-11-05

---

## 1. PPO 契约（未改训练）

| 项 | 值 |
|----|-----|
| 权重 | `stage410d_ppo/model_5999.pt` |
| 观测 | **117-D**，hist=**3**，10 Hz |
| 动作 | **8-D** `[vx,wz,j1..j6]`；臂目标=`ARM_DEFAULT + 0.25*raw[2:]` |
| 条件 | teleop：`vel_cmd` + `ee_cmd=ee_command_from_offset(dpos,drpy)` |
| 执行 | **原生 MuJoCo** `teleop_eval.Sim` 循环；Habitat **仅同步关节** |

抬臂指令：`vx=wz=0`，`ee_offset_pos=(0,0,+0.40)`（KEYBOARD_BOX_410 Z+ 上限），**不用 IK**。

---

## 2. 抬臂结果（Habitat 0.7× FK）

证据：`ppo_raise_stage410d_z040.json` + 各 run `ppo_raise/handover.json`

| 量 | 抬臂前 (ARM_DEFAULT@0.7) | 抬臂后 |
|----|--------------------------|--------|
| TCP AGL | ≈0.530 m | **≈0.811 m**（目标 0.88±0.02：**未达**） |
| D455 optical AGL | ≈0.600 m | **≈0.881 m** |
| D455 pitch/roll/yaw_err | ~0 | ≈1.6° / −2.8° / −1.1°（水平 OK） |
| MuJoCo 底盘漂移 | — | ≈0.023 m |
| EE 跟踪误差 | — | ≈1.9 cm / 3.4° |
| 近限位 | — | false |

说明：在 teleop Z+0.40 饱和下，**D455 回到 ApexNav 常用 ~0.88 m 视高且水平**；TCP（Link6+offset）最高约 0.81 m。按验收「末端 0.88」记 **best-effort / short**，**未改 IK、未硬编码关节**。

---

## 3. ApexNav（抬臂姿态保持后）

同 episode + 强制 1.0× spawn XY；`robot_scale=0.7`；legacy018；`:11312`。

| 场景 | 进入探索 | 模式 | FWD | free | 终止 |
|------|----------|------|-----|------|------|
| yr17 | ✓ | NO_PASSABLE×1 | 0 | 1195 | planner_stop |
| eF36 | ✓ | NO_PASSABLE×1 | 0 | 441 | planner_stop |
| HY1 | ✓ | NO_PASSABLE×1 | 0 | 337 | planner_stop |

对照：同场景 **无 PPO 抬臂** 的 0.7× yr17 曾为 SEARCH_EXTREME FWD 0.5 m。抬高相机后环视建图变化，**Frontier A\* 立即不可达**——记为观测结构效应，不是碰撞关闭造成的假成功。

JSONL：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/ppo_raise_s070_batch_20261105_171118.jsonl`。

| 场景 | free / occupied / unknown | n_explore | explore_actions | forward_m |
|------|---------------------------|-----------|-----------------|-----------|
| yr17 | 1195 / 7067 / 42033 | 1 | STOP×1 | 0.0 |
| eF36 | 441 / 2194 / 36731 | 1 | STOP×1 | 0.0 |
| HY1 | 337 / 947 / 36546 | 1 | STOP×1 | 0.0 |

（三场景均 26 步环视 + 1 步探索 STOP；足迹安全因无前进路径未另计。）

---

## 4. 控制权交接

1. MuJoCo PPO 独占臂（底盘 cmd=0）  
2. 同步 `arm_q` → Habitat；底盘不动  
3. ApexNav 接管导航 / LOOK（joint3 相对抬臂姿态微调）与探索  
4. 全程标记 `scaled_robot_proxy_070`

---

## 5. Demo（1280×720，7/1，论文风三画面）

路径前缀：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/`

| 场景 | 7fps | 帧数 |
|------|------|------|
| yr17 | `real_s070_pporaise_yr17_20261105_171118/demo/apexnav_ranger_paper_demo_7fps.mp4` | 146 |
| eF36 | `real_s070_pporaise_ef36_20261105_171203/demo/apexnav_ranger_paper_demo_7fps.mp4` | 140 |
| HY1 | `real_s070_pporaise_hy1_20261105_171252/demo/apexnav_ranger_paper_demo_7fps.mp4` | 135 |

抬臂过程帧：各 run `ppo_raise/frames/`；MuJoCo 日志：`ppo_raise_stage410d_z040.json(.jsonl)`。

---

## 6. 复现

```bash
bash adapters/habitat_rangercr10/scripts/run_ppo_raise_then_apexnav_s070.sh
```

---

## 7. 结论

1. **Teleop-PPO 抬臂链路已接通**：MuJoCo 原生推理 → Habitat 0.7× 关节同步，底盘稳定、无 IK。  
2. **D455 ≈0.88 m 且水平**；**TCP ≈0.81 m**，未满足 0.88±0.02（策略在 Z+ 箱顶饱和）。  
3. 该视高下初版 yr17/eF36/HY1 **立即 NO_PASSABLE**（见同目录后续报告）。  
4. **后续已修复多步探索**：`apexnav_rangercr10_nopassable_after_ppo_raise.md`（AGL Z + odom 相机 XY + self-hit）。  
5. 未改 1.0× 模型 / PPO 权重 / ApexNav 算法源码默认。