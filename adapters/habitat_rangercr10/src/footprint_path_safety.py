"""Offline Ranger footprint sweep safety on recorded ApexNav paths (GT eval only).

################################
Replays Habitat poses from steps.jsonl with oriented chassis rectangle (+ optional
arm reach circle) against PathFinder / mesh. Does NOT feed results to ApexNav.
################################
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import magnum as mn
import numpy as np
from PIL import Image, ImageDraw

from .constants import URDF_HABITAT
from .ranger_footprint import (
    ARM_HOME_XY_REACH_M,
    CHASSIS_HALF_L,
    CHASSIS_HALF_W,
    CHASSIS_CIRCUM_R,
    footprint_report,
    oriented_rect_corners,
)
from .robot_scale import footprint_at_scale


def _load_jsonl(path: Path) -> List[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _interp_poses(p0: dict, p1: dict, n: int) -> List[Tuple[float, float, float]]:
    out = []
    y0, y1 = float(p0["yaw"]), float(p1["yaw"])
    dy = (y1 - y0 + math.pi) % (2 * math.pi) - math.pi
    for i in range(1, n + 1):
        u = i / float(n)
        x = float(p0["x"]) + u * (float(p1["x"]) - float(p0["x"]))
        z = float(p0["z"]) + u * (float(p1["z"]) - float(p0["z"]))
        yaw = y0 + u * dy
        out.append((x, z, yaw))
    return out


def _corner_clearances(
    pf,
    x: float,
    z: float,
    yaw: float,
    floor_y: float,
    half_l: float = CHASSIS_HALF_L,
    half_w: float = CHASSIS_HALF_W,
) -> Dict[str, Any]:
    """Min distance_to_closest_obstacle at chassis corners + center (navmesh GT)."""
    y = float(floor_y) + 0.05
    pts = [(x, z, "center")]
    for i, (cx, cz) in enumerate(oriented_rect_corners(x, z, yaw, half_l=half_l, half_w=half_w)):
        pts.append((float(cx), float(cz), f"c{i}"))
    # mid-edge samples
    for sx, sz in ((half_l, 0.0), (-half_l, 0.0), (0.0, half_w), (0.0, -half_w)):
        fx, fz = math.sin(yaw), math.cos(yaw)
        rx, rz = math.cos(yaw), -math.sin(yaw)
        # ROS left = -right
        px = x + sx * fx - sz * rx
        pz = z + sx * fz - sz * rz
        pts.append((px, pz, "edge"))
    ds = []
    nav_flags = []
    for px, pz, _ in pts:
        p = mn.Vector3(float(px), y, float(pz))
        try:
            nav = bool(pf.is_navigable(p))
            d = float(pf.distance_to_closest_obstacle(p))
        except Exception:
            nav, d = False, 0.0
        ds.append(d)
        nav_flags.append(nav)
    return {
        "min_clearance_m": float(min(ds) if ds else 0.0),
        "center_clearance_m": float(ds[0]) if ds else 0.0,
        "all_corners_navigable": bool(all(nav_flags)),
        "n_samples": len(ds),
    }


def analyze_run(
    run_dir: Path,
    out_dir: Path,
    scene_glb: Optional[str] = None,
    gpu: int = 0,
    inter_samples: int = 4,
    robot_scale: Optional[float] = None,
) -> Dict[str, Any]:
    import habitat_sim

    out_dir.mkdir(parents=True, exist_ok=True)
    steps = _load_jsonl(run_dir / "steps.jsonl")
    acts = _load_jsonl(run_dir / "actions.jsonl")
    start_pose = json.loads((run_dir / "start_pose.json").read_text())
    spawn = start_pose["spawn"]
    floor_y = float(spawn["floor_y"])
    # ################################
    # Honor recorded robot_scale (0.7 proxy uses scaled half-width criterion).
    # ################################
    if robot_scale is None:
        robot_scale = float(
            start_pose.get("robot_scale")
            or spawn.get("robot_scale")
            or 1.0
        )
    fp = footprint_at_scale(float(robot_scale))
    half_l = float(fp["chassis_half_length_m"])
    half_w = float(fp["chassis_half_width_m"])
    arm_reach = float(fp["arm_home_xy_reach_m"])
    if scene_glb is None:
        ep = json.loads((run_dir / "episode.json").read_text())
        sid = Path(ep["scene_id"]).name.replace(".basis.glb", "")
        # resolve under hm3d val
        root = Path("/media/ubuntu/D/VLN_shared/datasets/scene_datasets/hm3d/val")
        hits = list(root.glob(f"*-{sid}/{sid}.basis.glb"))
        if not hits:
            hits = list(root.glob(f"**/{sid}.basis.glb"))
        scene_glb = str(hits[0])

    backend = habitat_sim.SimulatorConfiguration()
    backend.scene_id = scene_glb
    backend.enable_physics = False
    backend.gpu_device_id = gpu
    cfg = habitat_sim.Configuration(backend, [habitat_sim.agent.AgentConfiguration()])
    sim = habitat_sim.Simulator(cfg)
    try:
        pf = sim.pathfinder
        rows = []
        unsafe = 0
        min_gap = 1e9
        for i in range(1, len(steps)):
            a = acts[i]
            if a.get("phase") not in ("explore_planner", "init_lookaround"):
                continue
            # only base-changing actions
            if a.get("name") not in ("MOVE_FORWARD", "TURN_LEFT", "TURN_RIGHT"):
                continue
            p0, p1 = steps[i - 1]["base"], steps[i]["base"]
            samples = _interp_poses(p0, p1, inter_samples)
            sample_rows = []
            for x, z, yaw in samples:
                c = _corner_clearances(pf, x, z, yaw, floor_y, half_l=half_l, half_w=half_w)
                sample_rows.append(c)
                min_gap = min(min_gap, c["min_clearance_m"])
            worst = min(sample_rows, key=lambda r: r["min_clearance_m"])
            # Safety vs half-width: clearance at corner should be ≥0 for navmesh baked at
            # agent radius; we recompute navmesh at r=0 for raw? Existing baked mesh is
            # ~0.18. For Ranger, require center clearance ≥ half_width on baked mesh as
            # conservative proxy OR recompute at 0.05 then check corners.
            ok = worst["min_clearance_m"] >= 0.05 and worst["all_corners_navigable"]
            if not ok:
                unsafe += 1
            rows.append(
                {
                    "step": steps[i]["step"],
                    "action": a.get("name"),
                    "phase": a.get("phase"),
                    "worst_min_clearance_m": worst["min_clearance_m"],
                    "worst_center_clearance_m": worst["center_clearance_m"],
                    "safe_proxy": ok,
                }
            )

        # Recompute navmesh at tiny radius for geometric clearance estimate
        settings = habitat_sim.NavMeshSettings()
        settings.set_defaults()
        settings.agent_radius = 0.05
        settings.agent_height = 1.5
        sim.recompute_navmesh(sim.pathfinder, settings)
        pf2 = sim.pathfinder
        rows2 = []
        unsafe2 = 0
        min_gap2 = 1e9
        for i in range(1, len(steps)):
            a = acts[i]
            if a.get("phase") != "explore_planner":
                continue
            if a.get("name") not in ("MOVE_FORWARD", "TURN_LEFT", "TURN_RIGHT"):
                continue
            p0, p1 = steps[i - 1]["base"], steps[i]["base"]
            samples = _interp_poses(p0, p1, inter_samples)
            sample_rows = []
            for x, z, yaw in samples:
                c = _corner_clearances(pf2, x, z, yaw, floor_y, half_l=half_l, half_w=half_w)
                sample_rows.append(c)
                min_gap2 = min(min_gap2, c["min_clearance_m"])
            worst = min(sample_rows, key=lambda r: r["min_clearance_m"])
            # Oriented footprint: need clearance ≥ 0 at corners on thin navmesh, AND
            # center clearance ≥ half_width for body disk proxy.
            body_ok = worst["center_clearance_m"] >= half_w
            corner_ok = worst["min_clearance_m"] >= 0.02 and worst["all_corners_navigable"]
            ok = body_ok and corner_ok
            if not ok:
                unsafe2 += 1
            rows2.append(
                {
                    "step": steps[i]["step"],
                    "action": a.get("name"),
                    "worst_min_clearance_m": worst["min_clearance_m"],
                    "worst_center_clearance_m": worst["center_clearance_m"],
                    "body_halfwidth_ok": body_ok,
                    "corners_ok": corner_ok,
                    "safe_oriented_proxy": ok,
                }
            )

        n = max(len(rows2), 1)
        rep = {
            "run_dir": str(run_dir),
            "scene_glb": scene_glb,
            "robot_scale": float(robot_scale),
            "scale_tag": fp["scale_tag"],
            "footprint": fp,
            "method": "GT navmesh clearance at chassis corners/edges along interpolated SE2; offline eval only",
            "baked_navmesh_proxy": {
                "n_base_actions": len(rows),
                "unsafe_count": unsafe,
                "safe_ratio": float((len(rows) - unsafe) / max(len(rows), 1)),
                "min_clearance_m": float(min_gap if rows else float("nan")),
                "note": "Baked HM3D navmesh ~agent 0.18; optimistic for Ranger.",
                "per_action": rows,
            },
            "recomputed_r005_oriented_proxy": {
                "n_explore_base_actions": len(rows2),
                "unsafe_count": unsafe2,
                "safe_ratio": float((len(rows2) - unsafe2) / n),
                "min_corner_clearance_m": float(min_gap2 if rows2 else float("nan")),
                "criterion": f"center_clearance>=half_width({half_w:.4f}) AND corners navigable on r=0.05 navmesh",
                "per_action": rows2,
            },
            "arm_note": (
                f"Arm horizontal reach ~{arm_reach} m not swept as polygon; "
                "LOOK poses may collide above chassis footprint — reported separately as TODO."
            ),
        }
        (out_dir / "footprint_path_safety.json").write_text(json.dumps(rep, indent=2))
        # simple plot of clearances
        if rows2:
            w, h = 640, 240
            im = Image.new("RGB", (w, h), (255, 255, 255))
            dr = ImageDraw.Draw(im)
            xs = [r["worst_center_clearance_m"] for r in rows2]
            for i, v in enumerate(xs):
                x = int(i / max(len(xs) - 1, 1) * (w - 40) + 20)
                y = int(h - 20 - min(v, 1.5) / 1.5 * (h - 40))
                color = (0, 160, 0) if v >= half_w else (200, 0, 0)
                dr.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)
            y_thr = int(h - 20 - half_w / 1.5 * (h - 40))
            dr.line([20, y_thr, w - 20, y_thr], fill=(0, 0, 200))
            dr.text((10, 5), "center clearance along explore actions (blue=half_width)", fill=(0, 0, 0))
            im.save(out_dir / "center_clearance_trace.png")
        return rep
    finally:
        sim.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--run_dir",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_yr17_openband_20261105_012302",
    )
    p.add_argument(
        "--out_dir",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/footprint_path_safety/yr17_openband",
    )
    p.add_argument("--gpu", type=int, default=0)
    args = p.parse_args(argv)
    rep = analyze_run(Path(args.run_dir), Path(args.out_dir), gpu=args.gpu)
    print(
        json.dumps(
            {
                "baked_safe_ratio": rep["baked_navmesh_proxy"]["safe_ratio"],
                "oriented_safe_ratio": rep["recomputed_r005_oriented_proxy"]["safe_ratio"],
                "oriented_unsafe": rep["recomputed_r005_oriented_proxy"]["unsafe_count"],
                "min_corner_clearance_m": rep["recomputed_r005_oriented_proxy"]["min_corner_clearance_m"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
