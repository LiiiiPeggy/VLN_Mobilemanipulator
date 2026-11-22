# Joint4 交付报告（2026-11-22）

## 1. 运行有效性

| 项 | 结论 |
|----|------|
| 批次 | `joint4_20261122_164956`，8/8 完成，锁已释放 |
| 工作区/分支 | `VLN_Mobilemanipulator_integrate` / `cursor/habitat-rangercr10-scale070-integrate` |
| 源码冻结 | **`a77f7d979f0dd0068dc5adf0f221e8acf40d41b2`**（批次启动时 HEAD） |
| 容器/devel | `vln-rangercr10-integrate` / `.catkin_devel_integrate` |
| 配置串线 | **无**；8/8 `profile_ok` + `recovery_mode_ok` + `nf_look=false` + `spawn_status=ok` |
| PPO | **全部未调用**；臂姿来自 `fixed_base_gimbal` → `ARM_DEFAULT`；无 `PPO_RAISE_JSON` |
| model_9999 权重更新 | **不影响本批**（抬臂链路未进入）；单列见 §5 |

变量仅：`INFLATION_PROFILE`∈{legacy018,inf020_soft010} × `BLOCKED_RECOVERY_MODE`∈{legacy,v2}。

### V2 开关行为（本批生效部分）

- turn 连续全挡 → `opposite_turn` → `forced_forward_after_turn_block`（经碰撞试探）
- 仅平移清零 escalate
- FSM Look 左右交替：本批 nf_look=OFF，**未触发**

## 2. 八组主结果（详见 `results_*/SUMMARY_TABLE.md`）

### hy1_plant_0

| 组 | 规划 | 恢复 | term | dtg↓ | moved↑ | near_goal | FF_try/exec/moved |
|----|------|------|------|------|--------|-----------|-------------------|
| g1 | legacy018 | OFF | planner_stop | 2.313 | 2.46 | F | 0/0/0 |
| g2 | inf020 | OFF | budget | 1.628 | 3.85 | F | 0/0/0 |
| **g3** | **legacy018** | **ON** | budget | **0.485** | **5.71** | **T** | **5/3/3** |
| g4 | inf020 | ON | planner_stop | 1.836 | 2.40 | F | 1/0/0 |

### Dd4b toilet_0

| 组 | 规划 | 恢复 | term | dtg↓ | moved↑ | near_goal | FF_try/exec/moved |
|----|------|------|------|------|--------|-----------|-------------------|
| g1 | legacy018 | OFF | budget | 2.716 | 2.38 | F | 0/0/0 |
| **g2** | **inf020** | **OFF** | budget | **2.107** | **4.55** | F | 0/0/0 |
| g3 | legacy018 | ON | budget | 3.011 | 2.13 | F | 5/4/5 |
| g4 | inf020 | ON | budget | 2.991 | 2.63 | F | 6/6/6 |

**成功率**：8/8 `success_claimed=False`。无 ObjectNav 成功。

## 3. 配置建议

| 配置 | 建议 | 理由 |
|------|------|------|
| `INFLATION_PROFILE` 默认 | **保持 `legacy018`** | inf020 单独略增移动，但未带来成功；与 v2 组合在 hy1 上反而变差（g4） |
| `BLOCKED_RECOVERY_MODE` 默认 | **暂保持 `legacy`** | hy1 上 v2 有明确进展（near_goal），但 dd4b 上 dtg/blocked 变差 → **候选**而非默认翻转 |
| 下一评测候选 | `legacy018` + `v2` | hy1 最优；需更大样本确认是否伤窄通道 |
| `ENABLE_NO_FRONTIER_LOOK` | 保持 false（本批设计） | — |

**不跑原成功任务回归的原因**：在 `apexnav_real` 下扫描 488 份 summary，**0** 例 `success_claimed=True`，无可用冻结成功案例。

## 4. 下一项修复（最明确执行受阻）

来自 **g3 hy1 step 106**（近目标仍失败）：

- 请求 `TURN_RIGHT` 连挡 → recovery `forced_forward`
- `block_reason=robot_env_collision`，探针 t≈0.2 即挡
- 接触：`d455_link` + `gripper_finger1_finger_tip_link`
- 最终仍 near_goal（0.485 m）但预算耗尽未成功

→ 优先：**近距 3D 执行碰撞（相机/夹爪）与 forced_forward 可行间隙**，而非继续加大规划膨胀。

## 5. PPO 权重更新（并列，不影响本批）

- 发布文件与 `load_actor` 推理接口检查 **通过**（SHA 一致，117→512-256-128→8）
- **本轮未运行抬臂验证**
- 历史抬臂 JSON / 旧实验仍标注原 `model_5999` 来源

## 6. 清理

- joint4 wrapper 已退出；`LOCK_RELEASED`
- 已清理 integrate 容器内 :11316 残留尝试；主机锁 **FREE**
