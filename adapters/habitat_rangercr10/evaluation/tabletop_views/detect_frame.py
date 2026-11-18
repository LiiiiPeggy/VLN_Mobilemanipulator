#!/usr/bin/env python3
# ################################
# VLN adapt: offline get_object call — target class only, empty similar_answer
# ################################
"""Run ApexNav production YOLOv7+MobileSAM path via get_object().

Does NOT read GT masks. Writes predictions JSON (+ optional overlay PNG).
Must run inside vln-rangercr10 (or host with ApexNav PYTHONPATH + VLM ports).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import numpy as np

_THIS = Path(__file__).resolve().parent
if str(_THIS) not in sys.path:
    sys.path.insert(0, str(_THIS))
from category_map import (  # noqa: E402
    EMPTY_SIMILAR_ANSWER,
    ensure_canonical,
)


# ################################
# VLN adapt: Habitat / get_object masks are 480x640 (H,W)
# ################################
PROD_HW = (480, 640)  # H, W


def _load_rgb(path: Path, *, resize_to_prod: bool = True) -> np.ndarray:
    import cv2

    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"cannot read RGB: {path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if resize_to_prod and (rgb.shape[0], rgb.shape[1]) != PROD_HW:
        rgb = cv2.resize(rgb, (PROD_HW[1], PROD_HW[0]), interpolation=cv2.INTER_LINEAR)
    return rgb


def _detector_cfg(
    conf_yolo: float = 0.3,
    iou_yolo: float = 0.5,
    agnostic_nms: bool = True,
) -> Any:
    # Match baselines/ApexNav/config/habitat_eval_hm3dv2.yaml detector.yolo
    return SimpleNamespace(
        yolo=SimpleNamespace(
            confidence_threshold_yolo=conf_yolo,
            iou_threshold_yolo=iou_yolo,
            agnostic_nms=agnostic_nms,
        ),
        groundingDINO=SimpleNamespace(
            confidence_threshold_dino=0.40,
            text_threshold=0.25,
        ),
    )


def detect_rgb(
    rgb: np.ndarray,
    target_label: str,
    *,
    similar_answer: Optional[List[str]] = None,
    conf_yolo: float = 0.3,
    iou_yolo: float = 0.5,
    save_overlay: Optional[Path] = None,
) -> Dict[str, Any]:
    """Call production get_object. similar_answer defaults to []."""
    canonical = ensure_canonical(target_label)
    similar = list(EMPTY_SIMILAR_ANSWER if similar_answer is None else similar_answer)
    cfg = _detector_cfg(conf_yolo=conf_yolo, iou_yolo=iou_yolo)

    # Import after path setup so clients bind to container localhost ports
    from vlm.utils.get_object_utils import get_object  # type: ignore

    vis, score_list, masks, label_list = get_object(
        canonical, rgb.copy(), cfg, similar
    )

    # label_list==0 → matched right_label (target class); >0 → similar only
    preds = []
    for i, (sc, m, lab) in enumerate(zip(score_list, masks, label_list)):
        is_target = int(lab) == 0
        mask_arr = np.asarray(m)
        preds.append(
            {
                "idx": i,
                "score": float(sc) if sc is not None else None,
                "label_list_code": int(lab),
                "is_target_class": bool(is_target),
                "mask_sum": int(mask_arr.astype(bool).sum()) if m is not None else 0,
                "mask_shape": list(mask_arr.shape) if m is not None else None,
            }
        )

    if save_overlay is not None:
        save_overlay.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image

        Image.fromarray(vis).save(save_overlay)

    return {
        "query_label": canonical,
        "similar_answer": similar,
        "detector": {
            "backend": "get_object→YOLOv7+MobileSAM",
            "conf_yolo": conf_yolo,
            "iou_yolo": iou_yolo,
            "agnostic_nms": True,
            "dino_used": False,  # empty similar + COCO target ⇒ YOLO only
            "note": "six-class LLM answer table unused; similar_answer=[] locked",
        },
        "image_hw": [int(rgb.shape[0]), int(rgb.shape[1])],
        "n_pred": len(preds),
        "n_pred_target_class": sum(1 for p in preds if p["is_target_class"]),
        "predictions": preds,
        # raw arrays kept separately by caller if needed for IoU
        "_masks": masks,
        "_scores": [float(s) for s in score_list],
        "_label_list": [int(x) for x in label_list],
        "_vis": vis,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rgb", type=Path, required=True)
    ap.add_argument("--label", required=True, help="cup|bowl|remote|bottle or alias")
    ap.add_argument("--out_json", type=Path, required=True)
    ap.add_argument("--out_overlay", type=Path, default=None)
    ap.add_argument("--out_masks_dir", type=Path, default=None)
    ap.add_argument("--conf_yolo", type=float, default=0.3)
    ap.add_argument("--iou_yolo", type=float, default=0.5)
    args = ap.parse_args()

    rgb = _load_rgb(args.rgb)
    result = detect_rgb(
        rgb,
        args.label,
        conf_yolo=args.conf_yolo,
        iou_yolo=args.iou_yolo,
        save_overlay=args.out_overlay,
    )
    masks = result.pop("_masks")
    scores = result.pop("_scores")
    labs = result.pop("_label_list")
    result.pop("_vis", None)

    if args.out_masks_dir:
        args.out_masks_dir.mkdir(parents=True, exist_ok=True)
        for i, m in enumerate(masks):
            np.save(args.out_masks_dir / f"pred_mask_{i:02d}.npy", np.asarray(m).astype(np.uint8))
        (args.out_masks_dir / "scores.json").write_text(
            json.dumps({"scores": scores, "label_list": labs}, indent=2) + "\n"
        )

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"wrote {args.out_json} n_pred={result['n_pred']} "
        f"n_target={result['n_pred_target_class']} query={result['query_label']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
