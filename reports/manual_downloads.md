# 需手动下载的大文件 / 授权数据

盘点时间：2026-10-29（A6000）。以下文件**本机未找到**或需授权，请按路径放入后告知，我会校验并继续仿真。

共享根目录：`/media/ubuntu/D/VLN_shared/`  
工作空间软链：`shared/datasets_large` → 上述 datasets，`shared/checkpoints_large` → checkpoints。

---

## 已就绪（无需再下）

| 资源 | 来源 / 状态 | 共享路径 |
|------|-------------|----------|
| GroundingDINO SwinT OGC (~662MB) | 复用 NBV | `.../checkpoints/grounding_dino/groundingdino_swint_ogc.pth` |
| PointNav / Spot PointNav (~34MB×2) | VLFM 仓内 | `.../checkpoints/pointnav/` |
| CLIP ViT-H（可选） | 复用 DovSG | `.../checkpoints/clip/` |
| MobileSAM (~39MB) | **已下载** | `.../checkpoints/mobile_sam/mobile_sam.pt` |
| YOLOv7-e6e (~291MB) | **已下载** | `.../checkpoints/yolov7/yolov7-e6e.pt` |

---

## 1. 仍缺的视觉权重

保存到：`/media/ubuntu/D/VLN_shared/checkpoints/`

### 1.1–1.2 MobileSAM / YOLOv7

**已完成，可跳过。**

### 1.3 MSGNav 检测权重（若跑 MSGNav 完整仿真）

- `yolov8x-world.pt`：Ultralytics 首次运行常自动拉取；也可预先：

```bash
mkdir -p /media/ubuntu/D/VLN_shared/cache/ultralytics
# 容器内或本机有 ultralytics 时：
# yolo predict model=yolov8x-world.pt source=bus.jpg
```

- `sam_l.pt`（Segment Anything Large，约 **1.2 GB**）  
  常用：https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3192.pth  
  保存为：`/media/ubuntu/D/VLN_shared/checkpoints/sam/sam_vit_l_0b3192.pth`  
  （MSGNav 配置写 `sam_l.pt`，放入后我会按官方命名做软链。）

```bash
mkdir -p /media/ubuntu/D/VLN_shared/checkpoints/sam
cd /media/ubuntu/D/VLN_shared/checkpoints/sam
wget -c -O sam_vit_l_0b3192.pth \
  https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3192.pth
ln -sfn sam_vit_l_0b3192.pth sam_l.pt
```

---

## 2. Habitat 任务 Episode（公开，无 Matterport 账号也可下）

保存到：`/media/ubuntu/D/VLN_shared/datasets/objectnav/`

### 2.1 HM3D ObjectNav v1（VLFM 常用）

- 压缩包约 **数百 MB 级**（以下载页为准）
- URL：https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v1/objectnav_hm3d_v1.zip

```bash
mkdir -p /media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d
cd /media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d
wget -c -O v1.zip \
  https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v1/objectnav_hm3d_v1.zip
unzip v1.zip && mv objectnav_hm3d_v1 v1 && rm v1.zip
```

### 2.2 HM3D ObjectNav v2（ApexNav / MSGNav 常用）

- URL：https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v2/objectnav_hm3d_v2.zip

```bash
cd /media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d
wget -c -O v2.zip \
  https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v2/objectnav_hm3d_v2.zip
unzip v2.zip && mv objectnav_hm3d_v2 v2 && rm v2.zip
```

优先下 **v1 + v2 的 `val` / `val_mini`** 即可；训练 split 本轮不需要。

---

## 3. HM3D 场景网格（必须授权，本机未找到）

**阻塞官方 ObjectNav 闭环仿真的关键数据。**

- 申请：https://matterport.com/habitat-matterport-3d-research-dataset  
- 本轮最小集：**HM3D val v0.2**（habitat 格式）
- 官方包名示例：`hm3d-val-habitat-v0.2.tar`（体积约 **数十 GB 级**，以 Matterport 页面为准）
- 保存并解压到：

```text
/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/
```

参考命令（拿到 tar 或 Matterport token 后）：

```bash
# 方式 A：已有 tar
mkdir -p /media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val
cd /media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val
tar -xvf /path/to/hm3d-val-habitat-v0.2.tar

# 方式 B：有 MATTERPORT_TOKEN_ID / SECRET
export MATTERPORT_TOKEN_ID=...
export MATTERPORT_TOKEN_SECRET=...
# 在已安装 habitat-sim 的环境中：
python -m habitat_sim.utils.datasets_download \
  --username "$MATTERPORT_TOKEN_ID" \
  --password "$MATTERPORT_TOKEN_SECRET" \
  --uids hm3d_val_v0.2 \
  --data-path /media/ubuntu/D/VLN_shared/datasets
```

解压后期望能看到类似 `00800-TEEsavR23oF/` 等场景目录，以及 `hm3d_annotated_basis.scene_dataset_config.json`（MSGNav 已自带一份 config 模板）。

若你只有 **1–2 个 val 场景** 的子集，也可先放到上述 `val/` 下，我按可用 scene_id 裁剪 episode 做小批量测。

---

## 4. GOAT-Bench（仅 MSGNav GOAT 入口需要，可后补）

- 参考：https://github.com/Ram81/goat-bench  
- 保存建议：`/media/ubuntu/D/VLN_shared/datasets/goatbench/`  
- 本轮可先只做 HM3D ObjectNav；GOAT 暂缓。

---

## 5. API 凭证（MSGNav / 部分 LLM 路径）

本机未发现可用的 `OPENAI` / `DASHSCOPE` / `QWEN` 环境变量。  
MSGNav 的 `src/const.py` 目前仍是占位符。若要用官方 LLM 决策：

- 将密钥放到**仅本地**的 `baselines/MSGNav/.env`（已在 `.gitignore`），或运行前 `export`，**不要提交 GitHub**。
- 无密钥时：继续做本地检测 / 建图 / 容器与入口审计，不静默调用付费 API。

---

## 请你优先处理（按阻塞程度）

| 优先级 | 内容 | 约大小 | 保存路径 |
|--------|------|--------|----------|
| **P0** | HM3D val v0.2 场景（Matterport 授权） | 数十 GB | `/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val/` |
| **P1** | ObjectNav HM3D v1 + v2 episode zip（公开） | 各约数百 MB–数 GB | `/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/` |
| P2 | MSGNav `sam_l.pt` / SAM ViT-L | ~1.2 GB | `.../checkpoints/sam/` |
| P2 | APRR 百度权重 | 未知 | `.../checkpoints/aprr/`（密码 `uw53`） |
| P3 | SG-Nav：MP3D 场景 + GLIP；UniGoal text-goal zip | 视授权 | 见上文各节 |

若有 Matterport `TOKEN_ID` / `SECRET`，也可只把凭证给我（本地 env，勿提交），由我在容器内用 `habitat_sim.utils.datasets_download` 拉 **val** 子集。

## 下载完成后请告知

我会执行 `bash scripts/verify_shared_assets.sh`，校验后继续 VLFM → ApexNav → MSGNav 单 episode。  
期间继续：正式 Habitat 镜像构建、轻量审计深化、接口分析、Git 提交推送。
