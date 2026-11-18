# ################################
# VLN adapt: category include/exclude for tabletop pilot (scene labels)
# ################################
from __future__ import annotations

import re
from typing import Optional, Tuple

# Canonical categories for selection / D scoring
CANONICAL = ("cup", "bowl", "remote", "bottle")

# Exact label match (case-insensitive) after strip. pen cup excluded.
CUP_LABELS = frozenset({"cup", "mug", "coffee mug"})
BOWL_LABELS = frozenset({"bowl", "bowl of fruit", "fruit bowl", "decorative bowl"})
REMOTE_LABELS = frozenset({"remote control", "remote"})
# Prefer plain bottle / wine bottle; soap/detergent allowed but tagged bathroom-ish
BOTTLE_LABELS = frozenset(
    {
        "bottle",
        "wine bottle",
        "soap bottle",
        "bottle of soap",
        "bottle of detergent",
    }
)

EXCLUDE_EXACT = frozenset({"pen cup", "sauna bowl"})

_LABEL_TO_CANON = {}
for lab in CUP_LABELS:
    _LABEL_TO_CANON[lab] = "cup"
for lab in BOWL_LABELS:
    _LABEL_TO_CANON[lab] = "bowl"
for lab in REMOTE_LABELS:
    _LABEL_TO_CANON[lab] = "remote"
for lab in BOTTLE_LABELS:
    _LABEL_TO_CANON[lab] = "bottle"


def normalize_label(name: str) -> str:
    return " ".join(str(name).strip().lower().replace("_", " ").split())


def classify_label(name: str) -> Optional[str]:
    key = normalize_label(name)
    if key in EXCLUDE_EXACT:
        return None
    return _LABEL_TO_CANON.get(key)


def instance_key(scene_id: str, semantic_id: int) -> str:
    return f"{scene_id}:{int(semantic_id)}"


def pair_id(scene_id: str, canonical: str, semantic_id: int) -> str:
    return f"{scene_id}_{canonical}_{int(semantic_id)}"
