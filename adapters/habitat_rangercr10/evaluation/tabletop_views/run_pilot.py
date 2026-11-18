#!/usr/bin/env python3
# ################################
# VLN adapt: batch detect → instance match → paired confirmation (Cursor D)
# ################################
"""Offline production get_object on Cursor C captures.

Detector sees only RGB + query label. GT masks are read AFTER inference.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

_THIS = Path(__file__).resolve().parent
if str(_THIS) not in sys.path:
    sys.path.insert(0, str(_THIS))

from category_map import EMPTY_SIMILAR_ANSWER, canonicalize, ensure_canonical  # noqa: E402
from detect_frame import PROD_HW, detect_rgb  # noqa: E402
from make_overlays import overlay  # noqa: E402
from match_instance import IOU_HIT_THR, load_mask, match_frame  # noqa: E402
from score_pairs import build_instance_table, summarize, to_markdown  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
DEFAULT_CAPTURES = REPO / "reports/tabletop_views_pilot/captures"
DEFAULT_OUT = REPO / "reports/tabletop_views_pilot/evaluation"
CAMERA_MODES = ("fixed_base_gimbal", "arm_ee")


def _write_locked_config(path: Path, conf_yolo: float, iou_yolo: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = {
        "protocol": "tabletop_views_pilot_v1",
        "role": "Cursor D — offline get_object + instance IoU match",
        "detector_entry": "baselines/ApexNav/vlm/utils/get_object_utils.get_object",
        "backend": "YOLOv7Client:12184 + MobileSAMClient:12183",
        "query_labels_canonical": ["cup", "bowl", "remote", "bottle"],
        "alias_map": {
            "mug": "cup",
            "coffee mug": "cup",
            "remote control": "remote",
        },
        "similar_answer": EMPTY_SIMILAR_ANSWER,
        "similar_answer_rationale": (
            "HM3D six-class LLM answer table has no small-object rows; "
            "pass explicit empty list so only the target COCO class is scored"
        ),
        "yolo": {
            "confidence_threshold_yolo": conf_yolo,
            "iou_threshold_yolo": iou_yolo,
            "agnostic_nms": True,
            "source": "baselines/ApexNav/config/habitat_eval_hm3dv2.yaml detector.yolo",
        },
        "hit_rule": {
            "pred_class": "canonical target",
            "iou_thr": IOU_HIT_THR,
            "note": "same-class other instance with IoU<0.5 → other_instance, not hit",
        },
        "confirmation_rule": (
            "instance confirmed for a camera mode iff ≥1 of ≤3 views is a frame hit"
        ),
        "metric_name": "桌边目标确认率",
        "same_weights_both_groups": True,
    }
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")


def _load_index(captures: Path) -> List[dict]:
    # ################################
    # VLN adapt: accept pairing_index.json or Cursor C manifest_index.json
    # ################################
    pairs: List[dict] = []
    for name in ("pairing_index.json", "manifest_index.json"):
        j = captures / name
        if j.is_file():
            data = json.loads(j.read_text())
            pairs = list(data.get("pairs") or data.get("instances") or [])
            break
    jl = captures / "pairing_index.jsonl"
    if not pairs and jl.is_file():
        for line in jl.read_text().splitlines():
            if line.strip():
                pairs.append(json.loads(line))
    if not pairs:
        # discover pair dirs that look ready
        for d in sorted(captures.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            if (d / "fixed_base_gimbal").is_dir() or (d / "arm_ee").is_dir():
                meta = {}
                mp = d / "meta.json"
                if mp.is_file():
                    meta = json.loads(mp.read_text())
                pairs.append(
                    {
                        "pair_id": meta.get("pair_id", d.name),
                        "instance_id": meta.get("instance_id", d.name),
                        "category": meta.get("category"),
                        "scene": meta.get("scene"),
                        "reliable_gt": meta.get("reliable_gt", True),
                        "_dir": str(d),
                    }
                )
    return pairs


def _pair_dir(captures: Path, pair: dict) -> Path:
    if pair.get("_dir"):
        return Path(pair["_dir"])
    return captures / str(pair["pair_id"])


def _find_rgb(view_dir: Path) -> Optional[Path]:
    for name in ("rgb.png", "rgb.jpg", "rgb.jpeg", "RGB.png"):
        p = view_dir / name
        if p.is_file():
            return p
    for p in sorted(view_dir.glob("*.png")):
        if "mask" not in p.name.lower() and "gt" not in p.name.lower():
            return p
    return None


def _find_gt(view_dir: Path) -> Optional[Path]:
    for name in (
        "gt_mask.png",
        "gt_mask.npy",
        "instance_mask.png",
        "instance_mask.npy",
        "mask.png",
        "mask.npy",
    ):
        p = view_dir / name
        if p.is_file():
            return p
    return None


def _iter_views(mode_dir: Path) -> List[Tuple[str, Path]]:
    """Return list of (view_id, view_dir). view_dir contains rgb + optional gt_mask."""
    if not mode_dir.is_dir():
        return []
    # prefer view_XX / obs_XX dirs
    sub = sorted(
        [
            d
            for d in mode_dir.iterdir()
            if d.is_dir() and (d.name.startswith("view_") or d.name.startswith("obs_"))
        ]
    )
    if sub:
        return [(d.name, d) for d in sub[:3]]
    # flat: mode_dir/rgb.png or rgb_00.png — synthesize one-file view dirs via parent + marker
    out: List[Tuple[str, Path]] = []
    if (mode_dir / "rgb.png").is_file() or (mode_dir / "rgb.jpg").is_file():
        out.append(("view_00", mode_dir))
        return out
    for i, p in enumerate(sorted(mode_dir.glob("rgb_*.png"))[:3]):
        # put a sidecar dir pointer: use mode_dir but tag view_id; process_view finds rgb by name prefer
        out.append((f"view_{i:02d}", mode_dir))
    return out


def _load_view_meta(view_dir: Path) -> dict:
    for name in ("view_meta.json", "meta.json"):
        p = view_dir / name
        if p.is_file():
            meta = json.loads(p.read_text())
            # aliases from A drafts
            if "gt_visible" not in meta and "target_visible" in meta:
                meta["gt_visible"] = meta["target_visible"]
            return meta
    return {}


def process_view(
    *,
    pair: dict,
    camera_mode: str,
    view_id: str,
    view_dir: Path,
    out_root: Path,
    conf_yolo: float,
    iou_yolo: float,
    make_overlay_always: bool,
    mock_detect: bool = False,
) -> dict:
    pair_id = str(pair["pair_id"])
    vmeta0 = _load_view_meta(view_dir)
    category_raw = (
        pair.get("category")
        or pair.get("category_raw")
        or vmeta0.get("category")
        or vmeta0.get("category_raw")
    )
    try:
        category = ensure_canonical(str(category_raw))
    except Exception as e:
        return {
            "pair_id": pair_id,
            "instance_id": pair.get("instance_id"),
            "category": category_raw,
            "camera_mode": camera_mode,
            "view_id": view_id,
            "bucket": "log_missing",
            "hit": False,
            "error": f"bad_category: {e}",
        }

    rgb_path = _find_rgb(view_dir)
    vmeta = _load_view_meta(view_dir)
    if rgb_path is None:
        return {
            "pair_id": pair_id,
            "instance_id": pair.get("instance_id"),
            "category": category,
            "camera_mode": camera_mode,
            "view_id": view_id,
            "bucket": "log_missing",
            "hit": False,
            "error": "rgb_missing",
            "view_meta": vmeta,
        }

    # ################################
    # VLN adapt: detect FIRST — do not load GT until after get_object returns
    # ################################
    pred_dir = out_root / "preds" / pair_id / camera_mode / view_id
    pred_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        from detect_frame import _load_rgb

        # ################################
        # VLN adapt: force 480x640 (H,W) to match get_object MobileSAM canvas
        # ################################
        rgb = _load_rgb(rgb_path, resize_to_prod=True)
        # ################################
        # VLN adapt: mock_detect for schema/IoU plumbing without VLM ports
        # ################################
        if mock_detect:
            gt_early = None  # still do not use GT for "detection"
            det = {
                "query_label": category,
                "similar_answer": list(EMPTY_SIMILAR_ANSWER),
                "n_pred": 0,
                "n_pred_target_class": 0,
                "predictions": [],
                "detector": {"backend": "mock_detect"},
                "_masks": [],
                "_scores": [],
                "_label_list": [],
                "_vis": rgb.copy(),
            }
            _ = gt_early
        else:
            det = detect_rgb(
                rgb,
                category,
                similar_answer=list(EMPTY_SIMILAR_ANSWER),
                conf_yolo=conf_yolo,
                iou_yolo=iou_yolo,
                save_overlay=pred_dir / "detect_vis.png",
            )
        # ################################
    except Exception as e:
        return {
            "pair_id": pair_id,
            "instance_id": pair.get("instance_id"),
            "category": category,
            "camera_mode": camera_mode,
            "view_id": view_id,
            "rgb": str(rgb_path),
            "bucket": "log_missing",
            "hit": False,
            "error": f"detect_failed: {e}",
            "view_meta": vmeta,
        }
    detect_s = time.time() - t0

    masks = det.pop("_masks")
    scores = det.pop("_scores")
    labs = det.pop("_label_list")
    det.pop("_vis", None)
    for i, m in enumerate(masks):
        np.save(pred_dir / f"pred_mask_{i:02d}.npy", np.asarray(m).astype(np.uint8))
    (pred_dir / "detect.json").write_text(json.dumps(det, indent=2) + "\n")

    # ################################
    # VLN adapt: NOW read GT for instance IoU scoring
    # ################################
    gt_path = _find_gt(view_dir)
    gt = load_mask(gt_path, resize_hw=PROD_HW) if gt_path else None
    is_target = [int(x) == 0 for x in labs]
    # Only score target-class masks for hit; still pass all for n_pred bookkeeping
    match = match_frame(
        gt_mask=gt,
        pred_masks=masks,
        pred_scores=scores,
        pred_labels_is_target=is_target,
        gt_visible=vmeta.get("gt_visible"),
        log_missing=(gt is None and pair.get("reliable_gt", True)),
    )

    # best pred mask for overlay
    best_i = match.get("best_pred_idx")
    pred_best = None
    if best_i is not None and 0 <= int(best_i) < len(masks):
        pred_best = np.asarray(masks[int(best_i)]).astype(bool)

    overlay_path = None
    if make_overlay_always or match.get("hit") or match.get("bucket") == "other_instance":
        ov = overlay(
            rgb,
            gt.astype(bool) if gt is not None else None,
            pred_best,
            title=f"{pair_id}|{camera_mode}|{view_id}|{match.get('bucket')}|iou={match.get('best_iou')}",
        )
        overlay_path = out_root / "overlays" / f"{pair_id}__{camera_mode}__{view_id}.png"
        overlay_path.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image

        Image.fromarray(ov).save(overlay_path)

    row = {
        "pair_id": pair_id,
        "instance_id": pair.get("instance_id"),
        "category": category,
        "category_raw": category_raw,
        "scene": pair.get("scene"),
        "camera_mode": camera_mode,
        "view_id": view_id,
        "rgb": str(rgb_path),
        "gt_mask": str(gt_path) if gt_path else None,
        "detect_s": round(detect_s, 3),
        "query_label": det.get("query_label"),
        "similar_answer": det.get("similar_answer"),
        "n_pred": det.get("n_pred"),
        "n_pred_target_class": det.get("n_pred_target_class"),
        "action_rejected": vmeta.get("action_rejected"),
        "viewpoint_id": vmeta.get("viewpoint_id", view_id),
        "t_start": vmeta.get("t_start"),
        "t_end": vmeta.get("t_end"),
        "overlay": str(overlay_path) if overlay_path else None,
        **match,
    }
    return row


def run(
    captures: Path,
    out: Path,
    *,
    conf_yolo: float = 0.3,
    iou_yolo: float = 0.5,
    pair_filter: Optional[str] = None,
    stop_after_first_pair: bool = False,
    mock_detect: bool = False,
) -> Dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    _write_locked_config(out / "configs" / "locked_detector_config.json", conf_yolo, iou_yolo)

    pairs = _load_index(captures)
    if pair_filter:
        pairs = [p for p in pairs if p.get("pair_id") == pair_filter]
    # only reliable_gt in denominator later; still process all for diagnostics
    frame_rows: List[dict] = []
    for pair in pairs:
        if pair.get("reliable_gt") is False:
            continue
        if not pair.get("category"):
            # try meta.json / manifest.json (A may use either)
            pdir0 = _pair_dir(captures, pair)
            for name in ("meta.json", "manifest.json"):
                md = pdir0 / name
                if md.is_file():
                    meta = json.loads(md.read_text())
                    pair = {**meta, **pair}
                    break
        pdir = _pair_dir(captures, pair)
        for mode in CAMERA_MODES:
            for view_id, view_dir in _iter_views(pdir / mode):
                row = process_view(
                    pair=pair,
                    camera_mode=mode,
                    view_id=view_id,
                    view_dir=view_dir,
                    out_root=out,
                    conf_yolo=conf_yolo,
                    iou_yolo=iou_yolo,
                    make_overlay_always=True,
                    mock_detect=mock_detect,
                )
                frame_rows.append(row)
                print(
                    f"[frame] {row.get('pair_id')} {mode}/{view_id} "
                    f"bucket={row.get('bucket')} iou={row.get('best_iou')}"
                )
        if stop_after_first_pair and frame_rows:
            break

    tables = out / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    frames_path = tables / "frames.jsonl"
    frames_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in frame_rows)
        + ("\n" if frame_rows else "")
    )

    inst_rows = build_instance_table(frames_path)
    summary = summarize(inst_rows)
    # ops counters if present
    summary["ops"] = {
        "n_frames": len(frame_rows),
        "n_action_rejected": sum(1 for r in frame_rows if r.get("action_rejected")),
        "n_unique_viewpoints": len(
            {(r.get("pair_id"), r.get("camera_mode"), r.get("viewpoint_id")) for r in frame_rows}
        ),
    }
    (tables / "instances.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in inst_rows)
        + ("\n" if inst_rows else "")
    )
    (tables / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    (tables / "summary.md").write_text(to_markdown(summary, inst_rows), encoding="utf-8")
    return {"n_frames": len(frame_rows), "n_instances": len(inst_rows), "summary": summary}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--conf_yolo", type=float, default=0.3)
    ap.add_argument("--iou_yolo", type=float, default=0.5)
    ap.add_argument("--pair_id", default=None)
    ap.add_argument("--stop_after_first_pair", action="store_true")
    ap.add_argument(
        "--mock_detect",
        action="store_true",
        help="skip VLM; empty preds (schema/IoU plumbing only)",
    )
    args = ap.parse_args()
    info = run(
        args.captures,
        args.out,
        conf_yolo=args.conf_yolo,
        iou_yolo=args.iou_yolo,
        pair_filter=args.pair_id,
        stop_after_first_pair=args.stop_after_first_pair,
        mock_detect=args.mock_detect,
    )
    print(json.dumps({"n_frames": info["n_frames"], "n_instances": info["n_instances"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
