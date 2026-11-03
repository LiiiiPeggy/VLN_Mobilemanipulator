# PROGRESS.md — 当前状态

更新时间：2026-11-03（相机 FK / LOOK / free-space 诊断；不接新 PPO）  
证据优先于本文；冲突时以代码、`reports/`、`runs/`、容器实测为准。

## 研究目标与阶段

**目标**：六套 VLN/ObjectNav baseline 可复现评测 → 再适配 RangerBox-CR10。

**当前阶段**：真实 ApexNav ROS 闭环与论文风 Demo 已保留；本轮完成 **Habitat 运动学相机/臂构型验证**，默认臂改为只读自 LocoManip 4.10；**不**等待/替换新 PPO 训练。

## Baseline 状态

| Baseline | 状态 | 备注 |
|----------|------|------|
| VLFM / ApexNav / MSGNav | `BATCH_OK` | 镜像未改 |
| APRR / SG-Nav / UniGoal | `CONTAINER_READY` | 未改 |

## 机械臂适配

| 项 | 状态 | 证据 |
|----|------|------|
| 直立 / 贴地 | 通过 | `Ry(-90)*Rx(-90)` |
| 初始臂 | **LocoManip 4.10 默认** | HEAD `b0a536f` 只读；光学 AGL≈0.78 m，水平 |
| LOOK | joint3 ±0.6 rad | DOWN 诱发近场遮挡；UP 干净 |
| ApexNav 闭环 | 保留 | `real_20261103_124521` |
| free/NO_COVERABLE | 原因已记 | 近场遮挡 + 狭窄出生 + frontier 空 |
| PPO 权重 | **仍 stage45j** | `model_5999.pt`；新训未接 |
| 控制 | `kinematic_state_set` | |

## 下一步（最多 5）

1. 用 4.10 臂 + 更开阔 Episode 重跑有界 ApexNav，验证 free/frontier 与多步 FWD。  
2. LocoManip 新 PPO 训练完成后：**单独**做权重钉扎与控制验证（本轮不做）。  
3. TURN_DOWN 遮挡：评估更小俯仰或组合关节。  
4. 点云一致性报告完善。  
5. 停用后腾 GPU。
