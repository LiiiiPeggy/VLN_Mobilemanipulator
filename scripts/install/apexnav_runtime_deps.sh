#!/usr/bin/env bash
# ApexNav runtime layer on top of vln-apexnav:build (habitat-sim 0.3.1).
# Status: WRITTEN_BACK as operational notes + this script. Working image:
#   vln-apexnav:single-ep-deps = 50e76a268b26 (docker commit after ROS/VLM install).
# Clean rebuild of ROS-in-Jammy is NOT claimed; prefer dedicated ros:noetic base later.
set -euo pipefail
PIP_INDEX_URL=${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}
PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST:-mirrors.aliyun.com}
export PIP_INDEX_URL PIP_TRUSTED_HOST

# Keep habitat-sim ABI happy
pip install --force-reinstall --no-deps 'numpy==1.23.5' 'numba==0.60.0'
pip install 'opencv-python==4.8.1.78' 'transformers==4.26.1' 'salesforce-lavis==1.0.2' 'dash<3'
pip install git+https://github.com/IDEA-Research/GroundingDINO.git \
  git+https://github.com/ChaoningZhang/MobileSAM.git

echo "NOTE: ROS Noetic + catkin exploration_node must be provisioned separately"
echo "  (copy from nbv-fkie:noetic IMAGE only; never stop running nbv_* containers)."
echo "  Then: source /opt/ros/noetic/setup.bash && catkin_make in ApexNav workspace."

python - <<'PY'
import numpy,torch
print("numpy", numpy.__version__, "torch", torch.__version__)
assert numpy.__version__.startswith("1.23"), numpy.__version__
PY
