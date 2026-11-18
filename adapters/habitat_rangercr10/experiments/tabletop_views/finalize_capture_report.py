#!/usr/bin/env python3
# ################################
# VLN adapt: annotate reliable_gt + write C capture report
# ################################
from __future__ import annotations

import json
from pathlib import Path

DATA = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/tabletop_views_pilot/captures")
REPORT = Path("/workspace/VLN_Mobilemanipulator/reports/tabletop_views_pilot/capture")
CAPT_REPORT = Path("/workspace/VLN_Mobilemanipulator/reports/tabletop_views_pilot/captures")


def main() -> int:
    pairs = []
    rows = []
    for d in sorted(DATA.iterdir()):
        if not d.is_dir() or not (d / "capture_summary.json").is_file():
            continue
        cap = json.loads((d / "capture_summary.json").read_text())
        man = (
            json.loads((d / "manifest.json").read_text())
            if (d / "manifest.json").is_file()
            else {}
        )
        modes = (cap.get("capture") or {}).get("modes") or {}
        max_pix = 0
        n_visible_views = 0
        n_rejected = 0
        n_truncated = 0
        for _mode, md in modes.items():
            for f in md.get("frames") or []:
                pix = int(f.get("gt_pixels") or 0)
                max_pix = max(max_pix, pix)
                if pix >= 32:
                    n_visible_views += 1
                if f.get("blocked"):
                    n_rejected += 1
                if f.get("truncated"):
                    n_truncated += 1
        reliable = max_pix >= 32
        reason = (
            None
            if reliable
            else "no_ee_view_with_gt_pixels>=32_after_visibility_ranked_spawn"
        )
        man["reliable_gt"] = reliable
        man["gt_reliability_note"] = reason
        man["max_gt_pixels_any_view"] = max_pix
        (d / "manifest.json").write_text(json.dumps(man, indent=2) + "\n")
        (d / "meta.json").write_text(json.dumps(man, indent=2) + "\n")
        pairs.append(
            {
                "pair_id": man.get("pair_id", d.name),
                "instance_id": man.get("instance_id"),
                "category": man.get("category_raw") or man.get("category"),
                "scene": man.get("scene") or man.get("scene_id"),
                "reliable_gt": reliable,
                "notes": reason or "",
                "max_gt_pixels_any_view": max_pix,
                "n_visible_views": n_visible_views,
            }
        )
        rows.append(
            {
                **pairs[-1],
                "init_mae": ((cap.get("capture") or {}).get("init_frame_consistency") or {}).get(
                    "mae"
                ),
                "base_moved": man.get("base_moved_during_capture"),
                "fg_pixels": [
                    f.get("gt_pixels")
                    for f in (modes.get("fixed_base_gimbal") or {}).get("frames") or []
                ],
                "arm_pixels": [
                    f.get("gt_pixels") for f in (modes.get("arm_ee") or {}).get("frames") or []
                ],
                "n_rejected": n_rejected,
                "n_truncated": n_truncated,
            }
        )

    index = {
        "protocol": "tabletop_views_pilot_v1",
        "camera_modes": ["fixed_base_gimbal", "arm_ee"],
        "arm_mode_alias": "arm_view",
        "max_views_per_mode": 3,
        "captures_data_root": str(DATA),
        "n_pairs": len(pairs),
        "n_reliable_gt": sum(1 for p in pairs if p["reliable_gt"]),
        "pairs": pairs,
    }
    for root in (DATA, CAPT_REPORT, REPORT):
        root.mkdir(parents=True, exist_ok=True)
        (root / "pairing_index.json").write_text(json.dumps(index, indent=2) + "\n")
    (REPORT / "batch_summary.json").write_text(json.dumps(rows, indent=2) + "\n")

    lines = [
        "# Tabletop capture final report (Cursor C)",
        "",
        "- Baseline SHA pin: `492f53f`",
        "- Branch: `cursor/habitat-rangercr10-scale070`",
        "- Robot: RangerBox-CR10 scale 0.7, gripper fixed, executor `kinematic_collision_v1.2`",
        f"- Pairs captured: **{len(pairs)}** (reliable GT views: **{index['n_reliable_gt']}**)",
        "- Modes: `fixed_base_gimbal` + `arm_ee` (alias arm_view); 3 views each incl. shared init",
        f"- Data root: `{DATA}`",
        "- D index: `reports/tabletop_views_pilot/captures/pairing_index.json`",
        "",
        "## Coverage",
        "",
        "| pair_id | cat | reliable_gt | fg_pixels | arm_pixels | init_mae | notes |",
        "|---------|-----|-------------|-----------|------------|----------|-------|",
    ]
    for r in rows:
        note = r.get("notes") or ""
        lines.append(
            f"| `{r['pair_id']}` | {r['category']} | {r['reliable_gt']} | "
            f"{r['fg_pixels']} | {r['arm_pixels']} | {r.get('init_mae')} | {note} |"
        )
    lines += [
        "",
        "## Failed / empty-mask notes",
        "",
        "- Observation actions do not aim with GT; empty masks mean target out of view / occluded.",
        "- Pairs with max_gt_pixels=0 marked `reliable_gt=false`.",
        "- Gimbal/arm motion failures recorded without retries.",
        "",
        "## Reconstruct",
        "",
        "See `README.md` in this folder.",
        "",
    ]
    (REPORT / "CAPTURE_REPORT.md").write_text("\n".join(lines) + "\n")

    handoff_path = REPORT / "handoff_to_D_first_pair.json"
    if handoff_path.is_file():
        h = json.loads(handoff_path.read_text())
    else:
        h = {}
    h.update(
        {
            "status": "batch_ready",
            "first_pair_id": "CrMo8WxCyVb_cup_423",
            "all_pairs_index": "reports/tabletop_views_pilot/captures/pairing_index.json",
            "capture_report": "reports/tabletop_views_pilot/capture/CAPTURE_REPORT.md",
            "n_pairs_total": len(pairs),
            "n_reliable_gt": index["n_reliable_gt"],
        }
    )
    handoff_path.write_text(json.dumps(h, indent=2) + "\n")
    print("reliable", index["n_reliable_gt"], "/", len(pairs))
    for p in pairs:
        if not p["reliable_gt"]:
            print(" unreliable", p["pair_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
