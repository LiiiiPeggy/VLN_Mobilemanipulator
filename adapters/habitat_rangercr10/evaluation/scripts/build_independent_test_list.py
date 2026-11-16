#!/usr/bin/env python3
# ################################
# VLN adapt: build ~120-ep independent ObjectNav test list (no duplicate instances)
# ################################
"""Select up to N episodes per HM3D ObjectNav category with scene/instance diversity.

Does NOT invent force_spawn poses. Spawn feasibility is a separate gate from algorithm score.
Does NOT insert objects or rebuild scenes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OBJNAV = Path("/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2/val/content_json")
DEV24 = ROOT / "reports/startup_prior_e2e_20261107/episode_list.json"
OUT_LISTS = ROOT / "adapters/habitat_rangercr10/evaluation/lists"
OUT_REPORT = ROOT / "reports/ranger_category_eval_20261116/lists"

CATEGORIES = ["chair", "bed", "sofa", "plant", "toilet", "tv_monitor"]
GROUP = {
    "chair": "large_furniture",
    "bed": "large_furniture",
    "sofa": "large_furniture",
    "toilet": "large_furniture",
    "tv_monitor": "large_furniture",
    "plant": "large_furniture",  # ObjectNav plant is room-scale potted plant, not small object
}


def _load_pool(objnav_dir: Path):
    pool = []
    for f in sorted(objnav_dir.glob("*.json")):
        scene = f.stem
        data = json.loads(f.read_text())
        gbc = data.get("goals_by_category") or {}
        for ep in data.get("episodes") or []:
            cat = ep.get("object_category")
            if cat not in CATEGORIES:
                continue
            oid = (ep.get("info") or {}).get("closest_goal_object_id")
            gkey = f"{scene}.basis.glb_{cat}"
            goals = gbc.get(gkey) or []
            goal = next((g for g in goals if g.get("object_id") == oid), None)
            n_vp = len((goal or {}).get("view_points") or [])
            pool.append(
                {
                    "scene_filter": scene,
                    "category": cat,
                    "episode_id": str(ep.get("episode_id")),
                    "closest_goal_object_id": oid,
                    "geodesic_distance": (ep.get("info") or {}).get("geodesic_distance"),
                    "euclidean_distance": (ep.get("info") or {}).get("euclidean_distance"),
                    "n_view_points": n_vp,
                    "dataset_start_position": ep.get("start_position"),
                    "dataset_start_rotation": ep.get("start_rotation"),
                    "goal_position": (goal or {}).get("position"),
                    "object_name": (goal or {}).get("object_name"),
                    "room_name": (goal or {}).get("room_name"),
                    "group_large_furniture": GROUP[cat],
                    "spawn_status": "pending_validation",
                    "force_spawn_json": None,
                }
            )
    return pool


def _select(pool, per_cat: int, prefer_non_dev_scenes, dev_keys, dev_scenes):
    """Greedy: unique (scene, cat, object_id); prefer new scenes; then fill."""
    by_cat = defaultdict(list)
    for e in pool:
        by_cat[e["category"]].append(e)

    selected = []
    notes = {}
    for cat in CATEGORIES:
        cand = by_cat[cat]
        # sort: non-dev scenes first, then more view_points, then scene name / ep id
        def key(e):
            in_dev_scene = e["scene_filter"] in prefer_non_dev_scenes
            return (
                1 if in_dev_scene else 0,
                -int(e.get("n_view_points") or 0),
                e["scene_filter"],
                int(e["episode_id"]),
            )

        cand = sorted(cand, key=key)
        used_inst = set()
        used_scene = set()
        picked = []
        # pass 1: unique instance + unique scene
        for e in cand:
            inst = (e["scene_filter"], e["category"], e["closest_goal_object_id"])
            if e["closest_goal_object_id"] is None:
                continue
            if inst in used_inst:
                continue
            if e["scene_filter"] in used_scene:
                continue
            if len(picked) >= per_cat:
                break
            picked.append(e)
            used_inst.add(inst)
            used_scene.add(e["scene_filter"])
        # pass 2: allow scene reuse, still unique instance
        if len(picked) < per_cat:
            for e in cand:
                inst = (e["scene_filter"], e["category"], e["closest_goal_object_id"])
                if e["closest_goal_object_id"] is None or inst in used_inst:
                    continue
                if len(picked) >= per_cat:
                    break
                picked.append(e)
                used_inst.add(inst)
        # pass 3: if still short, unique episode keys only (do NOT duplicate same instance)
        shortfall = per_cat - len(picked)
        notes[cat] = {
            "target": per_cat,
            "selected": len(picked),
            "shortfall": max(0, shortfall),
            "unique_scenes": len({p["scene_filter"] for p in picked}),
            "unique_instances": len(
                {(p["scene_filter"], p["closest_goal_object_id"]) for p in picked}
            ),
        }
        for p in picked:
            p = dict(p)
            p["id"] = f"{p['scene_filter'][:4].lower()}_{p['category']}_{p['episode_id']}"
            # prettier stable id
            p["id"] = f"{p['scene_filter']}_{p['category']}_{p['episode_id']}"
            key = (p["scene_filter"], p["category"], p["episode_id"])
            p["overlaps_dev24_episode"] = key in dev_keys
            p["overlaps_dev24_scene"] = p["scene_filter"] in dev_scenes
            p["list_role"] = "independent_test"
            selected.append(p)
    return selected, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--objnav_dir", type=Path, default=DEFAULT_OBJNAV)
    ap.add_argument("--per_category", type=int, default=20)
    args = ap.parse_args()

    if not args.objnav_dir.is_dir():
        print(f"MISSING objnav dir: {args.objnav_dir}", file=sys.stderr)
        return 2

    dev = json.loads(DEV24.read_text())
    dev_eps = dev["episodes"]
    dev_keys = {(e["scene_filter"], e["category"], str(e["episode_id"])) for e in dev_eps}
    dev_scenes = {e["scene_filter"] for e in dev_eps}

    pool = _load_pool(args.objnav_dir)
    selected, notes = _select(pool, args.per_category, dev_scenes, dev_keys, dev_scenes)

    # dedupe ids if collision
    seen = set()
    for e in selected:
        if e["id"] in seen:
            e["id"] = e["id"] + f"_oid{e['closest_goal_object_id']}"
        seen.add(e["id"])

    OUT_LISTS.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.mkdir(parents=True, exist_ok=True)

    doc = {
        "name": "ranger_independent_hm3d_objectnav_v1",
        "created": "2026-11-16",
        "task": "ObjectNav-HM3D-v2-val",
        "robot_scale": 0.7,
        "scale_tag": "scaled_robot_proxy_070",
        "success_distance_m": 1.0,
        "distance_to": "VIEW_POINTS",
        "spl": "N/A_no_matched_geodesic_for_ranger_footprint",
        "per_category_target": args.per_category,
        "n_selected": len(selected),
        "category_notes": notes,
        "selection_rules": [
            "Up to N episodes per concrete category (chair/bed/sofa/plant/toilet/tv_monitor).",
            "Do not duplicate the same (scene, category, closest_goal_object_id).",
            "Do not pad by repeating instances when shortfall remains.",
            "Prefer scenes outside the 24-ep development set when possible.",
            "force_spawn_json left null until spawn validation (independent of algo score).",
            "large_furniture is a report grouping only; not double-counted in micro SR.",
            "cup/small-object is NOT in ObjectNav goals; see small_object_feasibility.md.",
        ],
        "overlap_with_dev24": {
            "dev24_n": len(dev_eps),
            "dev24_scenes": sorted(dev_scenes),
            "n_episode_key_overlap": sum(1 for e in selected if e["overlaps_dev24_episode"]),
            "n_scene_overlap": sum(1 for e in selected if e["overlaps_dev24_scene"]),
            "note": "Independent list is not claimed scene-disjoint from dev24; overlaps are recorded.",
        },
        "episodes": selected,
    }

    out_json = OUT_LISTS / "independent_test_list_v1.json"
    out_json.write_text(json.dumps(doc, indent=2) + "\n")
    (OUT_REPORT / "independent_test_list_v1.json").write_text(json.dumps(doc, indent=2) + "\n")

    # slim CSV
    import csv

    csv_path = OUT_REPORT / "independent_test_list_v1.csv"
    fields = [
        "id",
        "scene_filter",
        "category",
        "episode_id",
        "closest_goal_object_id",
        "n_view_points",
        "geodesic_distance",
        "overlaps_dev24_episode",
        "overlaps_dev24_scene",
        "spawn_status",
    ]
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(selected)

    # copy / reference dev24
    dev_ref = {
        "name": "dev24_regression",
        "role": "development_regression_only",
        "source": str(DEV24),
        "episodes": dev_eps,
        "caveat": "May share historical penetration issues; not the independent baseline.",
    }
    (OUT_LISTS / "dev24_regression_ref.json").write_text(json.dumps(dev_ref, indent=2) + "\n")

    md = OUT_REPORT / "independent_test_list_v1.md"
    lines = [
        "# 独立测试清单 v1（HM3D ObjectNav 六类）",
        "",
        f"- 目标：每类 {args.per_category} 例，共约 {6 * args.per_category}；实选 **{len(selected)}**。",
        f"- 与 dev24 episode 键重合：{doc['overlap_with_dev24']['n_episode_key_overlap']}；"
        f"场景重合条目：{doc['overlap_with_dev24']['n_scene_overlap']} / {len(selected)}。",
        "- `spawn_status=pending_validation`：合法 spawn 与任务可行性检查独立于算法成绩。",
        "- 不重复同一 `closest_goal_object_id` 凑数；不足则在 `category_notes` 记 shortfall。",
        "",
        "| category | selected | target | shortfall | unique_scenes | unique_instances |",
        "|----------|---------:|-------:|----------:|--------------:|-----------------:|",
    ]
    for cat in CATEGORIES:
        n = notes[cat]
        lines.append(
            f"| {cat} | {n['selected']} | {n['target']} | {n['shortfall']} | "
            f"{n['unique_scenes']} | {n['unique_instances']} |"
        )
    lines += ["", f"JSON：`{out_json.relative_to(ROOT)}`", ""]
    md.write_text("\n".join(lines) + "\n")
    print(f"wrote {out_json} n={len(selected)}")
    for cat, n in notes.items():
        print(cat, n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
