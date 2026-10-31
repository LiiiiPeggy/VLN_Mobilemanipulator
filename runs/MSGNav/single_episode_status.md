# MSGNav single episode status

**Result: FAIL / BLOCKED** (pipeline started; weights load partial; exit 1 before Habitat steps)

| Item | Value |
|------|-------|
| Time | 2026-11-01 01:07–01:08 CST |
| Container | `vln-msgnav` → `vln-habitat025:msgnav-deps` (`24b7c26315a3`) |
| Command | `python run_hm3d_evaluation.py -cf cfg/eval_hm3d_single_ep.yaml --specific 0` |
| Log | `/media/ubuntu/D/VLN_shared/runs/MSGNav/single_episode_20261101_010711.log`（仓库内 `runs/MSGNav/single_episode_latest.log` 软链） |
| Prior attempt | `..._010653.log`（更早失败） |

## What succeeded

- Episode selection: scene 0 → **1 episode**
- `yolov8x-world.pt` load OK
- `sam_l.pt` load OK
- API env: `GPT_MODEL=gpt-5.6-sol` / `API_MODE=gpt`

## Blocker

`open_clip.create_model_and_transforms("ViT-H-14-quickgelu", pretrained="dfn5b")` 尝试从 HuggingFace 拉取：

`apple/DFN5B-CLIP-ViT-H-14` → `open_clip_pytorch_model.bin`

容器内直连 `huggingface.co` → `Network is unreachable`，随后 `RuntimeError: Cannot send a request, as the client has been closed.` → **EXIT:1**。

缓解（进行中 / 待验证）：`HF_ENDPOINT=https://hf-mirror.com` + `HF_HOME=/shared/cache/huggingface` 预拉权重到 D 盘缓存。

## Status mapping

仍为 `DEPENDENCIES_READY`（deps/API 已验）；**未**达 `MODEL_LOADED` / `SINGLE_EPISODE_OK`。
