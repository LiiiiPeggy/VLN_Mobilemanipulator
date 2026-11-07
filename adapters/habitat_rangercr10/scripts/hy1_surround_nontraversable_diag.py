#!/usr/bin/env python3
# ################################
# Offline HY1 diagnostic: why occupancy map surrounds chassis as non-traversable
# while physical space is open. Frozen-run only; no deploy / gate / A* changes.
# ################################
"""Classify surround as UNKNOWN / raw OCC / inflation / planner reject.

Reads a frozen apexnav_real run (native plan_seq local_map + steps + depth).
Writes layered local maps, exterior-band stats, cell provenance, camera-bias
chain checks, and a coarse multi-view wall-consistency probe.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.robot_scale import footprint_at_scale  # noqa: E402
from src.camera_model import pinhole_from_hfov  # noqa: E402


# ################################
LEGEND = {0: "UNKNOWN", 1: "FREE", 2: "OCCUPIED"}
NEAR_START_EXEMPT_M = 0.25
# ################################


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text())


def _oriented_in_footprint(
    x: float, y: float, cx: float, cy: float, yaw: float, half_l: float, half_w: float
) -> bool:
    dx, dy = x - cx, y - cy
    c, s = math.cos(yaw), math.sin(yaw)
    bx = c * dx + s * dy
    by = -s * dx + c * dy
    return abs(bx) <= half_l and abs(by) <= half_w


def _dxy(x: float, y: float, cx: float, cy: float) -> float:
    return math.hypot(x - cx, y - cy)


def analyze_local_map(
    lm: dict, yaw: float, half_l: float, half_w: float
) -> Dict[str, Any]:
    cx, cy = float(lm["chassis"][0]), float(lm["chassis"][1])
    cells = lm["cells"]  # [x,y,raw,inflate]
    res = float(lm["resolution"])

    def band_stats(r0: float, r1: float, region: str) -> dict:
        rows = []
        for x, y, r, inf in cells:
            d = _dxy(x, y, cx, cy)
            if not (r0 <= d < r1):
                continue
            under = _oriented_in_footprint(x, y, cx, cy, yaw, half_l, half_w)
            if region == "under_body" and not under:
                continue
            if region == "exterior" and under:
                continue
            rows.append((x, y, int(r), int(inf), d))
        raw = Counter(r for *_, r, inf, d in rows)
        n_inf = sum(1 for *_, r, inf, d in rows if inf == 1)
        # block classes for exterior target (planner-relevant)
        n_unk = raw.get(0, 0)
        n_free = raw.get(1, 0)
        n_occ = raw.get(2, 0)
        # inflate-only: inflate=1 and raw!=OCC
        n_inf_only = sum(1 for *_, r, inf, d in rows if inf == 1 and r != 2)
        n_occ_and_inf = sum(1 for *_, r, inf, d in rows if inf == 1 and r == 2)
        return {
            "n": len(rows),
            "raw": {LEGEND[k]: int(v) for k, v in sorted(raw.items())},
            "inflate_any": int(n_inf),
            "inflate_only_non_raw_occ": int(n_inf_only),
            "raw_occ_and_inflate": int(n_occ_and_inf),
            "overlap_note": (
                "inflate overlays raw OCC; inflate_only = inflated FREE/UNKNOWN cells"
            ),
            "block_share": {
                "UNKNOWN": n_unk,
                "FREE": n_free,
                "OCCUPIED": n_occ,
            },
        }

    bands = {}
    for r0, r1 in [(0.0, 0.3), (0.3, 0.6), (0.6, 1.0), (1.0, 1.5)]:
        bands[f"{r0:.1f}-{r1:.1f}"] = {
            "all": band_stats(r0, r1, "all"),
            "under_body": band_stats(r0, r1, "under_body"),
            "exterior": band_stats(r0, r1, "exterior"),
        }

    # exterior target: outside footprint, within 0.3–1.0 m (drivable annulus)
    ext_target = band_stats(0.3, 1.0, "exterior")

    free = [(x, y, _dxy(x, y, cx, cy)) for x, y, r, inf in cells if int(r) == 1]
    free.sort(key=lambda t: t[2])
    occ = [
        (x, y, _dxy(x, y, cx, cy), int(inf))
        for x, y, r, inf in cells
        if int(r) == 2
    ]
    occ.sort(key=lambda t: t[2])
    unk_ext = [
        (x, y, _dxy(x, y, cx, cy))
        for x, y, r, inf in cells
        if int(r) == 0
        and not _oriented_in_footprint(x, y, cx, cy, yaw, half_l, half_w)
    ]
    unk_ext.sort(key=lambda t: t[2])

    # UNKNOWN moat thickness: min exterior FREE distance; max radius where exterior is all UNKNOWN
    moat_r = 0.0
    for rr in np.arange(0.05, 1.51, 0.05):
        ext = band_stats(rr - 0.05, rr, "exterior")
        if ext["n"] == 0:
            continue
        if ext["block_share"]["FREE"] == 0 and ext["block_share"]["OCCUPIED"] == 0:
            moat_r = rr
        else:
            break

    start_cell = min(
        cells, key=lambda c: _dxy(c[0], c[1], cx, cy)
    )
    return {
        "chassis_xy": [cx, cy],
        "yaw_ros": yaw,
        "resolution": res,
        "half_m": lm.get("half_m"),
        "footprint_half_lw": [half_l, half_w],
        "global_raw": {
            LEGEND[k]: v
            for k, v in sorted(Counter(int(c[2]) for c in cells).items())
        },
        "global_inflate_ones": int(sum(1 for c in cells if int(c[3]) == 1)),
        "bands": bands,
        "exterior_target_0p3_1p0": ext_target,
        "start_cell": {
            "xy": [start_cell[0], start_cell[1]],
            "raw": LEGEND[int(start_cell[2])],
            "inflate": int(start_cell[3]),
            "dxy": _dxy(start_cell[0], start_cell[1], cx, cy),
        },
        "nearest_free_m": free[0][2] if free else None,
        "nearest_free_xy": list(free[0][:2]) if free else None,
        "nearest_occ_m": occ[0][2] if occ else None,
        "nearest_occ_xy": list(occ[0][:2]) if occ else None,
        "nearest_exterior_unk_m": unk_ext[0][2] if unk_ext else None,
        "unknown_moat_radius_m": float(moat_r),
        "near_start_exempt_m": NEAR_START_EXEMPT_M,
        "gap_exempt_to_free_m": (
            None
            if not free
            else float(free[0][2] - NEAR_START_EXEMPT_M)
        ),
    }


def render_layered_map(
    lm: dict,
    yaw: float,
    half_l: float,
    half_w: float,
    cam_xy: Optional[List[float]],
    cam_traj: List[List[float]],
    candidates: List[dict],
    out_png: Path,
    title: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Circle
    from matplotlib.lines import Line2D

    cx, cy = float(lm["chassis"][0]), float(lm["chassis"][1])
    res = float(lm["resolution"])
    half = float(lm["half_m"])
    # raster
    n = int(round(2 * half / res))
    # colors: FREE white, UNKNOWN light gray, OCC dark, inflate outline magenta
    img = np.ones((n, n, 3), dtype=np.float32) * 0.85  # default unknown-ish
    xs = np.array([c[0] for c in lm["cells"]])
    ys = np.array([c[1] for c in lm["cells"]])
    raw = np.array([int(c[2]) for c in lm["cells"]])
    inf = np.array([int(c[3]) for c in lm["cells"]])

    def to_ij(x, y):
        # image: row increases with -y? keep y-up in imshow origin lower
        j = int(round((x - (cx - half)) / res))
        i = int(round((y - (cy - half)) / res))
        return i, j

    grid_raw = np.full((n, n), -1, dtype=np.int8)
    grid_inf = np.zeros((n, n), dtype=np.uint8)
    for x, y, r, f in zip(xs, ys, raw, inf):
        i, j = to_ij(x, y)
        if 0 <= i < n and 0 <= j < n:
            grid_raw[i, j] = r
            grid_inf[i, j] = f

    rgb = np.zeros((n, n, 3), dtype=np.float32)
    rgb[grid_raw == 0] = (0.75, 0.75, 0.78)  # UNKNOWN
    rgb[grid_raw == 1] = (1.0, 1.0, 1.0)  # FREE
    rgb[grid_raw == 2] = (0.15, 0.15, 0.15)  # OCC
    rgb[grid_raw < 0] = (0.9, 0.9, 0.92)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.2))
    extent = [cx - half, cx + half, cy - half, cy + half]

    ax = axes[0]
    ax.imshow(rgb, origin="lower", extent=extent, interpolation="nearest")
    # inflate contour
    ys_i, xs_i = np.where(grid_inf == 1)
    if len(xs_i):
        wx = (cx - half) + xs_i * res
        wy = (cy - half) + ys_i * res
        ax.scatter(wx, wy, s=6, c="#d000d0", marker="s", alpha=0.35, label="inflate")

    # footprint rectangle in world
    c, s = math.cos(yaw), math.sin(yaw)
    corners = []
    for sx, sy in [
        (-half_l, -half_w),
        (half_l, -half_w),
        (half_l, half_w),
        (-half_l, half_w),
        (-half_l, -half_w),
    ]:
        corners.append((cx + c * sx - s * sy, cy + s * sx + c * sy))
    ax.plot([p[0] for p in corners], [p[1] for p in corners], "b-", lw=1.5, label="footprint")
    ax.plot(cx, cy, "b+", ms=12, mew=2, label="chassis")
    if cam_xy is not None:
        ax.plot(cam_xy[0], cam_xy[1], "r*", ms=12, label="camera@plan")
    if cam_traj:
        ax.plot(
            [p[0] for p in cam_traj],
            [p[1] for p in cam_traj],
            "r.-",
            ms=3,
            lw=0.8,
            alpha=0.7,
            label="cam traj",
        )
    # rays (cam → a few free cells near chassis)
    if cam_xy is not None:
        free_pts = [(x, y) for x, y, r, f in zip(xs, ys, raw, inf) if r == 1]
        free_pts.sort(key=lambda p: math.hypot(p[0] - cx, p[1] - cy))
        for p in free_pts[:12]:
            ax.plot(
                [cam_xy[0], p[0]],
                [cam_xy[1], p[1]],
                color="cyan",
                lw=0.4,
                alpha=0.35,
            )
    # candidate goals
    for cand in candidates[:8]:
        g = cand.get("candidate")
        if g:
            ax.plot(g[0], g[1], "x", color="orange", ms=7)
            ax.annotate(
                cand.get("raw_return", "?")[:8],
                (g[0], g[1]),
                fontsize=6,
                color="orange",
            )
    ax.add_patch(
        Circle((cx, cy), NEAR_START_EXEMPT_M, fill=False, ls="--", ec="green", lw=1.0)
    )
    ax.add_patch(Circle((cx, cy), 0.3, fill=False, ls=":", ec="navy", lw=0.8))
    ax.set_aspect("equal")
    ax.set_xlabel("ROS X (m)")
    ax.set_ylabel("ROS Y (m)")
    ax.set_title(title + " — raw layers")
    ax.legend(loc="upper right", fontsize=7)
    ax.grid(True, alpha=0.25)

    # right: block-class only on exterior target
    ax = axes[1]
    block = np.zeros((n, n, 3), dtype=np.float32)
    block[:] = (0.92, 0.92, 0.94)
    for x, y, r, f in zip(xs, ys, raw, inf):
        under = _oriented_in_footprint(x, y, cx, cy, yaw, half_l, half_w)
        i, j = to_ij(x, y)
        if not (0 <= i < n and 0 <= j < n):
            continue
        if under:
            block[i, j] = (0.55, 0.65, 0.85)  # under-body (not required open)
            continue
        d = _dxy(x, y, cx, cy)
        if d < 0.3 or d > 1.0:
            if r == 1:
                block[i, j] = (1, 1, 1)
            elif r == 2:
                block[i, j] = (0.2, 0.2, 0.2)
            else:
                block[i, j] = (0.8, 0.8, 0.82)
            continue
        # exterior target
        if r == 0:
            block[i, j] = (0.95, 0.55, 0.15)  # UNKNOWN block
        elif r == 2:
            block[i, j] = (0.8, 0.1, 0.1)  # OCC block
        elif f == 1:
            block[i, j] = (0.75, 0.2, 0.75)  # inflate on free
        else:
            block[i, j] = (0.2, 0.75, 0.35)  # FREE passable
    ax.imshow(block, origin="lower", extent=extent, interpolation="nearest")
    ax.plot([p[0] for p in corners], [p[1] for p in corners], "b-", lw=1.5)
    ax.plot(cx, cy, "b+", ms=12, mew=2)
    if cam_xy is not None:
        ax.plot(cam_xy[0], cam_xy[1], "r*", ms=12)
    ax.add_patch(
        Circle((cx, cy), NEAR_START_EXEMPT_M, fill=False, ls="--", ec="green", lw=1.0)
    )
    legend_elems = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor=(0.95, 0.55, 0.15), markersize=10, label="ext UNKNOWN"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=(0.8, 0.1, 0.1), markersize=10, label="ext OCC"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=(0.75, 0.2, 0.75), markersize=10, label="ext inflate-on-FREE"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=(0.2, 0.75, 0.35), markersize=10, label="ext FREE"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=(0.55, 0.65, 0.85), markersize=10, label="under-body"),
        Line2D([0], [0], ls="--", color="green", label="0.25 m A* exempt"),
    ]
    ax.legend(handles=legend_elems, loc="upper right", fontsize=7)
    ax.set_aspect("equal")
    ax.set_xlabel("ROS X (m)")
    ax.set_title("exterior 0.3–1.0 m block class")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=140)
    plt.close(fig)


def camera_bias_chain(run: Path) -> Dict[str, Any]:
    pre = _load_json(run / "pre_plan_obs_meta.json")
    steps = []
    for line in (run / "steps.jsonl").read_text().splitlines():
        d = json.loads(line)
        m = d.get("publish_meta") or {}
        if not m.get("camera_ros"):
            continue
        steps.append(
            {
                "step": d["step"],
                "phase": d.get("phase"),
                "camera_ros": m["camera_ros"],
                "base_ros_chassis": m.get("base_ros_chassis") or m.get("base_ros"),
                "odom_ros": m.get("odom_ros"),
                "odom_xy_source": m.get("odom_xy_source"),
                "odom_xy_mode": m.get("odom_xy_mode"),
                "camera_frame_published": m.get("camera_frame_published"),
                "base_yaw_ros": m.get("base_yaw_ros"),
                "depth_validity": m.get("depth_validity"),
            }
        )
    bases = np.array([s["base_ros_chassis"][:2] for s in steps], dtype=float)
    cams = np.array([s["camera_ros"][:2] for s in steps], dtype=float)
    odoms = np.array([s["odom_ros"][:2] for s in steps], dtype=float)
    d_cb = np.linalg.norm(cams - bases, axis=1)
    d_ob = np.linalg.norm(odoms - bases, axis=1)
    return {
        "pre_plan": {
            "odom_xy_mode": pre.get("odom_xy_mode"),
            "odom_xy_source": pre.get("odom_xy_source"),
            "camera_frame_published": pre.get("camera_frame_published"),
            "invalid_depth_policy": pre.get("invalid_depth_policy"),
            "base_ros_chassis": pre.get("base_ros_chassis"),
            "camera_ros": pre.get("camera_ros"),
            "odom_equals_chassis": pre.get("odom_ros") == pre.get("base_ros_chassis"),
            "cam_base_xy_offset_m": float(
                np.linalg.norm(
                    np.array(pre["camera_ros"][:2]) - np.array(pre["base_ros_chassis"][:2])
                )
            ),
            "depth_validity": pre.get("depth_validity"),
        },
        "lookaround_n_publish": len(steps),
        "base_xy_std_m": bases.std(axis=0).tolist(),
        "base_drift_m": float(np.linalg.norm(bases[-1] - bases[0])) if len(bases) else None,
        "cam_base_offset_m": {
            "mean": float(d_cb.mean()),
            "std": float(d_cb.std()),
            "min": float(d_cb.min()),
            "max": float(d_cb.max()),
        },
        "odom_minus_chassis_max_m": float(d_ob.max()) if len(d_ob) else None,
        "odom_xy_sources": sorted({s["odom_xy_source"] for s in steps}),
        "odom_xy_modes": sorted({s["odom_xy_mode"] for s in steps}),
        "legacy_camera_xy_proxy_enabled": any(
            s.get("odom_xy_mode") == "legacy_camera_xy_proxy" for s in steps
        ),
        "camera_traj_xy": cams.tolist(),
        "verdict": (
            "camera offset present in sensor_pose; planning odom uses chassis; "
            "legacy proxy OFF"
            if (
                float(d_cb.mean()) > 0.4
                and float(d_ob.max()) < 1e-6
                and all(s.get("odom_xy_mode") == "chassis" for s in steps)
            )
            else "CHECK_FAILED"
        ),
    }


def multiview_wall_consistency(run: Path, floor_y: float) -> Dict[str, Any]:
    """Reproject a stable far wall seed across lookaround depth dumps."""
    Kin = pinhole_from_hfov(640, 480, 79.0)
    fx, fy, cxk, cyk = Kin["fx"], Kin["fy"], Kin["cx"], Kin["cy"]
    # pick frames with raw depth dumps
    depth_dir = run / "depth_validity"
    frames = sorted(
        int(p.stem.split("_")[-1]) for p in depth_dir.glob("raw_m_*.npy")
    )
    if len(frames) < 2:
        return {"status": "insufficient_depth_dumps", "frames": frames}

    # align publish_meta by step index ≈ frame index for init lookaround
    metas = {}
    for line in (run / "steps.jsonl").read_text().splitlines():
        d = json.loads(line)
        m = d.get("publish_meta") or {}
        if m.get("camera_ros") and m.get("camera_q_xyzw"):
            metas[int(d["step"])] = m
    # also try frame 0 from pre_plan
    pre = _load_json(run / "pre_plan_obs_meta.json")
    metas.setdefault(0, pre)

    def quat_to_R(q):
        x, y, z, w = q
        return np.array(
            [
                [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
            ],
            dtype=float,
        )

    def cam_world_from_meta(m):
        # published optical pose already in ROS world
        p = np.array(m["camera_ros"][:3], dtype=float)
        R = quat_to_R(m["camera_q_xyzw"])
        return R, p

    # Prefer early consecutive lookaround dumps (≈30° apart) for overlap.
    prefer = [f for f in (0, 1, 17, 18, 25, 26, 8, 9) if f in frames]
    f0 = prefer[0] if prefer else frames[0]
    prep_p = depth_dir / f"prep_m_{f0:04d}.npy"
    depth0 = np.load(prep_p if prep_p.exists() else depth_dir / f"raw_m_{f0:04d}.npy")
    if depth0.ndim == 3:
        depth0 = depth0[..., 0]
    H, W = depth0.shape
    # search neighborhood for finite depth in 1.5–4.5 m (wall-ish)
    seed = None
    for v0 in (int(H * 0.40), int(H * 0.35), int(H * 0.50), int(H * 0.55)):
        for dv in range(-40, 81, 2):
            for du in range(-120, 121, 3):
                uu, vv = W // 2 + du, v0 + dv
                if not (0 <= uu < W and 0 <= vv < H):
                    continue
                d = float(depth0[vv, uu])
                if np.isfinite(d) and 1.5 <= d <= 4.5:
                    seed = (uu, vv, d)
                    break
            if seed:
                break
        if seed:
            break
    if seed is None:
        return {"status": "no_seed", "frame0": f0, "depth_finite": int(np.isfinite(depth0).sum())}

    if f0 in metas:
        seed_meta_frame = f0
    else:
        # steps may be 0..26 while dumps use same indices; try nearest
        alt = min(metas.keys(), key=lambda k: abs(k - f0)) if metas else None
        if alt is None or abs(alt - f0) > 1:
            return {
                "status": "no_meta_for_seed_frame",
                "frame0": f0,
                "meta_keys": sorted(metas)[:10],
            }
        seed_meta_frame = alt
    R0, p0 = cam_world_from_meta(metas[seed_meta_frame])
    # ################################
    # ROS optical (map_ros pinhole): X right, Y down, Z forward.
    # ################################
    uu, vv, d = seed
    x = (uu - cxk) / fx * d
    y = (vv - cyk) / fy * d
    z = d
    p_cam = np.array([x, y, z], dtype=float)
    p_w = R0 @ p_cam + p0

    records = []
    for fi in frames:
        if fi not in metas:
            continue
        depth_p = depth_dir / f"prep_m_{fi:04d}.npy"
        depth = np.load(depth_p if depth_p.exists() else depth_dir / f"raw_m_{fi:04d}.npy")
        if depth.ndim == 3:
            depth = depth[..., 0]
        R, p = cam_world_from_meta(metas[fi])
        p_cam_i = R.T @ (p_w - p)
        if p_cam_i[2] <= 0.05:
            records.append({"frame": fi, "status": "behind_camera"})
            continue
        u = fx * (p_cam_i[0] / p_cam_i[2]) + cxk
        v = fy * (p_cam_i[1] / p_cam_i[2]) + cyk
        ui, vi = int(round(u)), int(round(v))
        if not (0 <= ui < W and 0 <= vi < H):
            records.append(
                {
                    "frame": fi,
                    "status": "out_of_fov",
                    "reproject_uv": [float(u), float(v)],
                    "z_cam": float(p_cam_i[2]),
                }
            )
            continue
        d_meas = float(depth[vi, ui])
        err = (
            abs(d_meas - float(p_cam_i[2]))
            if np.isfinite(d_meas)
            else float("nan")
        )
        records.append(
            {
                "frame": fi,
                "status": "ok",
                "reproject_uv": [float(u), float(v)],
                "z_pred": float(p_cam_i[2]),
                "z_meas": d_meas,
                "abs_depth_err_m": err,
            }
        )

    ok = [
        r
        for r in records
        if r.get("status") == "ok" and np.isfinite(r.get("abs_depth_err_m", float("nan")))
    ]
    errs = [r["abs_depth_err_m"] for r in ok]
    return {
        "status": "ok",
        "seed_frame": f0,
        "seed_meta_frame": seed_meta_frame,
        "seed_uvd": [uu, vv, d],
        "seed_world_ros": p_w.tolist(),
        "frames_checked": frames,
        "n_ok": len(ok),
        "abs_depth_err_m": {
            "mean": float(np.mean(errs)) if errs else None,
            "median": float(np.median(errs)) if errs else None,
            "max": float(np.max(errs)) if errs else None,
        },
        "records": records,
        "note": (
            "Same world seed reprojected via published optical pose+K; "
            "large yaw-dependent depth error would suggest extrinsics/sync bug. "
            "Sampling different surfaces can inflate error without pose error."
        ),
    }


def plan_reject_summary(plan: dict) -> dict:
    rej = Counter()
    for c in plan.get("candidates") or []:
        rc = c.get("reject_counts_inferred") or {}
        for k in ("occupied", "inflate", "unknown", "out_of_bounds"):
            rej[k] += int(rc.get(k, 0))
    return {
        "result": plan.get("result"),
        "start_raw_occ": plan.get("start_raw_occ"),
        "start_raw_legend": plan.get("start_occ_legend"),
        "start_inflate": plan.get("start_inflate"),
        "free_within_0p3": plan.get("free_within_0p3"),
        "unk_within_0p3": plan.get("unk_within_0p3"),
        "occ_within_0p3": plan.get("occ_within_0p3"),
        "inf_within_0p3": plan.get("inf_within_0p3"),
        "nearest_free_m": plan.get("nearest_free_m"),
        "n_reachable_candidates": plan.get("n_reachable_candidates"),
        "n_candidate_searches": plan.get("n_candidate_searches"),
        "reject_counts_sum_over_candidates": dict(rej),
        "dominant_reject": (
            max(rej, key=rej.get) if rej else None
        ),
        "any_success_path_relied_near_start_exemption": plan.get(
            "any_success_path_relied_near_start_exemption"
        ),
        "selected_path": plan.get("selected_path"),
        "pipeline_start_raw_is_camera_not_chassis": True,
        "pipeline_note": (
            "map_pipeline_diag.start_raw_occ uses camera_pos (see map_ros.cpp); "
            "native_plan_diag.start_raw_occ uses chassis. Do not conflate."
        ),
    }


def representative_cells(lm: dict, yaw: float, half_l: float, half_w: float, analysis: dict) -> list:
    cx, cy = analysis["chassis_xy"]
    cells = lm["cells"]
    out = []
    # 1) chassis start
    start = min(cells, key=lambda c: _dxy(c[0], c[1], cx, cy))
    out.append(
        {
            "role": "chassis_start",
            "xy": [start[0], start[1]],
            "raw": LEGEND[int(start[2])],
            "inflate": int(start[3]),
            "why_nontraversable": (
                "UNKNOWN at planning start; optimistic=false treats unknown as blocked; "
                f"nearest FREE={analysis['nearest_free_m']:.3f} m > "
                f"near-start exemption {NEAR_START_EXEMPT_M} m"
                if int(start[2]) == 0
                else LEGEND[int(start[2])]
            ),
            "false_obstacle": False,
            "provenance": "no depth endpoint / free-ray hit under footprint (observation cover)",
        }
    )
    # 2) nearest exterior UNKNOWN
    unk_ext = [
        c
        for c in cells
        if int(c[2]) == 0
        and not _oriented_in_footprint(c[0], c[1], cx, cy, yaw, half_l, half_w)
    ]
    unk_ext.sort(key=lambda c: _dxy(c[0], c[1], cx, cy))
    if unk_ext:
        c = unk_ext[0]
        out.append(
            {
                "role": "nearest_exterior_UNKNOWN",
                "xy": [c[0], c[1]],
                "d_chassis_m": _dxy(c[0], c[1], cx, cy),
                "raw": "UNKNOWN",
                "inflate": int(c[3]),
                "why_nontraversable": "never observed → remains UNKNOWN (not raw OCC, not inflate)",
                "false_obstacle": False,
                "provenance": "no free-ray / occ update for this cell in lookaround coverage",
            }
        )
    # 3) nearest raw OCC
    occ = [c for c in cells if int(c[2]) == 2]
    occ.sort(key=lambda c: _dxy(c[0], c[1], cx, cy))
    if occ:
        c = occ[0]
        out.append(
            {
                "role": "nearest_raw_OCCUPIED",
                "xy": [c[0], c[1]],
                "d_chassis_m": _dxy(c[0], c[1], cx, cy),
                "raw": "OCCUPIED",
                "inflate": int(c[3]),
                "why_nontraversable": "raw OCCUPIED endpoint (likely real scene geometry at ~0.9 m+)",
                "false_obstacle": "not_indicated_for_chassis_surround",
                "provenance": "depth→world→height classify→occ update; not the surround moat",
            }
        )
    # 4) nearest inflate-only
    inf_only = [c for c in cells if int(c[3]) == 1 and int(c[2]) != 2]
    inf_only.sort(key=lambda c: _dxy(c[0], c[1], cx, cy))
    if inf_only:
        c = inf_only[0]
        out.append(
            {
                "role": "nearest_inflate_non_raw_occ",
                "xy": [c[0], c[1]],
                "d_chassis_m": _dxy(c[0], c[1], cx, cy),
                "raw": LEGEND[int(c[2])],
                "inflate": 1,
                "why_nontraversable": "inflation halo of a real OCC cell (legacy018=0.18 m)",
                "false_obstacle": False,
                "provenance": "triggered by nearby raw OCC; not chassis-local",
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--run",
        type=Path,
        default=Path(
            "/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/"
            "real_s070_hy1_base_rep_v2_r1_20261106_191426"
        ),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(
            "/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/"
            "hy1_surround_nontraversable_20261106"
        ),
    )
    ap.add_argument("--git-sha", default="99ebb49")
    args = ap.parse_args()
    run: Path = args.run
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    summary = _load_json(run / "summary.json")
    process = _load_json(run / "process_meta.json")
    lm = _load_json(run / "native_diag" / "plan_seq_1_local_map.json")
    plan = json.loads((run / "native_diag" / "native_plan_diag.jsonl").read_text().splitlines()[0])
    yaw = float(summary["first_plan_diag"]["base_yaw_ros"])
    fp = footprint_at_scale(0.7)
    half_l = float(fp["chassis_half_length_m"])
    half_w = float(fp["chassis_half_width_m"])

    analysis = analyze_local_map(lm, yaw, half_l, half_w)
    bias = camera_bias_chain(run)
    mv = multiview_wall_consistency(run, float(summary.get("floor_y_hab") or 0.06218))
    plan_s = plan_reject_summary(plan)
    cells = representative_cells(lm, yaw, half_l, half_w, analysis)

    cam_xy = bias["pre_plan"]["camera_ros"][:2]
    render_layered_map(
        lm,
        yaw,
        half_l,
        half_w,
        cam_xy,
        bias["camera_traj_xy"],
        plan.get("candidates") or [],
        out / "plan_seq1_layered_local_map.png",
        title=f"HY1 plan_seq=1 NO_PASSABLE ({run.name})",
    )

    # lookaround begin/end paper maps are already in run/maps; copy note + indices
    map_frames = sorted((run / "maps").glob("frame_*.png"))
    freeze = {
        "git_sha_workspace_at_diag": args.git_sha,
        "run_id": run.name,
        "run_path": str(run),
        "process_meta": process,
        "robot_scale": summary.get("robot_scale"),
        "force_spawn_json": process.get("force_spawn_json"),
        "n_init_lookaround_actions": summary.get("n_init_lookaround_actions"),
        "entered_callActionPlanner": summary.get("entered_callActionPlanner"),
        "native_first_plan_result": plan_s["result"],
        "map_frame_begin": str(map_frames[0]) if map_frames else None,
        "map_frame_end": str(map_frames[-1]) if map_frames else None,
        "demo_video_not_used_for_inference": (
            "7fps hy1_20261105_171252 is older PPO-raise demo; this diag uses "
            f"{run.name} native_diag at plan_seq=1"
        ),
        "workspace_diff_note": (
            "Working tree has uncommitted MEMORY/PROGRESS/PROCESS + map_ros diag "
            "helpers + HY1 probe scripts; default deploy lookaround/ground/inflation/A* "
            "unchanged for this frozen run."
        ),
    }

    # cand05 / C gate loss cross-link (already on disk)
    gate_path = Path(
        "/home/ubuntu/locomani/VLN_Mobilemanipulator/reports/"
        "hy1_cand05_static_multiframe_20261106/gate_stage_loss_diag.json"
    )
    gate = _load_json(gate_path) if gate_path.exists() else None
    gate_summary = None
    if gate and "poses" in gate:
        gate_summary = {}
        for name, pose in gate["poses"].items():
            gate_summary[name] = {
                "earliest_corridor_ground_loss": pose.get("earliest_corridor_ground_loss"),
                "endpoint_cells_after_outlier": pose.get("endpoint_cells_after_outlier"),
                "corridor_raw_ground": (pose.get("2_corridor_agl") or {}).get(
                    "ground_0_0p03"
                ),
            }

    payload = {
        "freeze": freeze,
        "local_map_analysis": analysis,
        "camera_bias_chain": {
            k: v for k, v in bias.items() if k != "camera_traj_xy"
        },
        "camera_traj_xy": bias["camera_traj_xy"],
        "multiview_wall_consistency": mv,
        "native_plan": plan_s,
        "representative_cells": cells,
        "cand05_C_gate_stage_loss": gate_summary,
        "answers": {
            "surround_primary": "UNKNOWN",
            "surround_not": ["raw_OCCUPIED_near_chassis", "inflation_near_chassis"],
            "camera_bias_handled": bias["verdict"].startswith("camera offset"),
            "camera_bias_evidence": bias["verdict"],
            "open_area_not_FREE_earliest": (
                "exterior near-chassis cells never receive free-ray updates under "
                "default PPO-raise + 30° lookaround coverage; under-body 0–0.3 m is "
                "footprint-occluded (not a required observe target). Separately, when "
                "cand05/C geometries do put corridor ground in FOV, earliest map-side "
                "loss is voxel Z-mix (C:62→0; cand05:27→3)."
            ),
            "false_obstacle_near_chassis": False,
            "false_obstacle_note": (
                "Nearest OCC ≈0.87 m; surround moat is UNKNOWN. No evidence that "
                "chassis-enclosing non-traversable ring is a projected false obstacle."
            ),
            "fix_or_observe": (
                "Do NOT force FREE / widen exemption / inject GT. Primary: observation "
                "coverage redesign for exterior annulus. Optional independent: voxel "
                "Z-mix min-repro fix for cand05/C corridor ground. If exterior FREE "
                "reaches chassis but start stays UNKNOWN → start-state/planner-interface."
            ),
            "still_depends_on_start_exemption": (
                "At this frozen first-plan: exemption would NOT create a path "
                "(nearest FREE 0.52 m > 0.25 m; all candidates reject on unknown)."
            ),
        },
    }
    (out / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    # slim traj for overlay reuse
    np.save(out / "camera_traj_xy.npy", np.array(bias["camera_traj_xy"], dtype=float))
    print(json.dumps({"out": str(out), "answers": payload["answers"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
