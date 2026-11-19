# 桌面物品识别确认（固定云台 vs 机械臂相机）

- 基线：`16a541f`；结果：`reports/tabletop_views_pilot/evaluation_real_v1/`（旧 `evaluation/` 未覆盖）
- 检测：生产 `get_object`（YOLOv7+MobileSAM）；`cup|bowl|remote|bottle`；`similar_answer=[]`；conf=0.3
- 别名：`decorative bowl → bowl`，`bottle of detergent → bottle`
- 共采集 **12** 件；可评分 **9** 件；另 **3** 件缺可用于确认指定目标的标注
- 视角评分：**54** 条；无缺文件、无推理失败
- 9 个可评分实例共同起始画面均已可见；本批检验换视角能否帮助识别确认

## 主表（组会用）

| 类别 | 可评分实例数 | 固定云台识别成功数 | 机械臂相机识别成功数 | 仅固定云台认出 | 仅机械臂认出 |
|------|-------------:|-------------------:|---------------------:|---------------:|-------------:|
| 杯子 | 3 | 1 | 0 | 1 | 0 |
| 碗 | 3 | 0 | 0 | 0 | 0 |
| 遥控器 | 2 | 0 | 0 | 0 | 0 |
| 瓶子 | 1 | 0 | 0 | 0 | 0 |
| 总体 | 9 | 1 | 0 | 1 | 0 |

## 逐实例

| 实例 | 类别 | 固定云台 | 机械臂 | 四格 | 说明 |
|------|------|----------|--------|------|------|
| `CrMo8WxCyVb_cup_423` | 杯子 | 未认出 | 未认出 | neither | 两侧可见视角均为漏检 |
| `a8BtkwhxdRV_cup_598` | 杯子 | 未认出 | 未认出 | neither | 两侧可见视角均为漏检 |
| `bxsVRursffK_cup_381` | 杯子 | 成功 | 未认出 | fixed_only | 固定 view_01 命中 (IoU=0.883)；臂侧可见但漏检 |
| `5cdEh9F2hJL_bowl_395` | 碗 | 未认出 | 未认出 | neither | 两侧可见视角均为漏检 |
| `7MXmsvcQjpJ_bowl_791` | 碗 | 未认出 | 未认出 | neither | 两侧可见视角均为漏检 |
| `eF36g7L6Z9M_bowl_161` | 碗 | 未认出 | 未认出 | neither | 两侧可见视角均为漏检 |
| `QaLdnwvtxbs_remote_189` | 遥控器 | 未认出 | 未认出 | neither | 两侧可见视角均为漏检 |
| `y9hTuugGdiq_remote_232` | 遥控器 | 未认出 | 未认出 | neither | 臂侧同类别检出但 IoU=0（认成旁边同类）；整体未认出 |
| `7MXmsvcQjpJ_bottle_389` | 瓶子 | 未认出 | 未认出 | neither | 两侧可见视角均为漏检 |

## 差异叠图

- `cases/bxsVRursffK_cup_381__fixed_hit_view_01.png`：固定云台认对
- `cases/bxsVRursffK_cup_381__arm_miss_view_00.png`：机械臂漏检（目标仍可见）
- `cases/y9hTuugGdiq_remote_232__other_instance_arm_ee_view_01.png`：机械臂认成旁边同类

## 产物

- `tables/frames_reliable.jsonl` / `instances_reliable.jsonl` / `meeting_table.json`
- `overlays/`（54 视角）
- `configs/locked_detector_config.json`
