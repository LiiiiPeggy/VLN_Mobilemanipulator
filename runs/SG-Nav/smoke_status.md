# SG-Nav ObjectNav smoke — SINGLE_EPISODE_OK

更新：2026-11-07 14:43（UTC+8）

## 证据

- 运行：`runs/SG-Nav/smoke_20261107_143201_host/`（`driver.log`、`results.txt`；容器侧同 stamp 目录为 root 属主）
- 启动：`scripts/run_sgnav_smoke.sh`（`SGNAV_NUM_EPISODES=1`, `SPLIT_L=0`, `SPLIT_R=1`）
- 场景：MP3D `2azQ1b91cZZ`；goal=`cabinet`
- 指标（1 ep）：`success=0.0`，`spl=0.0`，`softspl=0.0`，`distance_to_goal≈11.06`

## 本轮修复（相对此前 BLOCKED）

1. **BERT 离线**：GLIP / GroundingDINO / scenegraph 走 `BERT_BASE_UNCASED_PATH`
2. **MP3D navmesh**：仅有 `.glb` 时 `geodesic_distance` 会 segfault → 已为 11 景重算 `.navmesh`（`scripts/build_mp3d_navmeshes.py`）
3. **pytorch3d**：容器内安装 `0.7.4`（cu118 / torch 2.0.1）供 3D IoU
4. **VLM `image_url`**：改为 OpenAI 兼容 `{"url": "data:..."}`；超时重试
5. **冒烟 cap**：`SGNAV_NUM_EPISODES` + smoke 脚本 `pipefail`

## 论文对照（未宣称复现）

| 协议 | 论文 | 本地 |
|------|------|------|
| MP3D ObjectNav val | SR≈40.2 / SPL≈16.0 | **1 ep smoke** success=0（不足统计） |

下一步：小批量（如 20 ep / 11 景）再对照；官方 navmesh 与自算 navmesh 可能有 SPL 偏差。
