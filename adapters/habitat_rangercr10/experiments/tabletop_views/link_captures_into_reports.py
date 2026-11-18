#!/usr/bin/env python3
# ################################
# VLN adapt: symlink D-disk captures into reports/ for Cursor D
# ################################
from __future__ import annotations

import json
from pathlib import Path

from paths import CAPTURES_DATA, REPORT_CAPTURE, REPORT_ROOT

CAPT_REPORT = REPORT_ROOT / "captures"


def main() -> int:
    CAPT_REPORT.mkdir(parents=True, exist_ok=True)
    REPORT_CAPTURE.mkdir(parents=True, exist_ok=True)
    pairs = []
    if not CAPTURES_DATA.is_dir():
        print("no data root", CAPTURES_DATA)
        return 1
    for d in sorted(CAPTURES_DATA.iterdir()):
        if not d.is_dir():
            continue
        man = d / "manifest.json"
        if not man.is_file():
            continue
        link = CAPT_REPORT / d.name
        if link.is_symlink() or link.exists():
            if link.is_symlink():
                link.unlink()
            elif link.is_dir() and not any(link.iterdir()):
                link.rmdir()
        if not link.exists():
            link.symlink_to(d, target_is_directory=True)
        m = json.loads(man.read_text())
        pairs.append(
            {
                "pair_id": m["pair_id"],
                "instance_id": m["instance_id"],
                "category": m.get("category_raw") or m.get("category"),
                "scene": m.get("scene") or m.get("scene_id"),
                "reliable_gt": True,
                "notes": "",
            }
        )
    index = {
        "protocol": "tabletop_views_pilot_v1",
        "camera_modes": ["fixed_base_gimbal", "arm_ee"],
        "max_views_per_mode": 3,
        "captures_data_root": str(CAPTURES_DATA),
        "pairs": pairs,
    }
    for root in (CAPTURES_DATA, CAPT_REPORT, REPORT_CAPTURE):
        (root / "pairing_index.json").write_text(json.dumps(index, indent=2) + "\n")
        (root / "manifest_index.json").write_text(
            json.dumps({"pairs": [{"pair_id": p["pair_id"]} for p in pairs]}, indent=2)
            + "\n"
        )
    print(f"linked {len(pairs)} pairs -> {CAPT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
