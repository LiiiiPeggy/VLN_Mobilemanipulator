#!/usr/bin/env python3
"""Recompute Habitat navmeshes for MP3D scenes that only ship as .glb.

SG-Nav ObjectNav DISTANCE_TO_GOAL calls pathfinder.geodesic_distance; without
a loaded navmesh habitat-sim segfaults on env.reset().

Default agent matches SG-Nav challenge_objectnav2021.local.rgbd.yaml
(HEIGHT=0.88, RADIUS=0.18).

Usage (inside vln-sgnav):
  python /workspace/SG-Nav/../scripts/...  # or copy path
  python scripts/build_mp3d_navmeshes.py --root data/MatterPort3D/mp3d
"""
from __future__ import annotations

import argparse
import os
import time

import habitat_sim


def build_one(root: str, scene_id: str, radius: float, height: float, force: bool) -> None:
    glb = os.path.join(root, scene_id, f"{scene_id}.glb")
    out = os.path.join(root, scene_id, f"{scene_id}.navmesh")
    if not os.path.isfile(glb):
        raise FileNotFoundError(glb)
    if (not force) and os.path.isfile(out) and os.path.getsize(out) > 1000:
        print(f"SKIP {scene_id} exists size={os.path.getsize(out)}")
        return

    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = glb
    backend.enable_physics = False
    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.height = height
    agent_cfg.radius = radius
    cfg = habitat_sim.Configuration(backend, [agent_cfg])

    t0 = time.time()
    print(f"BUILD {scene_id} ...", flush=True)
    sim = habitat_sim.Simulator(cfg)
    settings = habitat_sim.NavMeshSettings()
    settings.set_defaults()
    settings.agent_radius = radius
    settings.agent_height = height
    settings.agent_max_climb = 0.2
    settings.agent_max_slope = 45.0
    ok = sim.recompute_navmesh(sim.pathfinder, settings)
    if (not ok) or (not sim.pathfinder.is_loaded):
        sim.close()
        raise RuntimeError(f"navmesh recompute failed for {scene_id}")
    sim.pathfinder.save_nav_mesh(out)
    sim.close()
    print(f"SAVED {out} size={os.path.getsize(out)} dt={time.time() - t0:.1f}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="data/MatterPort3D/mp3d")
    ap.add_argument("--radius", type=float, default=0.18)
    ap.add_argument("--height", type=float, default=0.88)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    scenes = sorted(
        d for d in os.listdir(args.root) if os.path.isdir(os.path.join(args.root, d))
    )
    for sid in scenes:
        build_one(args.root, sid, args.radius, args.height, args.force)
    print("DONE", len(scenes), "scenes")


if __name__ == "__main__":
    main()
