# 大数据 / 权重下载状态

更新：2026-10-29 晚。共享根：`/media/ubuntu/D/VLN_shared/`

## 已就绪（公开资源，无需 Matterport）

| 资源 | 大小 | 路径 |
|------|------|------|
| GroundingDINO | ~662MB | `checkpoints/grounding_dino/`（复用 NBV） |
| MobileSAM | 39MB | `checkpoints/mobile_sam/mobile_sam.pt` |
| YOLOv7-e6e | 291MB | `checkpoints/yolov7/yolov7-e6e.pt` |
| PointNav / Spot | ~34MB×2 | `checkpoints/pointnav/` |
| CLIP ViT-H | — | `checkpoints/clip/`（复用 DovSG） |
| SAM2 hiera large | 857MB | `checkpoints/sam2/`（复用 NBV） |
| **SAM ViT-H** | **2.4GB** | `checkpoints/sam/sam_vit_h_4b8939.pth` |
| **ObjectNav HM3D v1** | 解压后 ~133MB | `datasets/objectnav/hm3d/v1/`（含 val） |
| **ObjectNav HM3D v2** | 解压后 ~249MB | `datasets/objectnav/hm3d/v2/`（含 val/val_mini） |
| **ObjectNav MP3D v1** | 解压后 ~173MB | `datasets/objectnav/mp3d/` |
| **InstanceImageNav HM3D v3** | zip 514MB | `datasets/instance_imagenav/hm3d/` |
| VLFM/ApexNav 代码依赖 | — | `baselines/VLFM/yolov7`、`baselines/ApexNav/{yolov7,GroundingDINO}` |

软链：VLFM→objectnav v1，ApexNav→v2，SG-Nav/UniGoal→sam_h + groundingdino。

## 公开资源补充完成

| 资源 | 大小 | 路径 |
|------|------|------|
| **GLIP large** | **6.42 GiB** (6896153761 B) | `checkpoints/glip/glip_large_model.pth` |
| **YOLOv8x-worldv2** | 140MB | `checkpoints/yolo_world/yolov8x-worldv2.pt`（`yolov8x-world.pt` 软链） |

## 公开下载失败（需换源或稍后重试）

### SAM ViT-L（MSGNav `sam_l.pt`）— 已就绪

- 文件：`checkpoints/sam/sam_vit_l_0b3195.pth`（1249524607 B）
- 别名：`checkpoints/sam/sam_l.pt` → 上述文件

## 仍需你处理（授权 / 权限）

### ObjectNav HM3D v2 权限（可选）

若 `verify_shared_assets.sh` 提示 `index not readable`，在宿主机执行：

```bash
sudo chmod -R a+rX /media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2
sudo chown -R "$USER:$USER" /media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2
```

### 其它可选

- APRR 百度权重：**已就位**（`checkpoints/aprr/` + `baselines/APRR/home-robot/ckpt/` 软链）
- UniGoal text-goal（Google Drive）
- SG-Nav 用的 **MP3D 场景网格**（需 Niessner 授权；episodes 已下）

## 校验

```bash
bash scripts/verify_shared_assets.sh
# 期望：ok=11 miss=0（软链按目标大小计；ObjectNav 看 content/）
```
