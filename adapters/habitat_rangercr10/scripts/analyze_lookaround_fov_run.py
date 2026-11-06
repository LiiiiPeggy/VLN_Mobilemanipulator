#!/usr/bin/env python3
"""Analyze camera FOV / lookaround / passability for one apexnav_real run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.lookaround_fov_diag import (  # noqa: E402
    analyze_episode_lookaround,
    angular_occupancy_hist,
    render_coverage_rose,
    summarize_passability,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", type=Path, required=True)
    ap.add_argument("--out_dir", type=Path, default=None)
    args = ap.parse_args()
    run = args.run_dir
    out = args.out_dir or (
        Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/lookaround_fov_diag")
        / run.name
    )
    out.mkdir(parents=True, exist_ok=True)

    diag = analyze_episode_lookaround(run)
    # strip heavy frames for summary json? keep full for evidence
    (out / "lookaround_fov_diag.json").write_text(json.dumps(diag, indent=2))
    render_coverage_rose(diag, out / "lookaround_fov_wedges.png")

    # Angular hist from first_plan dump
    diag_dir = run / "planner_first_call_diag"
    ang = {}
    if (diag_dir / "occupied_xy.npy").exists():
        occ = np.load(diag_dir / "occupied_xy.npy")
        free = np.load(diag_dir / "free_xy.npy")
        center = json.loads((diag_dir / "first_plan_diag.json").read_text()).get(
            "base_ros_xy"
        ) or free.mean(0).tolist()
        ang = {
            "occupied": angular_occupancy_hist(occ, center),
            "free": angular_occupancy_hist(free, center),
            "center_xy": center,
        }
        (out / "angular_hist.json").write_text(json.dumps(ang, indent=2))

    passability = {}
    fp = diag_dir / "first_plan_diag.json"
    if fp.exists():
        passability = summarize_passability(json.loads(fp.read_text()))
        (out / "passability_summary.json").write_text(json.dumps(passability, indent=2))

    # Compact report markdown
    fov = diag["fov"]
    lines = [
        f"# Lookaround FOV diag — `{run.name}`",
        "",
        f"- HFOV/VFOV (from ApexNav fx/fy): **{fov['hfov_deg']:.2f}° / {fov['vfov_deg']:.2f}°**",
        f"- Mean TURN yaw step: **{diag.get('mean_turn_yaw_step_deg')}°**",
        f"- Overlap @ mean step: `{diag.get('overlap_at_mean_step')}`",
        f"- Overlap table: `{json.dumps(diag.get('overlap_table'))}`",
        "",
        "## Findings",
    ]
    for f in diag.get("findings") or []:
        lines.append(f"- {f}")
    lines += ["", "## Passability (first plan)", f"```json\n{json.dumps(passability, indent=2)}\n```"]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("wrote", out)
    print(json.dumps({"findings": diag.get("findings"), "passability": passability}, indent=2))


if __name__ == "__main__":
    main()
