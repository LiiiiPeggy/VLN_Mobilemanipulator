#!/usr/bin/env python3
# ################################
# VLN adapt: audit cup/small-object feasibility without inserting assets
# ################################
"""Check whether cup-like objects exist as HM3D semantic geometry and as evaluable goals.

Does not insert meshes or rewrite scenes. Adding a category string alone is NOT a new task.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OBJNAV = Path("/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2/val/content_json")
SEM_ROOT = Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val")
OUT = ROOT / "reports/ranger_category_eval_20261116/tables"

CUP_RE = re.compile(r"\b(cup|mug|coffee mug|pen cup)\b", re.I)
SMALL_RE = re.compile(
    r"\b(cup|mug|glass|bottle|bowl|plate|book|remote control|laptop|vase|telephone)\b",
    re.I,
)


def _parse_name(line: str) -> str | None:
    # HM3D: id,hex,"name",region
    m = re.search(r',"([^"]+)",\d+\s*$', line)
    return m.group(1) if m else None


def main() -> int:
    scenes = sorted(p.stem for p in OBJNAV.glob("*.json"))
    objectnav_cats = Counter()
    for f in OBJNAV.glob("*.json"):
        for ep in json.loads(f.read_text()).get("episodes") or []:
            objectnav_cats[ep.get("object_category")] += 1

    cup_labels = Counter()
    small_labels = Counter()
    per_scene = {}
    for scene in scenes:
        hits = list(SEM_ROOT.glob(f"*-{scene}/{scene}.semantic.txt"))
        if not hits:
            continue
        cup = Counter()
        small = Counter()
        for line in hits[0].read_text(errors="ignore").splitlines():
            name = _parse_name(line)
            if not name:
                continue
            if CUP_RE.search(name):
                cup[name] += 1
                cup_labels[name] += 1
            if SMALL_RE.search(name):
                small[name] += 1
                small_labels[name] += 1
        per_scene[scene] = {"cup_like": dict(cup), "small_like": dict(small)}

    cup_scenes = [s for s, d in per_scene.items() if d["cup_like"]]
    payload = {
        "objectnav_goal_categories": dict(objectnav_cats),
        "objectnav_has_cup_goal": "cup" in objectnav_cats or "mug" in objectnav_cats,
        "semantic_cup_like_label_counts": dict(cup_labels),
        "semantic_small_like_top": small_labels.most_common(30),
        "n_objectnav_scenes_with_cup_like_semantics": len(cup_scenes),
        "cup_like_scenes": cup_scenes,
        "per_scene_cup_like": {s: per_scene[s]["cup_like"] for s in cup_scenes},
        "evaluability": {
            "has_mesh_geometry": True if cup_labels else False,
            "has_objectnav_episode_goals_viewpoints": False,
            "has_official_success_protocol_for_cup": False,
            "verdict": (
                "NOT_TASK_READY: semantic instances exist in a minority of val scenes, "
                "but HM3D ObjectNav v2 provides neither cup goals nor view_points. "
                "Do not treat adding a category string as a new task. "
                "A separate minimal data-construction proposal is required "
                "(instance IDs, view_points or EE confirmation envelope, spawn checks)."
            ),
        },
        "minimal_data_construction_if_needed": [
            "Enumerate semantic instance IDs for cup/mug in selected scenes (read-only).",
            "Define evaluable goal: either hand-authored view_points near instance, "
            "or an EE/camera observability envelope — not base-only ObjectNav radius alone.",
            "Do not insert foreign meshes into HM3D; prefer existing semantic geometry.",
            "Keep cup tasks out of the 120-ep ObjectNav independent list until goals exist.",
            "Observation-condition labels (height/occlusion/ambiguity) must be annotatable "
            "on the same instances before claiming arm benefit.",
        ],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "small_object_feasibility.json").write_text(json.dumps(payload, indent=2) + "\n")
    md = OUT / "small_object_feasibility.md"
    md.write_text(
        "\n".join(
            [
                "# 小目标 / 杯子数据可行性",
                "",
                "## ObjectNav 官方目标",
                "",
                f"HM3D ObjectNav v2 val 仅六类：`{sorted(objectnav_cats)}`。"
                "**无 cup/mug 目标、无对应 view_points 协议。**",
                "",
                "## 语义几何（只读审计）",
                "",
                f"- ObjectNav 36 景中含 cup/mug 类语义标签的场景数：**{len(cup_scenes)}**。",
                f"- 标签计数：`{dict(cup_labels)}`。",
                "- 有网格语义 ≠ 有可评测任务（缺官方 goals / viewpoints / 成功判据）。",
                "",
                "## 结论",
                "",
                payload["evaluability"]["verdict"],
                "",
                "## 若要建设（最小方案，待立项）",
                "",
                *[f"- {x}" for x in payload["minimal_data_construction_if_needed"]],
                "",
            ]
        )
        + "\n"
    )
    print(md)
    print("cup_scenes", len(cup_scenes), "objectnav_has_cup", payload["objectnav_has_cup_goal"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
