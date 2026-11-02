# 大数据 / 权重下载状态

更新：2026-11-02。共享根：`/media/ubuntu/D/VLN_shared/`  
范围约定：**不下载跨楼层专用数据集**；MP3D 以现有 **11 个 val 场景**为准，不再扩全库。

## 已就绪

| 资源 | 路径 | 备注 |
|------|------|------|
| GroundingDINO / MobileSAM / YOLOv7 / PointNav / CLIP / SAM2 | `checkpoints/...` | 含 NBV/DovSG 复用 |
| SAM ViT-H / SAM ViT-L（`sam_l.pt`） | `checkpoints/sam/` | |
| GLIP large / YOLOv8x-worldv2 | `checkpoints/glip/`、`checkpoints/yolo_world/` | |
| ObjectNav HM3D v1/v2、MP3D episodes | `datasets/objectnav/` | |
| HM3D 场景 | `datasets/scene_datasets/hm3d/` | |
| MP3D val 场景（11 栋 + `.glb`） | `datasets/scene_datasets/mp3d/` | 对齐 `objectnav/mp3d/val`；**够用，不再下全量** |
| InstanceImageNav HM3D v3 | `datasets/instance_imagenav/hm3d/instance_imagenav_hm3d_v3/` | 权限已 `a+rX`；val content=36、episodes=1000 |
| UniGoal text-goal | `datasets/textnav/val/val_text.json.gz` | 2026-11-02 重下；`episodes=[]` **正常**；795 条 `attribute_data` 与 IIN `goal_key` 对齐 |
| APRR 百度权重 | `checkpoints/aprr/` | |

软链：VLFM→objectnav v1，ApexNav→v2，SG-Nav/UniGoal→sam_h + groundingdino。

## UniGoal 路径约定（接线时）

- 官方期望 `.../instance_imagenav/hm3d/v3/`；磁盘目录名为 `instance_imagenav_hm3d_v3`。接线时建软链即可：  
  `ln -sfn instance_imagenav_hm3d_v3 .../hm3d/v3`
- text-goal **不自带 episodes**：跑 `--goal_type text` 时仍加载 InstanceImageNav 任务，再用 `attribute_data[episode.goal_key]` 取文本（`goal_key`=`{scene}_{goal_object_id}`）。

## 可选权限修复

若 `verify_shared_assets.sh` 提示 ObjectNav v2 `index not readable`：

```bash
sudo chmod -R a+rX /media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2
```

## 校验

```bash
bash scripts/verify_shared_assets.sh
# 期望：ok=11 miss=0（软链按目标大小计；ObjectNav 看 content/）
```

**公开大数据下载清单：当前无强制待办。** 剩余是 baseline 环境对齐与评测接线，不是缺文件。
