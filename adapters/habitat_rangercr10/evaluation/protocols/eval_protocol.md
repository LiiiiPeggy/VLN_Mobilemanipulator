# Ranger 分类评测协议（v0.1）

更新：2026-11-16  
平台：Habitat + **0.7×** RangerBox-CR10 代理（`scaled_robot_proxy_070`）。**不得**称为真实尺寸实机结果。  
本轮优先：**ApexNav** 部署评估；不并行铺开六套大规模实验。

## 1. 清单与预算

| 清单 | 角色 | 路径 |
|------|------|------|
| dev24 | 开发回归 | `lists/dev24_regression_ref.json` ← `reports/startup_prior_e2e_20261107/episode_list.json` |
| independent_v1 | 独立测试 | `lists/independent_test_list_v1.json`（六类各 ≤20，不重复实例凑数） |

- **同一清单、同一 spawn 门禁、同一预算**用于所有算法 / 相机模式对照。
- 合法 spawn 与任务可行性检查 **独立于算法成绩**；不得删除某算法失败样本以提高 SR。
- 运行失败 / 超时 / 无效 spawn **分别记账**，禁止静默丢弃。
- 不靠加大单 episode 预算代替增加样本量。
- 与 dev24 的场景/实例重合必须披露，禁止宣称虚假独立性。

## 2. 类别层级

- **具体类别**（计分单元）：`chair / bed / sofa / plant / toilet / tv_monitor`（及未来独立建设的 `cup` 等）。
- **汇总分组**（仅报告）：`large_furniture`、`small_object`。分组 **不与子类重复计入** 总体 micro SR。
- ObjectNav plant 为室内盆栽尺度，归入 `large_furniture` 分组，**不是**小物体。

## 3. 观测条件（可标注分层，非选题偏置）

在类别之外记录（可后标；缺省记 `unknown`）：

| 字段 | 含义 |
|------|------|
| `goal_height_bin` | low / mid / high（相对地板） |
| `apparent_scale_bin` | 初始可见像素或投影尺度：small / mid / large |
| `occlusion_bin` | none / partial / heavy |
| `multi_instance_ambiguity` | false / true |
| `control_unoccluded` | 普通无遮挡控制组标记 |

**禁止**先挑「只有机械臂能成功」的案例再推广到全体任务。

## 4. 成功与指标

| 指标 | 定义 |
|------|------|
| `SR_proxy` | `planner_stop ∧` 底盘到最近 **VIEW_POINTS** 水平距 ≤ 1.0 m |
| micro SR | 全部具体类 episode 合计 |
| macro SR | 各类 SR 的未加权平均 |
| 置信区间 | Wilson 95%（脚本 `wilson_ci.py`） |
| 错误停止率 | `planner_stop` 且未成功 / n |
| 效率 | 步数、墙钟、底盘 `forward_m`、有效观测次数 |
| 臂代价 | 臂运动次数/时间、执行碰撞/异常（由日志字段提供） |
| SPL | **不报**（无与 Ranger 足迹匹配的 geodesic） |
| 检测 precision | 与导航 SR **分列**，禁止混称「精度」 |

配对：同一 `episode_list_id` 跨方法做配对表；重复种子单独标记，解释场景相关不确定性。

## 5. 两层对照

### 5.1 算法部署对照

同一 Ranger 与执行规则；各方法保留自身相机能力：

- VLFM：固定位置与朝向  
- ApexNav：固定安装高度，允许云台俯仰  

须披露：相机安装、动作空间、观测次数、模型版本。**不声称**观测动作空间完全一致。

### 5.2 机械臂收益对照（同一 ApexNav 骨干）

| 臂 | 含义 | 本轮状态 |
|----|------|----------|
| **A** | 固定位置云台相机 | 先建立可信基线（等 Cursor A 冻结执行/日志） |
| **B** | 后续规则机械臂观察 | 协议冻结；实现跟 A |
| **C** | 后续主动观察方法 | 协议冻结；不凭空实现未定义算法 |

若增加「目标可见性 / 确认」指标：必须对 A/B/C **一致定义**，并与导航 `SR_proxy` **分列**；**不得**把「动臂」本身当作成功条件。

## 6. 与 Cursor A 的衔接

见 `field_requests_for_cursor_a.md`。A 冻结 `camera_mode` 与日志后：固定版本 → 少样本核对 → 再跑 independent_v1。共享 GPU/ROS 先排队；不跨执行器版本混合汇总。
