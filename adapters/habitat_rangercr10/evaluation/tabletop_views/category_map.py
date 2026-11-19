#!/usr/bin/env python3
# ################################
# VLN adapt: tabletop pilot — category alias → COCO query label
# ################################
"""Canonical query terms for v1: cup, bowl, remote, bottle.

Scene labels like mug/coffee mug map to cup; remote control → remote.
Only the canonical target class is scored (get_object right_label; similar=[]).
"""

from __future__ import annotations

from typing import Optional

# ################################
# VLN adapt: locked query set for pilot v1
# ################################
CANONICAL_QUERIES = ("cup", "bowl", "remote", "bottle")

# Scene / HM3D style aliases → canonical COCO query
ALIAS_TO_CANONICAL = {
    "cup": "cup",
    "mug": "cup",
    "coffee mug": "cup",
    "coffee_mug": "cup",
    "bowl": "bowl",
    # ################################
    # VLN adapt: capture labels used in pairing_index (must enter YOLO queries)
    # ################################
    "decorative bowl": "bowl",
    "remote": "remote",
    "remote control": "remote",
    "remote_control": "remote",
    "tv remote": "remote",
    "bottle": "bottle",
    "water bottle": "bottle",
    "bottle of detergent": "bottle",
}

# Empty similar_answer: do NOT expand to LLM near-synonyms for scoring.
EMPTY_SIMILAR_ANSWER: list = []


def canonicalize(label: Optional[str]) -> Optional[str]:
    if label is None:
        return None
    key = str(label).strip().lower().replace("_", " ")
    key = " ".join(key.split())
    if key in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[key]
    # already canonical?
    if key in CANONICAL_QUERIES:
        return key
    return None


def ensure_canonical(label: str) -> str:
    c = canonicalize(label)
    if c is None:
        raise ValueError(
            f"unsupported tabletop label {label!r}; "
            f"allowed aliases → {sorted(set(ALIAS_TO_CANONICAL.values()))}"
        )
    return c
