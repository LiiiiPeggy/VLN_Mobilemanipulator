#!/bin/bash
set -euo pipefail
LOG=/workspace/runs/vlfm_runtime_deps.log
mkdir -p /workspace/runs
exec > >(tee -a "$LOG") 2>&1
echo "RETRY_START $(date -Is)"
PIP_I=(-i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com)
# Already attempted: spacy + lavis. Re-ensure pins.
pip install "${PIP_I[@]}" 'spacy==3.5.3' 'salesforce-lavis==1.0.2'
# Install VLFM without pulling git deps from setup metadata; then add them explicitly.
pip install "${PIP_I[@]}" --no-deps -e /workspace/VLFM
retry_pip_git() {
  local url="$1"
  local n=0
  until pip install "$url"; do
    n=$((n+1))
    if [ "$n" -ge 5 ]; then
      echo "FAIL after retries: $url"
      return 1
    fi
    echo "retry $n: $url"
    sleep $((n*5))
  done
}
retry_pip_git 'git+https://github.com/naokiyokoyama/frontier_exploration.git'
retry_pip_git 'git+https://github.com/ChaoningZhang/MobileSAM.git'
retry_pip_git 'git+https://github.com/naokiyokoyama/depth_camera_filtering'
retry_pip_git 'git+https://github.com/IDEA-Research/GroundingDINO.git'
pip install 'git+https://github.com/naokiyokoyama/bd_spot_wrapper.git' || echo "WARN: bd_spot_wrapper skipped"
# Install remaining non-git VLFM requirements if any (ignore git+ lines already handled)
if [ -f /workspace/VLFM/requirements.txt ]; then
  grep -vE '^\s*#|git\+|frontier|MobileSAM|GroundingDINO|depth_camera|bd_spot|yolov7' /workspace/VLFM/requirements.txt \
    | pip install "${PIP_I[@]}" -r /dev/stdin || true
fi
python - <<'PY'
import importlib
for m in ["spacy","lavis","frontier_exploration","mobile_sam","groundingdino","vlfm"]:
    try:
        importlib.import_module(m)
        print("OK", m)
    except Exception as e:
        print("FAIL", m, type(e).__name__, e)
PY
echo "END $(date -Is)"
