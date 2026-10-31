# MSGNav dependency prep status

Updated: 2026-11-01  
Container: `vln-msgnav` → image `vln-habitat025:msgnav-deps` (`24b7c26315a3`)  
Evidence: imports + path checks + API smoke inside container. **No GPU episode run.**

## Compose / mounts

- Added host-identical mount: `/media/ubuntu/D/VLN_shared:/media/ubuntu/D/VLN_shared` (same pattern as VLFM) so absolute symlinks under `data/` resolve.
- Image pin: `vln-habitat025:msgnav-deps` (runtime extras committed; base `:latest` unchanged for other baselines).
- Recreated **only** `vln-msgnav`.

## Config path fixes (`cfg/eval_hm3d.yaml`)

| Key | Value | Verified |
|-----|-------|----------|
| `scene_dataset_config_path` | `/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/hm3d_annotated_basis.scene_dataset_config.json` | exists |
| `scene_data_path` | `/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d` | `train/` + `val/` |
| `test_data_dir` | `data/objectnav_hm3d_v2_val_content` | 36 plain `.json` |
| `sam_model_name` | `sam_l.pt` | cwd symlink → `.../sam_vit_l_0b3195.pth` |

Notes:
- Upstream yaml pointed at author machine paths; replaced with shared HM3D layout.
- Habitat ObjectNav ship as `.json.gz`; MSGNav `json.load` needs plain JSON → gunzipped copy at  
  `/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2/val/content_json`  
  (symlink `baselines/MSGNav/data/objectnav_hm3d_v2_val_content`).
- Workspace root `sam_l.pt` → `data/sam_l.pt` for UltraLytics `SAM("sam_l.pt")`.

## Python deps

| Package | Status | Notes |
|---------|--------|-------|
| torch 2.0.1+cu118 | OK | base image |
| habitat_sim 0.2.5 | OK | base image |
| omegaconf / open_clip / ultralytics / supervision / open3d / openai / httpx / faiss | OK | base image |
| HiPart 1.0.4 | OK | installed; import name `HiPart` (not used directly in eval scripts) |
| pytorch3d 0.7.4 | OK | conda package `py39_cu118_pyt201`; `pytorch3d.ops` OK |
| ultralytics CLIP (`clip`) | OK | README extra; eval uses `open_clip` |
| ollama | SKIP | `use_ollama: false` |
| segment_anything | N/A | code uses UltraLytics `SAM`, not Facebook SAM |

Warnings (non-blocking for import smoke):
- `habitat-sim` declares `numpy<1.24`; env has `numpy 1.24.3` after extras — `import habitat_sim` still OK.
- CLIP install bumps Pillow to 11.x.

## Env / API smoke

- `GPT_END_POINT=https://model8.run/v1`
- `GPT_MODEL` (local `.env`, gitignored): **`gpt-5.6-sol`** (was `gpt-5.5`)
- Key present (masked in checks only).

| Model | Result |
|-------|--------|
| `gpt-5.5` | FAIL — 404 model_not_found (“not supported by any configured account”) |
| `gpt-5.6-sol` | OK — cheap chat reply `pong` (~24s) |

Compose default fallback also set to `gpt-5.6-sol`.

## Not done (per plan)

- No MSGNav GPU eval / single episode (VLFM VLM servers still hold GPU).
- YOLO-World weight download / MODEL_LOADED not exercised here.

## Next for SINGLE_EPISODE_OK

1. Free GPU from VLFM VLM servers (or schedule off-peak).
2. `python run_hm3d_evaluation.py -cf cfg/eval_hm3d.yaml --start_ratio 0.0 --end_ratio` tiny / specific scene.
3. Confirm `yolov8x-world.pt` resolves (auto-download or shared checkpoint).
