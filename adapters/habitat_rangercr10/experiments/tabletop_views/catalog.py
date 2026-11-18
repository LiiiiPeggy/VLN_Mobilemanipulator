#!/usr/bin/env python3
# ################################
# VLN adapt: enumerate HM3D semantic instances for cup/bowl/remote/bottle
# ################################
"""Read-only catalog from Habitat SemanticScene (annotated HM3D).

Does not look at detector outputs. Writes JSON catalog under reports/.../capture/.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import habitat_sim
import numpy as np

_THIS = Path(__file__).resolve().parent
if str(_THIS) not in sys.path:
    sys.path.insert(0, str(_THIS))
_ADAPTER_SRC = str(_THIS.parents[1])
if _ADAPTER_SRC not in sys.path:
    sys.path.insert(0, _ADAPTER_SRC)

from category_rules import CANONICAL, classify_label, instance_key  # noqa: E402
from paths import (  # noqa: E402
    HM3D_DATASET_CFG,
    OBJNAV_CONTENT,
    REPORT_CAPTURE,
    scene_basis_glb,
)


def objectnav_scenes() -> List[str]:
    return sorted(p.stem for p in OBJNAV_CONTENT.glob("*.json"))


def _load_semantic_only(scene_id: str, gpu: int = 0):
    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = str(scene_basis_glb(scene_id))
    backend.scene_dataset_config_file = str(HM3D_DATASET_CFG)
    backend.enable_physics = False
    backend.gpu_device_id = int(gpu)
    # ################################
    # COLOR sensor required: with SEMANTIC-only, HM3D object AABBs stay zero.
    # ################################
    specs = []
    for uuid, stype in (
        ("rgb", habitat_sim.SensorType.COLOR),
        ("sem", habitat_sim.SensorType.SEMANTIC),
    ):
        s = habitat_sim.CameraSensorSpec()
        s.uuid = uuid
        s.sensor_type = stype
        s.resolution = [128, 128]
        s.hfov = 60.0
        specs.append(s)
    agent = habitat_sim.agent.AgentConfiguration()
    agent.sensor_specifications = specs
    sim = habitat_sim.Simulator(habitat_sim.Configuration(backend, [agent]))
    return sim


def enumerate_scene(scene_id: str, gpu: int = 0) -> List[Dict[str, Any]]:
    sim = _load_semantic_only(scene_id, gpu=gpu)
    out: List[Dict[str, Any]] = []
    try:
        # ################################
        # Force one observation so HM3D semantic object AABBs populate.
        # ################################
        sim.get_sensor_observations()
        ss = sim.semantic_scene
        for o in ss.objects or []:
            if o is None or o.category is None:
                continue
            label = o.category.name()
            canon = classify_label(label)
            if canon is None:
                continue
            c = np.asarray(o.aabb.center, dtype=np.float64)
            sz = np.asarray(o.aabb.sizes, dtype=np.float64)
            if float(np.linalg.norm(sz)) < 1e-6:
                continue
            out.append(
                {
                    "scene_id": scene_id,
                    "semantic_id": int(o.semantic_id),
                    "object_id_str": str(o.id),
                    "label": label,
                    "canonical": canon,
                    "instance_key": instance_key(scene_id, int(o.semantic_id)),
                    "center_hab": [float(c[0]), float(c[1]), float(c[2])],
                    "sizes_hab": [float(sz[0]), float(sz[1]), float(sz[2])],
                    "height_agl_guess": None,  # filled after floor snap at center xz
                }
            )
    finally:
        try:
            sim.close()
        except Exception:
            pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gpu", type=int, default=0)
    ap.add_argument(
        "--scenes",
        nargs="*",
        default=None,
        help="subset of scene ids; default=all ObjectNav val scenes",
    )
    ap.add_argument("--out", type=Path, default=REPORT_CAPTURE / "instance_catalog.json")
    args = ap.parse_args()

    scenes = args.scenes or objectnav_scenes()
    by_cat: Dict[str, List[dict]] = defaultdict(list)
    all_rows: List[dict] = []
    errors: List[dict] = []
    for i, sid in enumerate(scenes):
        print(f"[{i+1}/{len(scenes)}] {sid}", flush=True)
        try:
            rows = enumerate_scene(sid, gpu=args.gpu)
        except Exception as e:
            errors.append({"scene_id": sid, "error": f"{type(e).__name__}: {e}"})
            print("  ERR", e, flush=True)
            continue
        print(f"  n={len(rows)}", flush=True)
        for r in rows:
            by_cat[r["canonical"]].append(r)
            all_rows.append(r)

    payload = {
        "n_scenes_scanned": len(scenes),
        "n_instances": len(all_rows),
        "counts_by_canonical": {c: len(by_cat[c]) for c in CANONICAL},
        "scenes_by_canonical": {
            c: sorted({r["scene_id"] for r in by_cat[c]}) for c in CANONICAL
        },
        "errors": errors,
        "instances": all_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
