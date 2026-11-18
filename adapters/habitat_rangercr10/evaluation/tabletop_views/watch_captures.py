#!/usr/bin/env python3
# ################################
# VLN adapt: poll Cursor A captures; score first ready pair immediately (via docker)
# ################################
"""Host-side watcher. Detection runs inside vln-rangercr10 so YOLO/SAM
localhost ports are reachable.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from run_pilot import DEFAULT_CAPTURES, DEFAULT_OUT, _find_gt, _find_rgb, _iter_views

CAMERA_MODES = ("fixed_base_gimbal", "arm_ee")
# synthetic fixtures used for plumbing — do not count as A's first delivery
SKIP_PAIR_PREFIXES = ("smoke_synth_", "fixture_")


def pair_ready(pair_dir: Path) -> bool:
    any_mode = False
    modes_ok = 0
    for mode in CAMERA_MODES:
        md = pair_dir / mode
        views = _iter_views(md)
        if not views:
            continue
        any_mode = True
        for _, vd in views:
            if _find_rgb(vd) is None or _find_gt(vd) is None:
                return False
        modes_ok += 1
    return any_mode and modes_ok >= 2


def discover_ready(captures: Path, *, include_fixtures: bool = False) -> list[str]:
    ready = []
    idx = captures / "pairing_index.json"
    names = []
    if idx.is_file():
        data = json.loads(idx.read_text())
        names = [p["pair_id"] for p in data.get("pairs", [])]
    else:
        names = [d.name for d in sorted(captures.iterdir()) if d.is_dir()]
    for name in names:
        if not include_fixtures and any(name.startswith(p) for p in SKIP_PAIR_PREFIXES):
            continue
        if pair_ready(captures / name):
            ready.append(name)
    return ready


def _docker_run_pilot(pair_id: str | None, *, stop_after_first: bool) -> int:
    # ensure VLM
    root = Path(__file__).resolve().parents[4]
    subprocess.run(
        ["bash", str(Path(__file__).resolve().parent / "ensure_vlm_yolo_sam.sh")],
        check=False,
    )
    cmd = [
        "docker",
        "exec",
        "vln-rangercr10",
        "bash",
        "-lc",
        (
            "source /opt/ros/noetic/setup.bash; "
            "source /workspace/ApexNav/devel/setup.bash; "
            "cd /workspace/ApexNav; "
            "export PYTHONPATH=/workspace/ApexNav:"
            "/workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/evaluation/tabletop_views:"
            "${PYTHONPATH}; "
            "python3 /workspace/VLN_Mobilemanipulator/adapters/habitat_rangercr10/"
            "evaluation/tabletop_views/run_pilot.py"
            + (f" --pair_id {pair_id}" if pair_id else "")
            + (" --stop_after_first_pair" if stop_after_first else "")
        ),
    ]
    print("[watch] ", " ".join(cmd[-1][:80],) if False else "docker exec run_pilot", pair_id)
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--poll_s", type=float, default=15.0)
    ap.add_argument("--max_wait_s", type=float, default=0.0, help="0 = forever")
    ap.add_argument("--once", action="store_true")
    ap.add_argument(
        "--include_fixtures",
        action="store_true",
        help="also treat smoke_synth_/fixture_ as A delivery",
    )
    args = ap.parse_args()

    t0 = time.time()
    seen: set[str] = set()
    print(f"watching {args.captures} -> {args.out} (docker get_object)")
    while True:
        ready = discover_ready(args.captures, include_fixtures=args.include_fixtures)
        new = [p for p in ready if p not in seen]
        if new:
            first = new[0]
            print(f"first ready pair from A: {first}")
            rc = _docker_run_pilot(first, stop_after_first=True)
            print(f"smoke rc={rc}")
            seen.add(first)
            rest = discover_ready(args.captures, include_fixtures=args.include_fixtures)
            if rest:
                print(f"full ready set: {rest}")
                _docker_run_pilot(None, stop_after_first=False)
                seen.update(rest)
            if args.once:
                return 0
        if args.max_wait_s and (time.time() - t0) > args.max_wait_s:
            print("max_wait reached; exit")
            return 0
        time.sleep(args.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
