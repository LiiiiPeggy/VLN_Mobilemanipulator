#!/usr/bin/env python3
# ################################
# Export frozen HY1 plan_seq_1 local_map + candidates for native A* A/B replay.
# ################################
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run",
        type=Path,
        default=Path(
            "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/"
            "real_s070_hy1_base_rep_v2_r1_20261106_191426"
        ),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(
            "/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/"
            "hy1_startup_prior_20261107"
        ),
    )
    args = ap.parse_args()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    lm = json.loads((args.run / "native_diag" / "plan_seq_1_local_map.json").read_text())
    plan = json.loads(
        (args.run / "native_diag" / "native_plan_diag.jsonl").read_text().splitlines()[0]
    )
    summary = json.loads((args.run / "summary.json").read_text())

    cells_path = out / "cells.csv"
    with cells_path.open("w") as f:
        f.write("# x,y,raw_occ,inflate  raw:0=UNK,1=FREE,2=OCC\n")
        for x, y, r, i in lm["cells"]:
            f.write(f"{x},{y},{int(r)},{int(i)}\n")

    cands_path = out / "candidates.csv"
    with cands_path.open("w") as f:
        f.write("# candidate_x,candidate_y\n")
        for c in plan.get("candidates") or []:
            g = c.get("candidate")
            if g and len(g) >= 2:
                f.write(f"{g[0]},{g[1]}\n")

    meta = {
        "run": str(args.run),
        "plan_seq": lm.get("plan_seq"),
        "chassis": lm.get("chassis"),
        "yaw_ros": summary["first_plan_diag"]["base_yaw_ros"],
        "resolution": lm.get("resolution"),
        "half_m": lm.get("half_m"),
        "n_cells": len(lm["cells"]),
        "n_candidates": len(plan.get("candidates") or []),
        "native_result": plan.get("result"),
        "robot_scale": summary.get("robot_scale"),
        "half_l_0p7": 0.4557,
        "half_w_0p7": 0.30429,
    }
    (out / "freeze_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({"out": str(out), "meta": meta}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
