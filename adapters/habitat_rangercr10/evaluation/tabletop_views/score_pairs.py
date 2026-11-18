#!/usr/bin/env python3
# ################################
# VLN adapt: paired fixed_gimbal vs arm_ee instance confirmation
# ################################
"""Instance confirmed for a camera mode iff ≥1 of its ≤3 views is a frame hit
(IoU≥0.5 + correct class). Denominator = pre-selected paired instances with
reliable GT — invisibility under one mode is a result, not exclusion.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

CAMERA_MODES = ("fixed_base_gimbal", "arm_ee")


def _load_jsonl(path: Path) -> List[dict]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def confirm_instance(frame_rows: List[dict]) -> Dict[str, Any]:
    hits = [r for r in frame_rows if r.get("hit") is True]
    buckets = Counter(r.get("bucket") for r in frame_rows)
    return {
        "confirmed": len(hits) > 0,
        "n_views": len(frame_rows),
        "n_hits": len(hits),
        "best_iou": max((r.get("best_iou") or 0.0) for r in frame_rows) if frame_rows else None,
        "bucket_counts": dict(buckets),
        "visibility_any": any(
            r.get("bucket") not in ("target_invisible", "log_missing") for r in frame_rows
        ),
        "visible_but_never_hit": (
            any(r.get("bucket") in ("miss_visible", "other_instance") for r in frame_rows)
            and len(hits) == 0
        ),
    }


def build_instance_table(frame_jsonl: Path) -> List[dict]:
    frames = _load_jsonl(frame_jsonl)
    by_key: Dict[tuple, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    meta_by: Dict[tuple, dict] = {}
    for r in frames:
        key = (r.get("pair_id"), r.get("instance_id"), r.get("category"))
        mode = r.get("camera_mode")
        by_key[key][mode].append(r)
        meta_by[key] = {
            "pair_id": r.get("pair_id"),
            "instance_id": r.get("instance_id"),
            "category": r.get("category"),
            "scene": r.get("scene"),
        }

    rows = []
    for key, modes in sorted(by_key.items()):
        meta = meta_by[key]
        conf = {m: confirm_instance(modes.get(m, [])) for m in CAMERA_MODES}
        fg = conf["fixed_base_gimbal"]["confirmed"]
        ar = conf["arm_ee"]["confirmed"]
        if fg and ar:
            cell = "both"
        elif fg and not ar:
            cell = "fixed_only"
        elif ar and not fg:
            cell = "arm_only"
        else:
            cell = "neither"
        # gain attribution hints
        gain = None
        if cell == "arm_only":
            # first visible under arm vs visible-under-fixed but miss
            fixed_frames = modes.get("fixed_base_gimbal", [])
            if all(f.get("bucket") == "target_invisible" for f in fixed_frames) or not fixed_frames:
                gain = "visibility_new"
            elif any(f.get("bucket") in ("miss_visible", "other_instance") for f in fixed_frames):
                gain = "detection_improve"
            else:
                gain = "unknown"
        elif cell == "fixed_only":
            arm_frames = modes.get("arm_ee", [])
            if all(f.get("bucket") == "target_invisible" for f in arm_frames) or not arm_frames:
                gain = "fixed_visibility_advantage"
            else:
                gain = "fixed_detection_advantage"

        rows.append(
            {
                **meta,
                "fixed_base_gimbal": conf["fixed_base_gimbal"],
                "arm_ee": conf["arm_ee"],
                "pair_cell": cell,
                "gain_attribution": gain,
            }
        )
    return rows


def summarize(instance_rows: List[dict]) -> dict:
    by_cat = defaultdict(list)
    for r in instance_rows:
        by_cat[str(r.get("category"))].append(r)

    per_cat = []
    for cat in sorted(by_cat):
        xs = by_cat[cat]
        cells = Counter(x["pair_cell"] for x in xs)
        per_cat.append(
            {
                "category": cat,
                "n_instances": len(xs),
                "confirmed_fixed": sum(1 for x in xs if x["fixed_base_gimbal"]["confirmed"]),
                "confirmed_arm": sum(1 for x in xs if x["arm_ee"]["confirmed"]),
                "both": cells.get("both", 0),
                "fixed_only": cells.get("fixed_only", 0),
                "arm_only": cells.get("arm_only", 0),
                "neither": cells.get("neither", 0),
                "metric_name": "桌边目标确认率",
                "confirm_rate_fixed": (
                    sum(1 for x in xs if x["fixed_base_gimbal"]["confirmed"]) / len(xs)
                    if xs
                    else None
                ),
                "confirm_rate_arm": (
                    sum(1 for x in xs if x["arm_ee"]["confirmed"]) / len(xs) if xs else None
                ),
                "note": "small-n: prefer raw counts + case writeups over CI",
            }
        )

    overall_cells = Counter(x["pair_cell"] for x in instance_rows)
    return {
        "n_instances": len(instance_rows),
        "pair_cells": dict(overall_cells),
        "by_category": per_cat,
        "gain_attribution_counts": dict(
            Counter(x.get("gain_attribution") for x in instance_rows if x.get("gain_attribution"))
        ),
        "metric_notes": [
            "桌边目标确认率 = instances with ≥1 hit / pre-selected paired instances",
            "hit = target class ∧ IoU(pred, specified GT instance) ≥ 0.5",
            "Invisible under one mode remains in denominator",
            "Do not call this ObjectNav SR or paper accuracy",
        ],
    }


def to_markdown(summary: dict, instance_rows: List[dict]) -> str:
    lines = [
        "# Tabletop views pilot — paired confirmation",
        "",
        f"- n_instances: {summary['n_instances']}",
        f"- pair cells: {summary['pair_cells']}",
        f"- gain attribution: {summary.get('gain_attribution_counts')}",
        "",
        "## Per category (桌边目标确认率)",
        "",
        "| category | n | fixed | arm | both | fixed_only | arm_only | neither |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in summary["by_category"]:
        lines.append(
            f"| {c['category']} | {c['n_instances']} | {c['confirmed_fixed']} | "
            f"{c['confirmed_arm']} | {c['both']} | {c['fixed_only']} | "
            f"{c['arm_only']} | {c['neither']} |"
        )
    lines += ["", "## Instance rows", ""]
    for r in instance_rows:
        lines.append(
            f"- `{r['pair_id']}` / `{r['instance_id']}` ({r['category']}): "
            f"cell={r['pair_cell']} gain={r.get('gain_attribution')} "
            f"fixed_hits={r['fixed_base_gimbal']['n_hits']}/{r['fixed_base_gimbal']['n_views']} "
            f"arm_hits={r['arm_ee']['n_hits']}/{r['arm_ee']['n_views']}"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_jsonl", type=Path)
    ap.add_argument("--out_instances", type=Path, required=True)
    ap.add_argument("--out_summary_json", type=Path, required=True)
    ap.add_argument("--out_summary_md", type=Path, required=True)
    args = ap.parse_args()

    rows = build_instance_table(args.frames_jsonl)
    summary = summarize(rows)
    args.out_instances.parent.mkdir(parents=True, exist_ok=True)
    args.out_instances.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))
    args.out_summary_json.write_text(json.dumps(summary, indent=2) + "\n")
    args.out_summary_md.write_text(to_markdown(summary, rows))
    print(f"instances={len(rows)} cells={summary['pair_cells']} -> {args.out_summary_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
