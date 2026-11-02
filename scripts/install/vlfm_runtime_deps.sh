#!/usr/bin/env bash
# Install VLFM runtime deps into an already-running vln-habitat024 container.
# Status: WRITTEN_BACK (script). Clean-image bake still uses docker commit tag
#   vln-habitat024:latest = fe6b1ca643fd until Dockerfile.habitat024-runtime is
#   clean-build verified under an independent tag (see reports/image_repro.md).
set -euo pipefail
PIP_INDEX_URL=${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}
PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST:-mirrors.aliyun.com}
export PIP_INDEX_URL PIP_TRUSTED_HOST

pip install 'spacy==3.5.3' 'salesforce-lavis==1.0.2' 'dash<3'
pip install --no-deps -e /workspace/VLFM
pip install \
  git+https://github.com/naokiyokoyama/frontier_exploration.git \
  git+https://github.com/ChaoningZhang/MobileSAM.git \
  git+https://github.com/naokiyokoyama/depth_camera_filtering \
  git+https://github.com/IDEA-Research/GroundingDINO.git
pip install git+https://github.com/naokiyokoyama/bd_spot_wrapper.git || true

python - <<'PY'
import importlib
for m in ["spacy","lavis","frontier_exploration","mobile_sam","groundingdino","vlfm"]:
    importlib.import_module(m)
    print("OK", m)
PY
