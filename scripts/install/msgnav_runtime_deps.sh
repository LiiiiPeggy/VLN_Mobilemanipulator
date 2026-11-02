#!/usr/bin/env bash
# MSGNav extras on top of vln-habitat025 base (0.2.5).
# Status: WRITTEN_BACK. Verified working tree committed as
#   vln-habitat025:msgnav-deps = 1b1bdc94f963 (not a clean Dockerfile rebuild).
set -euo pipefail
PIP_INDEX_URL=${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}
PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST:-mirrors.aliyun.com}
export PIP_INDEX_URL PIP_TRUSTED_HOST

pip install 'hipart==1.0.4' 'ollama'
# pytorch3d wheel matching torch 2.0.1+cu118 / py39 (official anaconda package URL)
conda install -y https://anaconda.org/pytorch3d/pytorch3d/0.7.4/download/linux-64/pytorch3d-0.7.4-py39_cu118_pyt201.tar.bz2 || \
  pip install "git+https://github.com/facebookresearch/pytorch3d.git@v0.7.4"

python - <<'PY'
import importlib
for m in ["open_clip","ultralytics","hipart","pytorch3d","openai","habitat_sim","ollama"]:
    try:
        importlib.import_module(m if m!="hipart" else "HiPart")
        print("OK", m)
    except Exception as e:
        # HiPart import name
        try:
            importlib.import_module("HiPart")
            print("OK", m)
        except Exception as e2:
            print("FAIL", m, e2)
PY
