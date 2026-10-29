# Baseline Source Versions

Recorded on A6000 host `ubun` at import time. Upstream remotes were cloned; nested `.git` directories were removed on **2026-10-29** via `scripts/strip_nested_git.py` so sources are managed by the umbrella repo. Machine-readable copy: `reports/source_versions.json`.

| Project | Upstream | Branch | Commit SHA |
|---------|----------|--------|------------|
| VLFM | https://github.com/rai-opensource/vlfm.git | main | `584ed56008754fde7997d904983607def8328322` |
| ApexNav | https://github.com/Robotics-STAR-Lab/ApexNav.git | main | `049971b613fcd2554b034bd4a853d79cc1e61613` |
| MSGNav | https://github.com/ylwhxht/MSGNav.git | main | `03681a178d6993265e838e1fbbaf2338c54e1c62` |
| APRR | https://github.com/qinliangql/APRR.git | main | `046c9c24d688c9b6acd7fc8c52abe1c6c2086e56` |
| SG-Nav | https://github.com/bagh2178/SG-Nav.git | main | `d56863c96dea311aaa67fb0d39a1a8ccc3f0487f` |
| UniGoal | https://github.com/bagh2178/UniGoal.git | main | `e2c6d456d53150db507a008250f50c34798daad5` |

## Nested / vendored notes

- **MSGNav / SG-Nav**: `habitat-lab` is vendored as regular tracked files (not gitlinks).
- **UniGoal**: `third_party/habitat-lab` vendored as regular files.
- **APRR**: wraps `home-robot`; `home-robot/.gitmodules` lists Detic, habitat-lab, detectron2, contact_graspnet, Grounded-SAM, OVMM/HSSD data. `src/third_party/{habitat-lab,detectron2,contact_graspnet}` partially present after clone; data submodules and some detection submodules were **not** fully initialized (deferred for lightweight audit).
- **VLFM**: official `docker/Dockerfile` present; yolov7 must be cloned separately into the tree for detectors.
- **ApexNav Lite**: `Lite-Apexnav` branch noted but not mixed with main results.

## Host snapshot (import)

- GPU: NVIDIA RTX A6000, driver 550.163.01, CUDA 12.4, ~49 GiB VRAM
- OS: Ubuntu 22.04.5, Docker 27.3.1 / Compose v2.29.7
- Disk: root ~338 GiB free; `/media/ubuntu/D` ~1.9 TiB free (preferred for datasets/checkpoints)
