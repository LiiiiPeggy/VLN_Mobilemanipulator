# habitat024 build status

Updated: 2026-10-31 (Asia/Shanghai)

## Result: **OK** (base image + VLFM recreate + smoke + runtime deps)

| Item | Value |
|------|-------|
| Build exit | `0` |
| Image | `vln-habitat024:build` = `vln-habitat024:latest` |
| Image ID | `7a81efa03898` |
| Size | **17.9GB** |
| Smoke | `0.2.4 1.12.1+cu113 True` |
| Container | `vln-vlfm` recreated on formal image (Up) |
| nbv_* | untouched (`nbv_fkie` still Up) |

### Smoke command
```text
docker exec vln-vlfm python -c "import habitat_sim,habitat,torch; print(habitat_sim.__version__, torch.__version__, torch.cuda.is_available())"
# -> 0.2.4 1.12.1+cu113 True
```

### VLFM runtime deps (inside `vln-vlfm`)
- `spacy==3.5.3`, `salesforce-lavis==1.0.2` installed
- `pip install --no-deps -e /workspace/VLFM`
- git: frontier_exploration, MobileSAM, depth_camera_filtering, GroundingDINO, bd_spot_wrapper
- Import check: **OK** spacy / lavis / frontier_exploration / mobile_sam / groundingdino / vlfm
- Log: `/media/ubuntu/D/VLN_shared/runs/VLFM/vlfm_runtime_deps.log`

### Logs
- `/home/ubuntu/locomani/VLN_Mobilemanipulator/runs/_build/habitat024_retry.log`
- `/media/ubuntu/D/VLN_shared/runs/_build/habitat024_retry.log` (copy)

### Dockerfile notes
- Aliyun apt + empty proxy env (pre-existing)
- Added Aliyun PyPI index for pip layers (open3d 420MB was ~50KB/s on files.pythonhosted.org)
- No salesforce-lavis in base image (as intended)

## habitat025 (background)

| Item | Value |
|------|-------|
| First attempt | **FAIL** exit 1 — apt hit broken LAN proxy `172.31.247.35:8081` (hash/size mismatch) |
| Fix | Applied same Aliyun apt + empty proxy + Aliyun pip pattern as 024 |
| Rebuild | running via container `vln-go025b` (`0cfcd46bc066`) |
| Host PID | `2599080` (`docker build ... Dockerfile.habitat025`) |
| Log | `runs/_build/habitat025_build.log` (+ D: `.../VLN_shared/runs/_build/`) |
| Progress at status write | past apt/conda; downloading torch/triton wheels |

## Next blocker
1. Wait for `vln-habitat025:build` to finish; then tag `:latest` and recreate MSGNav/SG-Nav/UniGoal containers as needed.
2. VLFM single-episode still blocked on VLM service / eval launch (image+deps no longer the blocker).
3. Optional: habitat-baselines pip may have bumped numpy to 1.26.4 inside 024 image — smoke OK; watch for habitat-lab quirks.
