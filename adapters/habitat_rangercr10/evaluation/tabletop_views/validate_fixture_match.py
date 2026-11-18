#!/usr/bin/env python3
# ################################
# VLN adapt: score synthetic fixture WITHOUT YOLO (wiring + IoU + pairing tables)
# ################################
"""Uses GT as aligned pred on view_00/01 and a shifted pred on view_02 to exercise
hit / other_instance buckets. Real C RGB must go through run_pilot.py + live YOLO.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS))

from make_overlays import overlay  # noqa: E402
from match_instance import load_mask, match_frame  # noqa: E402
from run_pilot import (  # noqa: E402
    CAMERA_MODES,
    DEFAULT_OUT,
    _find_gt,
    _find_rgb,
    _iter_views,
    _write_locked_config,
)
from score_pairs import build_instance_table, summarize, to_markdown  # noqa: E402

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    pair_dir = REPO / "reports/tabletop_views_pilot/captures/fixture_cupA"
    out = DEFAULT_OUT
    _write_locked_config(out / "configs" / "locked_detector_config.json", 0.3, 0.5)
    rows = []
    for mode in CAMERA_MODES:
        for view_id, vd in _iter_views(pair_dir / mode):
            rgb_p = _find_rgb(vd)
            gt_p = _find_gt(vd)
            rgb = np.array(Image.open(rgb_p).convert("RGB"))
            gt = load_mask(gt_p)
            # view_02 → shifted pred (other instance); else perfect overlap
            pred = gt.copy()
            if view_id.endswith("02") or view_id == "view_02":
                pred = np.roll(gt, shift=120, axis=1)
            match = match_frame(
                gt_mask=gt,
                pred_masks=[pred],
                pred_scores=[0.88],
                pred_labels_is_target=[True],
            )
            ov = overlay(
                rgb,
                gt,
                pred,
                title=f"fixture|{mode}|{view_id}|{match['bucket']}|iou={match['best_iou']:.3f}",
            )
            op = out / "overlays" / f"fixture_cupA__{mode}__{view_id}.png"
            op.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(ov).save(op)
            rows.append(
                {
                    "pair_id": "fixture_cupA",
                    "instance_id": "cup_A",
                    "category": "cup",
                    "category_raw": "mug",
                    "scene": "synthetic_fixture",
                    "camera_mode": mode,
                    "view_id": view_id,
                    "rgb": str(rgb_p),
                    "gt_mask": str(gt_p),
                    "overlay": str(op),
                    "n_pred_target_class": 1,
                    "note": "synthetic_pred_from_gt_for_wiring",
                    **match,
                }
            )
            print(mode, view_id, match["bucket"], match["best_iou"])

    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    # keep smoke detect json; append fixture frames under fixture_frames.jsonl
    fp = tables / "fixture_frames.jsonl"
    fp.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    inst = build_instance_table(fp)
    summary = summarize(inst)
    (tables / "fixture_instances.jsonl").write_text(
        "\n".join(json.dumps(r) for r in inst) + "\n"
    )
    (tables / "fixture_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (tables / "fixture_summary.md").write_text(to_markdown(summary, inst))
    print("fixture summary cells", summary["pair_cells"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
