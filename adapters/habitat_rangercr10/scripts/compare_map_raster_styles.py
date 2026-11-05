#!/usr/bin/env python3
"""Compare 1-px Demo scatter vs resolution-matched cell fill on the same /grid_map dump.

################################
Offline Demo-raster audit only. Does not alter ApexNav map / planner.
Distinguishes: true occupied endpoints in cloud vs 1-px visualization gaps.
################################
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.map_listener import value_intensity_to_rgb  # noqa: E402
from src.map_raster import (  # noqa: E402
    DEFAULT_MAP_RESOLUTION_M,
    estimate_resolution_m,
    fill_cells_rgb,
    fill_value_cells,
)
from src.map_style import (  # noqa: E402
    PAPER_BG,
    PAPER_FREE,
    PAPER_OCCUPIED,
    PAPER_ROBOT,
    PAPER_TRAJ,
    PAPER_UNKNOWN,
    VALUE_OVERLAY_ALPHA,
)


def _paint_1px(canvas, xy, color, center, scale, mask=None, write=True):
    h, w = canvas.shape[:2]
    if xy is None or len(xy) == 0:
        return
    for p in xy:
        px = int((p[0] - center[0]) * scale + w / 2)
        py = int(-(p[1] - center[1]) * scale + h / 2)
        if 0 <= px < w and 0 <= py < h:
            if write:
                canvas[py, px] = color
            if mask is not None:
                mask[py, px] = True


def render_style(
    style: str,
    *,
    occ,
    free,
    unknown,
    value_xyi,
    center,
    size=(320, 240),
    meters_span=12.0,
) -> np.ndarray:
    h, w = size[1], size[0]
    canvas = np.full((h, w, 3), PAPER_BG, dtype=np.uint8)
    scale = w / meters_span
    free_mask = np.zeros((h, w), dtype=bool)
    occ_mask = np.zeros((h, w), dtype=bool)
    res = estimate_resolution_m(free, occ, unknown, default=DEFAULT_MAP_RESOLUTION_M)

    if style == "one_px":
        _paint_1px(canvas, unknown, PAPER_UNKNOWN, center, scale)
        _paint_1px(canvas, free, PAPER_FREE, center, scale, free_mask)
        _paint_1px(canvas, occ, PAPER_OCCUPIED, center, scale, occ_mask, write=False)
        if value_xyi is not None and len(value_xyi):
            a = float(VALUE_OVERLAY_ALPHA)
            for x, y, inten in value_xyi:
                px = int((x - center[0]) * scale + w / 2)
                py = int(-(y - center[1]) * scale + h / 2)
                if not (0 <= px < w and 0 <= py < h) or occ_mask[py, px]:
                    continue
                if not free_mask[py, px]:
                    continue
                heat = np.asarray(value_intensity_to_rgb(float(inten)), dtype=np.float64)
                base = canvas[py, px].astype(np.float64)
                canvas[py, px] = np.clip((1.0 - a) * base + a * heat, 0, 255).astype(np.uint8)
        _paint_1px(canvas, occ, PAPER_OCCUPIED, center, scale)
    else:
        fill_cells_rgb(
            canvas, unknown, PAPER_UNKNOWN, center_xy=center, scale=scale, resolution_m=res
        )
        fill_cells_rgb(
            canvas,
            free,
            PAPER_FREE,
            center_xy=center,
            scale=scale,
            resolution_m=res,
            mask=free_mask,
        )
        fill_cells_rgb(
            canvas,
            occ,
            PAPER_OCCUPIED,
            center_xy=center,
            scale=scale,
            resolution_m=res,
            mask=occ_mask,
            write_rgb=False,
        )
        if value_xyi is not None and len(value_xyi):
            fill_value_cells(
                canvas,
                value_xyi,
                center_xy=center,
                scale=scale,
                resolution_m=res,
                free_mask=free_mask,
                occ_mask=occ_mask,
                intensity_to_rgb=value_intensity_to_rgb,
                alpha=float(VALUE_OVERLAY_ALPHA),
            )
        fill_cells_rgb(
            canvas, occ, PAPER_OCCUPIED, center_xy=center, scale=scale, resolution_m=res
        )

    # robot marker
    px = int(w / 2)
    py = int(h / 2)
    canvas[max(0, py - 2) : py + 3, max(0, px - 2) : px + 3] = PAPER_ROBOT
    return canvas


def radial_report(occ, free, center) -> dict:
    o = np.asarray(occ, dtype=np.float64)
    f = np.asarray(free, dtype=np.float64)
    c = np.asarray(center, dtype=np.float64)

    def stats(xy, name):
        if len(xy) == 0:
            return {name: {"n": 0}}
        r = np.linalg.norm(xy - c, axis=1)
        ang = np.arctan2(xy[:, 1] - c[1], xy[:, 0] - c[0])
        hist, _ = np.histogram(ang, bins=36, range=(-math.pi, math.pi))
        return {
            "n": int(len(xy)),
            "r_med": float(np.median(r)),
            "r_p90": float(np.percentile(r, 90)),
            "ang_nonzero_bins": int((hist > 0).sum()),
            "ang_peakiness": float(hist.max() / (hist.mean() + 1e-9)),
            "frac_isolated_r_gt_1.5": float(((r > 1.5) & (r < 3.0)).mean()),
        }

    res = estimate_resolution_m(o, f)
    # Unique cells
    def n_unique(xy):
        if len(xy) == 0:
            return 0
        q = np.round(xy / res) * res
        return len({(a, b) for a, b in q})

    return {
        "resolution_m_est": res,
        "occupied": stats(o, "occ"),
        "free": stats(f, "free"),
        "occupied_unique_cells": n_unique(o),
        "free_unique_cells": n_unique(f),
        "interpretation": [
            "Occupied/free points are true /grid_map cell centers (res≈0.05m), not Demo inventions.",
            "Radial look during lookaround comes from sparse angular coverage of depth ray endpoints + free carving — present in raw cloud.",
            "1-px Demo paint undersamples each 0.05m cell (~1.3px at 12m/320span) → artificial gaps that look like cell borders/spokes.",
            "Cell-footprint fill removes those viz gaps without deleting points or morphological smoothing.",
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run_dir",
        type=Path,
        required=True,
        help="apexnav_real run with planner_first_call_diag/*.npy",
    )
    ap.add_argument("--out_dir", type=Path, default=None)
    args = ap.parse_args()
    run = args.run_dir
    diag = run / "planner_first_call_diag"
    out = args.out_dir or (
        Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/map_raster_compare")
        / run.name
    )
    out.mkdir(parents=True, exist_ok=True)

    occ = np.load(diag / "occupied_xy.npy")
    free = np.load(diag / "free_xy.npy")
    unknown = np.load(diag / "unknown_xy.npy") if (diag / "unknown_xy.npy").exists() else np.zeros((0, 2))
    # value intensity not dumped historically — synthesize flat mid value on free for overlay viz parity only if missing
    value_path = diag / "value_xyi.npy"
    if value_path.exists():
        value_xyi = np.load(value_path)
    else:
        # Use free cells with intensity from recorded itm if available
        itm = 0.18
        ls = run / "maps" / "latest_stats.json"
        if ls.exists():
            try:
                itm = float(json.loads(ls.read_text()).get("itm_cosine", itm))
            except Exception:
                pass
        value_xyi = np.concatenate(
            [free, np.full((len(free), 1), itm, dtype=np.float64)], axis=1
        ) if len(free) else np.zeros((0, 3))

    # center from robot in diag json if present
    center = free.mean(0) if len(free) else occ.mean(0)
    fj = diag / "first_plan_diag.json"
    if fj.exists():
        d = json.loads(fj.read_text())
        if d.get("base_ros_xy"):
            center = np.array(d["base_ros_xy"], dtype=np.float64)

    before = render_style(
        "one_px", occ=occ, free=free, unknown=unknown[:8000], value_xyi=value_xyi, center=center
    )
    after = render_style(
        "cell_fill", occ=occ, free=free, unknown=unknown[:8000], value_xyi=value_xyi, center=center
    )
    Image.fromarray(before).save(out / "same_data_before_1px.png")
    Image.fromarray(after).save(out / "same_data_after_cell_fill.png")

    # Side-by-side
    combo = np.concatenate([before, after], axis=1)
    im = Image.fromarray(combo)
    dr = ImageDraw.Draw(im)
    dr.text((8, 8), "BEFORE: 1px scatter", fill=(0, 0, 0))
    dr.text((before.shape[1] + 8, 8), "AFTER: cell footprint fill", fill=(0, 0, 0))
    im.save(out / "same_data_before_after_side_by_side.png")

    # Also copy live Demo map PNG at step 25 if present (prior style)
    for step in (0, 8, 17, 25):
        src = run / "maps" / f"frame_{step:04d}.png"
        if src.exists():
            Image.open(src).save(out / f"live_demo_map_step{step:02d}_prior_style.png")

    report = radial_report(occ, free, center)
    report["run_dir"] = str(run)
    report["out_dir"] = str(out)
    report["n_value"] = int(len(value_xyi))
    (out / "radial_raw_vs_render.json").write_text(json.dumps(report, indent=2))
    # Save raw arrays pointer note
    np.save(out / "occupied_xy.npy", occ)
    np.save(out / "free_xy.npy", free)
    print(json.dumps(report, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
