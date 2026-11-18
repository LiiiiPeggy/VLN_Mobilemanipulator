# ################################
# VLN adapt: tabletop capture path pins
# ################################
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ADAPTER = Path(__file__).resolve().parents[2]

HM3D_VAL = Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val")
HM3D_DATASET_CFG = Path(
    "/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/"
    "hm3d_annotated_basis.scene_dataset_config.json"
)
OBJNAV_CONTENT = Path(
    "/media/ubuntu/D/VLN_shared/datasets/objectnav/hm3d/v2/val/content_json"
)

# Large RGB / masks / depth live on D; git reports stay thin.
DATA_ROOT = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/tabletop_views_pilot")
CAPTURES_DATA = DATA_ROOT / "captures"
VERIFY_DATA = DATA_ROOT / "verify"

# Thin git-facing reports (lists, manifests, representative copies)
REPORT_ROOT = REPO / "reports/tabletop_views_pilot"
REPORT_CAPTURE = REPORT_ROOT / "capture"
REPORT_CAPTURES_LINK = REPORT_ROOT / "captures"  # may symlink to DATA

BASELINE_SHA = "492f53fd567c2be207a28a6fd5f9b6dbe7ee2da1"
ROBOT_SCALE = 0.7
PROTOCOL = "tabletop_views_pilot_v1"

# D layout: arm-mounted mode directory name
MODE_FIXED = "fixed_base_gimbal"
MODE_ARM_DISK = "arm_ee"  # on-disk (CAPTURE_LAYOUT.md)
MODE_ARM_NAME = "arm_view"  # conceptual / user brief


def scene_basis_glb(scene_id: str) -> Path:
    hits = sorted(HM3D_VAL.glob(f"*-{scene_id}/{scene_id}.basis.glb"))
    if not hits:
        raise FileNotFoundError(f"no basis.glb for scene {scene_id}")
    return hits[0]


def scene_semantic_txt(scene_id: str) -> Path:
    hits = sorted(HM3D_VAL.glob(f"*-{scene_id}/{scene_id}.semantic.txt"))
    if not hits:
        raise FileNotFoundError(f"no semantic.txt for scene {scene_id}")
    return hits[0]
