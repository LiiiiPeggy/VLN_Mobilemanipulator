# ApexNav formal image rebuild — 2026-11-01

## Result

- **EXIT:0**
- Image: `vln-apexnav:build` = `vln-apexnav:latest` = `118284656358` (**24.2GB**)
- Full id: `sha256:1182846563587b84cd56972b972c0e71c8dd93cbe8786ebf607773d8c2e6ab57`
- Container: `vln-apexnav` recreated from `:latest`, Up
- Smoke: `1.23.5 0.3.1 2.5.0+cu121 True`
- Status: **DEPENDENCIES_READY** (core imports OK; ApexNav app weights/VLM not exercised)

## Fixes applied

1. Pin `numpy==1.23.5` after habitat-lab/baselines (habitat-sim 0.3.1 needs `numpy<1.24`).
2. First rebuild FAIL: GitHub `git clone` TLS (`GnuTLS -110`). Switched to local release tarball `shared/docker/_cache/habitat-lab-v0.3.1.tar.gz` (gitignored).
3. Second attempt FAIL: `habitat-baselines` deps bumped numpy → numba/`numpy._core` import break. Final fix: `pip install -e habitat-baselines --no-deps`, manual deps with `moviepy==1.0.3`, then `--force-reinstall --no-deps numpy==1.23.5 numba==0.60.0`.

## Evidence

- Log: `runs/_build/apexnav_rebuild.log` (also `/media/ubuntu/D/VLN_shared/runs/_build/apexnav_rebuild.log` if copied)
- Dockerfile: `shared/docker/Dockerfile.apexnav`
