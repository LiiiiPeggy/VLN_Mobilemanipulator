# 小目标 / 杯子数据可行性

## ObjectNav 官方目标

HM3D ObjectNav v2 val 仅六类：`['bed', 'chair', 'plant', 'sofa', 'toilet', 'tv_monitor']`。**无 cup/mug 目标、无对应 view_points 协议。**

## 语义几何（只读审计）

- ObjectNav 36 景中含 cup/mug 类语义标签的场景数：**8**。
- 标签计数：`{'coffee mug': 5, 'cup': 7, 'mug': 6, 'pen cup': 2}`。
- 有网格语义 ≠ 有可评测任务（缺官方 goals / viewpoints / 成功判据）。

## 结论

NOT_TASK_READY: semantic instances exist in a minority of val scenes, but HM3D ObjectNav v2 provides neither cup goals nor view_points. Do not treat adding a category string as a new task. A separate minimal data-construction proposal is required (instance IDs, view_points or EE confirmation envelope, spawn checks).

## 若要建设（最小方案，待立项）

- Enumerate semantic instance IDs for cup/mug in selected scenes (read-only).
- Define evaluable goal: either hand-authored view_points near instance, or an EE/camera observability envelope — not base-only ObjectNav radius alone.
- Do not insert foreign meshes into HM3D; prefer existing semantic geometry.
- Keep cup tasks out of the 120-ep ObjectNav independent list until goals exist.
- Observation-condition labels (height/occlusion/ambiguity) must be annotatable on the same instances before claiming arm benefit.

