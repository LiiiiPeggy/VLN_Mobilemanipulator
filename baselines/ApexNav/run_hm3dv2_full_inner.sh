#!/usr/bin/env bash
# ################################
# Inside vln-apexnav: HM3D-v2 full val (1000 ep) paper-scale ApexNav reproduction.
# Paper target (ApexNav Table I): HM3Dv2 SR 76.2% / SPL 38.0%.
# Isolated ROS master :11313 (avoid NBV :11311 and Ranger :11312).
# Failure labels: check_failure() → record.txt "success or not: ...".
# ################################
set -eo pipefail
STAMP="${APEXNAV_FULL_STAMP:-$(date +%Y%m%d_%H%M%S)}"
OUT="${APEXNAV_FULL_OUT:-/media/ubuntu/D/VLN_shared/runs/ApexNav/hm3dv2_full_${STAMP}}"
VLM_LOG="$OUT/vlm_servers"
VIDEO_DIR="$OUT/videos_hm3dv2_val"
mkdir -p "$OUT" "$VLM_LOG" "$VIDEO_DIR"
printf '%s\n' "$OUT" > "$OUT/out_path.txt"

cd /workspace/ApexNav
export ROS_DISTRO=noetic
export ROS_MASTER_URI=http://127.0.0.1:11313
export ROS_IP=127.0.0.1
export ROS_HOSTNAME=127.0.0.1
export HF_HOME=/shared/cache/huggingface
export TRANSFORMERS_CACHE=/shared/cache/huggingface
export TORCH_HOME=/shared/cache/torch
export TRANSFORMERS_OFFLINE=1
export HF_HUB_OFFLINE=1

set +u
source /opt/ros/noetic/setup.bash
source /workspace/ApexNav/devel/setup.bash
set -u

pkill -f "roscore -p 11313" 2>/dev/null || true
# Only kill exploration tied to this eval if previously started with our log marker.
sleep 1

nohup roscore -p 11313 > "$VLM_LOG/roscore_11313.log" 2>&1 &
sleep 3

nohup bash -lc "
  source /opt/ros/noetic/setup.bash
  source /workspace/ApexNav/devel/setup.bash
  export ROS_MASTER_URI=http://127.0.0.1:11313 ROS_IP=127.0.0.1 ROS_HOSTNAME=127.0.0.1
  roslaunch exploration_manager exploration.launch
" > "$VLM_LOG/expl.log" 2>&1 &
sleep 6

# Container-local VLM ports 12181-84 (namespace isolated from host Ranger VLMs).
pkill -f "python -u -m vlm.detector.grounding_dino" 2>/dev/null || true
pkill -f "python -u -m vlm.itm.blip2itm" 2>/dev/null || true
pkill -f "python -u -m vlm.segmentor.sam" 2>/dev/null || true
pkill -f "python -u -m vlm.detector.yolov7" 2>/dev/null || true
sleep 2
nohup python -u -m vlm.detector.grounding_dino --port 12181 > "$VLM_LOG/gdino_12181.log" 2>&1 &
nohup python -u -m vlm.itm.blip2itm --port 12182 > "$VLM_LOG/blip2_12182.log" 2>&1 &
nohup python -u -m vlm.segmentor.sam --port 12183 > "$VLM_LOG/sam_12183.log" 2>&1 &
nohup python -u -m vlm.detector.yolov7 --port 12184 > "$VLM_LOG/yolov7_12184.log" 2>&1 &

echo "waiting for VLM ports 12181-84..."
ready=0
for i in $(seq 1 180); do
  ok=0
  for p in 12181 12182 12183 12184; do
    if python -c "import socket;s=socket.socket();s.settimeout(0.5);s.connect(('127.0.0.1',$p));s.close()" 2>/dev/null; then
      ok=$((ok+1))
    fi
  done
  if [ "$ok" = "4" ]; then
    echo "VLM ports up after ${i} checks"
    ready=1
    break
  fi
  sleep 2
done
if [ "$ready" != "1" ]; then
  echo "ERROR: VLM ports not ready" >&2
  tail -n 80 "$VLM_LOG"/*.log || true
  exit 1
fi

echo "===== START habitat_evaluation hm3dv2 full val =====" | tee "$OUT/driver.log"
echo "OUT=$OUT PAPER_TARGET_SR=76.2 PAPER_TARGET_SPL=38.0" | tee -a "$OUT/driver.log"
START=$(date +%s)

set +e
python -u habitat_evaluation.py --dataset hm3dv2 \
  test_epi_num=-1 \
  need_video=false \
  "video_output_path=${VIDEO_DIR}" \
  >"$OUT/habitat_evaluation.log" 2>&1
EC=$?
set -e
END=$(date +%s)
echo "EXIT=$EC WALL_S=$((END-START))" | tee -a "$OUT/driver.log"

python3 - <<PY
import json, re
from collections import Counter
from pathlib import Path
out = Path("$OUT")
rec = out / "videos_hm3dv2_val" / "record.txt"
failures = Counter()
episodes = []
if rec.is_file():
    blocks = re.split(r"(?=Scene ID: )", rec.read_text())
    for b in blocks:
        if "Scene ID:" not in b:
            continue
        m_scene = re.search(r"Scene ID:\s*(\S+)", b)
        m_ep = re.search(r"Episode ID:\s*(\S+)", b)
        m_res = re.search(r"success or not:\s*(.+)", b)
        m_lab = re.search(r"target to find is\s*(.+)", b)
        m_no = re.search(r"No\.(\d+) task is finished", b)
        m_sr = re.search(r"Average Success\s+\|\s+([\d.]+)%", b)
        m_spl = re.search(r"Average SPL\s+\|\s+([\d.]+)%", b)
        res = (m_res.group(1).strip() if m_res else "unknown")
        failures[res] += 1
        episodes.append({
            "n": int(m_no.group(1)) if m_no else None,
            "scene": m_scene.group(1) if m_scene else None,
            "episode_id": m_ep.group(1) if m_ep else None,
            "label": m_lab.group(1).strip() if m_lab else None,
            "result": res,
            "running_sr_pct": float(m_sr.group(1)) if m_sr else None,
            "running_spl_pct": float(m_spl.group(1)) if m_spl else None,
        })
# record.txt prepends newest first → reverse for chronological
episodes = list(reversed(episodes))
n = len(episodes)
n_succ = failures.get("success", 0)
summary = {
    "paper_target": {"dataset": "HM3D-v2 val", "n_episodes": 1000, "SR": 76.2, "SPL": 38.0},
    "n_completed": n,
    "n_success": n_succ,
    "SR_pct": (100.0 * n_succ / n) if n else None,
    "final_running_sr_pct": episodes[-1].get("running_sr_pct") if episodes else None,
    "final_running_spl_pct": episodes[-1].get("running_spl_pct") if episodes else None,
    "failure_hist": dict(failures),
    "exit_code": int("$EC"),
    "wall_s": int("$END") - int("$START"),
    "out_dir": str(out),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2))
(out / "episodes.jsonl").write_text("\n".join(json.dumps(e) for e in episodes) + ("\n" if episodes else ""))
(out / "failure_hist.json").write_text(json.dumps(dict(failures), indent=2))
print(json.dumps(summary, indent=2))
PY

echo FULL_HM3DV2_DONE | tee -a "$OUT/driver.log"
