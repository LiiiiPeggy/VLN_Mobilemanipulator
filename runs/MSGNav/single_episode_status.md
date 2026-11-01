# MSGNav single-episode status

Updated: 2026-11-01  
Result: **OK** (pipeline `EXIT:0`; task success=false / miss)

## Command

```bash
# Prep (once): 1-episode content from smallest scene zt1RVoi7PcG (22 eps → 1)
# cfg/eval_hm3d_single_ep.yaml → test_data_dir=data/objectnav_hm3d_single_ep, output=/workspace/runs
docker exec -w /workspace/MSGNav \
  -e HF_HOME=/shared/cache/huggingface \
  -e HUGGINGFACE_HUB_CACHE=/shared/cache/huggingface/hub \
  -e HF_ENDPOINT=https://hf-mirror.com \
  -e PYTHONUNBUFFERED=1 \
  vln-msgnav \
  python -u run_hm3d_evaluation.py -cf cfg/eval_hm3d_single_ep.yaml --specific 0
```

Container: `vln-msgnav` → `vln-habitat025:msgnav-deps`  
`GPT_MODEL=gpt-5.6-sol` / `API_MODE=gpt`

## Evidence

| Item | Path / value |
|------|----------------|
| Primary log | `/media/ubuntu/D/VLN_shared/runs/MSGNav/single_episode_20261101_012834.log` |
| Repo pointer | `runs/MSGNav/single_episode_latest.log` → same |
| Scene | `00839-zt1RVoi7PcG` |
| Episode | 1/1 (ID 0), goal=`chair` |
| Steps | 20 logged (~19 navigation steps) |
| Wall time | ~15 min eval (+ CLIP weight prep earlier) |
| Exit | `EXIT:0` |

## Metrics

| Metric | Value |
|--------|-------|
| success_by_distance | **0.00** |
| SPL_by_distance | **0.00** |
| success (object) | **0.00** |
| SPL (object) | **0.00** |
| Final distance to viewpoint | 5.329 m (threshold 1.0 m) |
| Path length | 16.724 |
| Filtered/total frames | 7/134 |

Verdict: **SINGLE_EPISODE_OK** — Habitat + YOLO/SAM/CLIP + GPT VLM loop completed without crash; episode was a navigation miss (same class of outcome as VLFM false_positive).

## Runtime fixes applied for this run

1. Stopped VLFM VLM servers in `vln-vlfm` (`pkill -f vlfm.vlm`); GPU ~17.6GB → ~5.1GB; container left Up.
2. Installed missing `ollama` Python package in container (import required even when `use_ollama: false`).
3. Prefetched open_clip `ViT-H-14-quickgelu`/`dfn5b` via `HF_ENDPOINT=https://hf-mirror.com` into `/shared/cache/huggingface`.
4. Symlinked `yolov8x-world.pt` → shared checkpoints; UltraLytics also fetched `ViT-B-32.pt` into `/root/.cache/clip/`.

## GPU after run

~5079 MiB used (Isaac Lab / desktop leftovers); MSGNav process released.
