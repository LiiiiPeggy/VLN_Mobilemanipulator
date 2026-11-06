#!/usr/bin/env python3
"""Independent validation of camera coord / intrinsics (no shared buggy formula).

################################
Analytic checks only (no Habitat required). Writes JSON under --out.
Does NOT modify planner / scale / PPO.
################################
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.camera_model import (  # noqa: E402
    REF_K_640x480_HFOV79,
    legacy_broken_fy_from_hfov_aspect,
    optical_ray_dir,
    pinhole_from_hfov,
    project_optical,
    rx_pi,
    unproject_habitat_render,
    unproject_optical,
)
from src.coord_habitat_ros import (  # noqa: E402
    hab_optical_rot_to_ros,
    hab_pos_to_ros,
    hab_rot_to_ros,
)


def _angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    return float(math.degrees(math.acos(float(np.clip(np.dot(a, b), -1, 1)))))


def test_intrinsics() -> dict:
    k = pinhole_from_hfov(640, 480, 79.0)
    legacy = legacy_broken_fy_from_hfov_aspect(640, 480, 79.0)
    ok_fx = abs(k["fx"] - 388.191) < 0.05
    ok_fy = abs(k["fy"] - k["fx"]) < 1e-9
    ok_vfov = abs(k["vfov_deg"] - 63.453) < 0.05
    return {
        "K": k,
        "legacy_wrong": legacy,
        "checks": {
            "fx_approx_388p191": ok_fx,
            "fy_equals_fx": ok_fy,
            "vfov_approx_63p453": ok_vfov,
            "legacy_fy_differs": abs(legacy["fy"] - k["fy"]) > 1.0,
        },
        "pass": bool(ok_fx and ok_fy and ok_vfov),
    }


def test_optical_vs_hab_rot() -> dict:
    """C@R@C.T must NOT equal C@R for optical pose mapping."""
    # Random Habitat optical orientation
    yaw, pitch, roll = 0.4, -0.3, 0.1
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=float)
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]], dtype=float)
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]], dtype=float)
    R_opt = Rz @ Ry @ Rx
    R_wrong = hab_rot_to_ros(R_opt)
    R_right = hab_optical_rot_to_ros(R_opt)
    C = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=float)
    p_opt = np.array([0.1, -0.2, 2.5])
    world_hab = R_opt @ p_opt
    world_ros_ref = C @ world_hab
    err_right = float(np.linalg.norm(R_right @ p_opt - world_ros_ref))
    err_wrong = float(np.linalg.norm(R_wrong @ p_opt - world_ros_ref))
    return {
        "err_optical_map_m": err_right,
        "err_legacy_hab_rot_to_ros_m": err_wrong,
        "pass": err_right < 1e-9 and err_wrong > 0.1,
    }


def test_render_optical_rx() -> dict:
    R_opt = np.eye(3)
    R_ren = R_opt @ rx_pi()
    # Recover optical
    R_back = R_ren @ rx_pi()
    return {
        "recover_err": float(np.linalg.norm(R_back - R_opt)),
        "pass": float(np.linalg.norm(R_back - R_opt)) < 1e-12,
    }


def test_project_unproject() -> dict:
    K = REF_K_640x480_HFOV79
    rows = []
    ok = True
    for u, v, d in [
        (320, 240, 1.5),
        (0, 0, 2.0),
        (639, 479, 3.0),
        (100, 400, 0.8),
        (500, 50, 4.5),
    ]:
        p = unproject_optical(u, v, d, K)
        uu, vv = project_optical(p, K)
        eu, ev = abs(uu - u), abs(vv - v)
        rows.append({"u": u, "v": v, "d": d, "eu": eu, "ev": ev})
        if eu > 1e-6 or ev > 1e-6:
            ok = False
    # render/optical consistency of look direction
    p_r = unproject_habitat_render(320, 240, 2.0, K)
    p_o = unproject_optical(320, 240, 2.0, K)
    # p_r should be Rx(π) @ p_o
    p_r_from_o = rx_pi() @ p_o
    return {
        "pixels": rows,
        "render_optical_rx_err": float(np.linalg.norm(p_r - p_r_from_o)),
        "pass": ok and float(np.linalg.norm(p_r - p_r_from_o)) < 1e-9,
    }


def test_agl_translation() -> dict:
    p = np.array([1.0, -0.95, 2.0])
    floor = -0.95
    ros = hab_pos_to_ros(p, floor_y=floor)
    # Z should be AGL=0 at floor
    return {
        "ros": ros.tolist(),
        "z_agl_at_floor": float(ros[2]),
        "pass": abs(float(ros[2])) < 1e-12,
    }


def test_ray_angles() -> dict:
    K = REF_K_640x480_HFOV79
    # center vs edge horizontal angle should be ±HFOV/2
    c = optical_ray_dir(320, 240, K)
    l = optical_ray_dir(0, 240, K)
    r = optical_ray_dir(640, 240, K)
    ang_l = _angle_deg(c, l)
    ang_r = _angle_deg(c, r)
    half = 79.0 / 2.0
    return {
        "half_hfov_left_deg": ang_l,
        "half_hfov_right_deg": ang_r,
        "pass": abs(ang_l - half) < 0.05 and abs(ang_r - half) < 0.05,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {
        "baseline_commit_expected": "9fb8ea4",
        "tests": {
            "intrinsics": test_intrinsics(),
            "optical_rot_map": test_optical_vs_hab_rot(),
            "render_rx": test_render_optical_rx(),
            "project_roundtrip": test_project_unproject(),
            "agl": test_agl_translation(),
            "ray_hfov": test_ray_angles(),
        },
    }
    report["all_pass"] = all(t["pass"] for t in report["tests"].values())
    (args.out / "camera_coord_validate.json").write_text(json.dumps(report, indent=2))
    md = [
        "# Camera coord / intrinsics validation",
        "",
        f"all_pass: **{report['all_pass']}**",
        "",
        "| test | pass |",
        "|---|---|",
    ]
    for k, v in report["tests"].items():
        md.append(f"| {k} | {v['pass']} |")
    md.append("")
    md.append(
        "Note: prior FOV reports that called launch fy=422 (VFOV≈59.25°) "
        "'measured D455 FOV' are **downgraded** — that fy used HFOV×H/W."
    )
    (args.out / "camera_coord_validate.md").write_text("\n".join(md) + "\n")
    print(json.dumps({"all_pass": report["all_pass"], "out": str(args.out)}, indent=2))
    if not report["all_pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
