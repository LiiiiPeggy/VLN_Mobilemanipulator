# Ranger 执行穿模修复 + fixed_base_gimbal 部署基线

更新：2026-11-16  
分支：`cursor/habitat-rangercr10-scale070`  
范围：仅导航与主动观察；夹爪固定；**不启动 PPO**；算法变量冻结（F0+expand0.3 / denoise=none / ObjectHold / LabelMap / 评估阈值）。

## 三者区分（勿混归因）

| 维度 | 内容 |
|------|------|
| **A. 执行有效性** | `kinematic_collision_v1.1`：试探/提交分离；机器人–环境碰撞拒绝/截断；轮地支撑允许；初始穿透单独报告 |
| **B. 相机基线** | `camera_mode=fixed_base_gimbal`（`simulated_gimbal`）：光心相对底盘固定；LOOK_UP/DOWN 只改俯仰；臂保持 `ARM_APEXNAV_INIT` |
| **C. 任务成功率** | 新协议下 24-ep SR_proxy；**不可与旧轨迹直接因果对比** |

## 配置冻结（给 Cursor B）

| 项 | 值 |
|----|-----|
| `robot_scale` | **0.7**（`scaled_robot_proxy_070`） |
| `camera_mode` | **fixed_base_gimbal** |
| `executor_version` | **kinematic_collision_v1.1**（轮地高度带修复后） |
| `startup_prior_mode` | `initial_footprint` |
| `startup_prior_expand_m` | `0.3`（仅地图查询；**不豁免**执行碰撞） |
| `obstacle_denoise` | `none` |
| PPO | **关闭**（`PPO_RAISE_JSON=`） |
| 清单 | `reports/startup_prior_e2e_20261107/episode_list.json` |

运行：

```bash
# 运动+相机单测（无 ROS）
docker exec vln-rangercr10 bash -lc \
  'PYTHONPATH=/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10:$PYTHONPATH \
   python adapters/habitat_rangercr10/scripts/test_execution_collision_camera.py'

# 冒烟 3 / 全 24
SMOKE_ONLY=1 SKIP_DEMO=1 bash adapters/habitat_rangercr10/scripts/run_exec_collision_baseline_batch.sh
SMOKE_ONLY=0 SKIP_DEMO=1 MAX_EXPLORE_ACTIONS=100 \
  bash adapters/habitat_rangercr10/scripts/run_exec_collision_baseline_batch.sh
```

每步 `steps.jsonl` → `exec` 含：`requested_action` / `actual_action`、底盘/相机位姿、`blocked`/`truncated`/`block_reason`、碰撞分类、`moved_m`。

## A. 穿模根因与修复

**原问题**：`MotionType.KINEMATIC` 直接写半步/整步位姿；回退条件为「接触总数↑ 且 moved&lt;0.05」——位姿传送常绕过；转向与 LOOK 无碰撞拒绝。

**修复**（`execution_collision.py` + `_execute_action`）：

1. 验证 Bullet 接触可用；**不以** `contact_test==0` 为无碰撞。
2. 分类：`wheel_support` / `robot_env` / `self` / `other`。
3. 平移步长 0.05 m、转角 5°、臂 8 段插值；薄障碍可能漏检（已文档化）。
4. 无效则拒绝或截断到最后合法姿态；向上返回真实执行结果。
5. 试探不发布观测；回滚底盘/关节/轮角/云台俯仰。
6. `initial_penetration.json` 单独报告。
7. 碰撞仅裁决仿真执行，不喂规划器。

## B. 相机模式

| mode | 行为 |
|------|------|
| `fixed_base` | 位姿相对底盘全固定；LOOK 禁用 |
| `fixed_base_gimbal` | **本轮主对照**：位置固定；`simulated_gimbal` 俯仰 ±30°/步 |
| `legacy_arm_look` | 历史 joint3 LOOK（光心移动）；仅复核旧结果 |

渲染 / `sensor_pose` / 自遮挡共用 `camera_world_matrix()`；odom 仍为真实底盘。

## C. 验证状态

### 运动单测

证据：`/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/exec_collision_camera_test/retest2.json` — `all_ok=true`  
（空旷前进/转向、长距截断、gimbal LOOK 光心漂移 0、查询相交/不相交可分）。

### 冒烟 HY1 / eF36 / yr17（`batch_smoke3_20261116_221049`）

| ep | termination | steps | explore | blocked | trunc | moved_m | init_pen | sr_proxy |
|----|-------------|-------|---------|---------|-------|---------|----------|----------|
| hy1_chair_3 | step_budget_exhausted | 50 | 24 | 15 | 1 | 3.00 | False | False |
| ef36_chair_4 | step_budget_exhausted | 50 | 24 | 19 | 3 | 2.15 | False | False |
| yr17_chair_0 | step_budget_exhausted | 50 | 24 | 26 | 3 | 0.96 | False | False |

说明：blocked 含贴家具时合法拒绝的转向/前进；episode **不再**因单次 blocked 中止。LOOK gimbal 正常。

### 24-ep 回归（合并 `ab24b_20261116_224229` + recovery `ab24b_rec_20261117_071620`）

| 指标 | 值 |
|------|-----|
| 完成 | **24/24** `status=ok` |
| SR_proxy | **0/24** |
| near_goal | 5/24 |
| init_pen episodes | 4/24 |
| termination | step_budget 22 / planner_stop 2 |
| sum moved (ok) | 14.75 m |
| blocked / truncated exec | 681 / 29 |

明细：`ab24_combined_table.md` / `ab24_combined_aggregate.json`。

**归因声明**：本表是碰撞门控 + `fixed_base_gimbal` 新协议基线；**不可**与旧 LabelMap/VIEW_POINTS 重算 8/24 直接对比。高 blocked 表示贴家具转向/前进被合法拒绝；部分 spawn 上环视 TURN 几乎全拒（如 lt9/k1cup），移动距离为 0。

## 代码入口

- `adapters/habitat_rangercr10/src/execution_collision.py`
- `adapters/habitat_rangercr10/src/camera_modes.py`
- `adapters/habitat_rangercr10/src/kinematic_demo.py`
- `adapters/habitat_rangercr10/src/apexnav_real_episode.py`
- `adapters/habitat_rangercr10/scripts/run_exec_collision_baseline_batch.sh`
- `adapters/habitat_rangercr10/scripts/test_execution_collision_camera.py`
