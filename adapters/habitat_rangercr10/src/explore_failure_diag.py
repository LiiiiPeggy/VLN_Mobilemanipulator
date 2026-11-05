"""Offline yr17 vs HY1 (or any two) ApexNav explore failure diagnosis.

################################
Uses saved maps/steps/actions/logs only. Does NOT feed GT into ApexNav.
################################
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw

from .map_style import LEGACY_COLORS, PAPER_BG, PAPER_FREE, PAPER_OCCUPIED, PAPER_UNKNOWN


def _mask_near(rgb: np.ndarray, color: Tuple[int, int, int], thr: float = 40.0) -> np.ndarray:
    d = np.linalg.norm(rgb.astype(np.float32) - np.asarray(color, dtype=np.float32), axis=2)
    return d <= thr


def _load_jsonl(path: Path) -> List[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def _map_stats_from_png(path: Path) -> Dict[str, Any]:
    rgb = np.asarray(Image.open(path).convert("RGB"))
    free = _mask_near(rgb, LEGACY_COLORS["free"], 45)
    occ = _mask_near(rgb, LEGACY_COLORS["occupied"], 45)
    unk = _mask_near(rgb, LEGACY_COLORS["unknown"], 45) if "unknown" in LEGACY_COLORS else (~free & ~occ)
    # Connectivity of free (4-connected)
    from collections import deque

    h, w = free.shape
    vis = np.zeros_like(free, dtype=bool)
    comps = []
    for y in range(h):
        for x in range(w):
            if not free[y, x] or vis[y, x]:
                continue
            q = deque([(y, x)])
            vis[y, x] = True
            n = 0
            while q:
                cy, cx = q.popleft()
                n += 1
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and free[ny, nx] and not vis[ny, nx]:
                        vis[ny, nx] = True
                        q.append((ny, nx))
            comps.append(n)
    comps.sort(reverse=True)
    return {
        "free_px": int(free.sum()),
        "occ_px": int(occ.sum()),
        "unk_px": int(unk.sum()),
        "n_free_components": len(comps),
        "largest_free_component_px": int(comps[0]) if comps else 0,
        "largest_free_frac": float(comps[0] / max(int(free.sum()), 1)) if comps else 0.0,
    }


def _parse_expl_log(log_path: Path) -> Dict[str, Any]:
    if not log_path.is_file():
        return {}
    txt = log_path.read_text(errors="ignore")
    return {
        "n_maybe_no_passable": len(re.findall(r"Maybe no passable frontier", txt)),
        "n_no_passable": len(re.findall(r"No passable frontier", txt)),
        "n_no_coverable": len(re.findall(r"No coverable frontier", txt)),
        "n_explore_closest": len(re.findall(r"Explore the environment \(Closest\)", txt)),
        "n_exploit_tsp": len(re.findall(r"Exploit the semantic value", txt)),
        "n_to_next_point": len(re.findall(r"To the next point", txt)),
        "n_search_extreme": len(re.findall(r"search exterme case", txt)),
        "has_hybrid": "Hybrid Mode" in txt,
    }


def diagnose_run(run_dir: Path, out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = json.loads((run_dir / "summary.json").read_text())
    steps = _load_jsonl(run_dir / "steps.jsonl")
    acts = _load_jsonl(run_dir / "actions.jsonl")
    expl_acts = [a for a in acts if a.get("phase") == "explore_planner"]
    expl_steps = [s for s in steps if s.get("phase") == "explore_planner"]
    # Map at end of lookaround / last frame
    maps = sorted((run_dir / "maps").glob("frame_*.png"))
    map_init = None
    map_final = maps[-1] if maps else None
    for s, a in zip(steps, acts):
        if a.get("phase") == "explore_planner":
            # map just before first explore ≈ last init frame
            idx = int(s["step"]) - 1
            cand = run_dir / "maps" / f"frame_{max(idx, 0):04d}.png"
            if cand.is_file():
                map_init = cand
            break
    if map_init is None and maps:
        map_init = maps[min(26, len(maps) - 1)]

    init_stats = _map_stats_from_png(map_init) if map_init else {}
    final_stats = _map_stats_from_png(map_final) if map_final else {}

    # Render free-component panel
    if map_init is not None:
        rgb = np.asarray(Image.open(map_init).convert("RGB"))
        free = _mask_near(rgb, LEGACY_COLORS["free"], 45)
        occ = _mask_near(rgb, LEGACY_COLORS["occupied"], 45)
        canvas = np.full_like(rgb, PAPER_BG)
        canvas[free] = PAPER_FREE
        canvas[occ] = PAPER_OCCUPIED
        im = Image.fromarray(canvas)
        dr = ImageDraw.Draw(im)
        dr.text(
            (6, 6),
            f"free={init_stats.get('free_px')} comps={init_stats.get('n_free_components')} "
            f"largest_frac={init_stats.get('largest_free_frac', 0):.2f}",
            fill=(0, 0, 0),
        )
        im.save(out_dir / "map_after_lookaround_free.png")

    expl_results = Counter(s.get("expl_result") for s in expl_steps)
    fwd = 0.0
    prev = None
    for s, a in zip(steps, acts):
        if a.get("phase") != "explore_planner":
            continue
        b = s["base"]
        if prev is not None and a.get("name") == "MOVE_FORWARD":
            fwd += math.hypot(b["x"] - prev["x"], b["z"] - prev["z"])
        prev = b

    log = _parse_expl_log(run_dir / "launch_logs" / "exploration.log")
    ep = json.loads((run_dir / "episode.json").read_text()) if (run_dir / "episode.json").is_file() else {}
    spawn = summary.get("spawn") or {}
    rep = {
        "run_dir": str(run_dir),
        "scene_id": ep.get("scene_id"),
        "episode_id": ep.get("episode_id"),
        "category": ep.get("object_category"),
        "termination": summary.get("termination"),
        "adapted_episode": summary.get("adapted_episode"),
        "spawn_offset_m": spawn.get("offset_from_episode_m"),
        "spawn_nav_clearance_m": spawn.get("nav_clearance_m"),
        "spawn_xyz": {"x": spawn.get("x"), "z": spawn.get("z"), "yaw": spawn.get("yaw")},
        "online_grid_final": (summary.get("online_grid_map") or {}).get("stats"),
        "map_after_lookaround": init_stats,
        "map_final_png": final_stats,
        "explore_actions": dict(Counter(a.get("name") for a in expl_acts)),
        "expl_result_counts": {str(k): v for k, v in expl_results.items()},
        "expl_result_legend": {
            "0": "EXPLORATION",
            "4": "NO_PASSABLE_FRONTIER",
            "5": "NO_COVERABLE_FRONTIER",
            "6": "SEARCH_EXTREME",
        },
        "forward_distance_m": fwd,
        "log_signals": log,
        "n_init": summary.get("n_init_lookaround_actions"),
        "n_explore": summary.get("n_explore_planner_actions"),
        "entered_callActionPlanner": summary.get("entered_callActionPlanner"),
    }
    (out_dir / "explore_failure_diag.json").write_text(json.dumps(rep, indent=2))
    return rep


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--yr17",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_yr17_openband_20261105_012302",
    )
    p.add_argument(
        "--hy1",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real/real_wide_hy1_openband_20261105_113724",
    )
    p.add_argument(
        "--out_root",
        default="/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/explore_failure_diag",
    )
    args = p.parse_args(argv)
    out = Path(args.out_root)
    y = diagnose_run(Path(args.yr17), out / "yr17_openband")
    h = diagnose_run(Path(args.hy1), out / "hy1_openband")
    cmp = {
        "yr17": y,
        "hy1": h,
        "contrast": {
            "spawn_clearance_m": {
                "yr17": y.get("spawn_nav_clearance_m"),
                "hy1": h.get("spawn_nav_clearance_m"),
            },
            "free_after_lookaround": {
                "yr17": (y.get("map_after_lookaround") or {}).get("free_px"),
                "hy1": (h.get("map_after_lookaround") or {}).get("free_px"),
            },
            "free_components": {
                "yr17": (y.get("map_after_lookaround") or {}).get("n_free_components"),
                "hy1": (h.get("map_after_lookaround") or {}).get("n_free_components"),
            },
            "largest_free_frac": {
                "yr17": (y.get("map_after_lookaround") or {}).get("largest_free_frac"),
                "hy1": (h.get("map_after_lookaround") or {}).get("largest_free_frac"),
            },
            "online_free": {
                "yr17": (y.get("online_grid_final") or {}).get("free"),
                "hy1": (h.get("online_grid_final") or {}).get("free"),
            },
            "explore_actions": {"yr17": y.get("explore_actions"), "hy1": h.get("explore_actions")},
            "log": {"yr17": y.get("log_signals"), "hy1": h.get("log_signals")},
            "hypothesis": (
                "Similar GT clearance scores ≠ same post-lookaround free connectivity / "
                "coverable frontiers. HY1 openband still NO_PASSABLE while yr17 finds Closest paths. "
                "Spawn band alone insufficient; scene-local frontier geometry after init matters."
            ),
        },
    }
    (out / "yr17_vs_hy1.json").write_text(json.dumps(cmp, indent=2))
    print(json.dumps(cmp["contrast"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
