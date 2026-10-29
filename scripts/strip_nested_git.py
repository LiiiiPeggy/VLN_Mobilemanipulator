#!/usr/bin/env python3
"""Remove nested .git metadata under baselines/* after recording SHAs."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "baselines"
# SHAs captured before any strip attempts (also in reports/source_versions.md)
KNOWN = {
    "VLFM": {
        "url": "https://github.com/rai-opensource/vlfm.git",
        "branch": "main",
        "sha": "584ed56008754fde7997d904983607def8328322",
    },
    "ApexNav": {
        "url": "https://github.com/Robotics-STAR-Lab/ApexNav.git",
        "branch": "main",
        "sha": "049971b613fcd2554b034bd4a853d79cc1e61613",
    },
    "MSGNav": {
        "url": "https://github.com/ylwhxht/MSGNav.git",
        "branch": "main",
        "sha": "03681a178d6993265e838e1fbbaf2338c54e1c62",
    },
    "APRR": {
        "url": "https://github.com/qinliangql/APRR.git",
        "branch": "main",
        "sha": "046c9c24d688c9b6acd7fc8c52abe1c6c2086e56",
    },
    "SG-Nav": {
        "url": "https://github.com/bagh2178/SG-Nav.git",
        "branch": "main",
        "sha": "d56863c96dea311aaa67fb0d39a1a8ccc3f0487f",
    },
    "UniGoal": {
        "url": "https://github.com/bagh2178/UniGoal.git",
        "branch": "main",
        "sha": "e2c6d456d53150db507a008250f50c34798daad5",
    },
}


def git_info(d: Path, fallback: dict) -> dict:
    info = dict(fallback)
    gitdir = d / ".git"
    if not gitdir.exists():
        return info
    try:
        info["sha"] = subprocess.check_output(
            ["git", "-C", str(d), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        info["branch"] = subprocess.check_output(
            ["git", "-C", str(d), "branch", "--show-current"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        info["url"] = subprocess.check_output(
            ["git", "-C", str(d), "remote", "get-url", "origin"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except subprocess.CalledProcessError:
        info["note"] = "used_fallback_sha_due_to_partial_git"
    return info


def main() -> None:
    umbrella = ROOT / ".git"
    assert umbrella.is_dir(), "Umbrella .git missing; abort"
    meta = {}
    for name, fallback in KNOWN.items():
        d = BASELINES / name
        assert d.is_dir(), d
        info = git_info(d, fallback)
        nested = [str(p.relative_to(d)) for p in d.rglob(".git")]
        info["nested_git_before_remove"] = nested
        meta[name] = info
        for path in sorted(d.rglob(".git"), reverse=True):
            if umbrella in path.parents or path == umbrella:
                raise RuntimeError(f"Refusing to touch umbrella git: {path}")
            if not str(path).startswith(str(d)):
                raise RuntimeError(f"Path escaped project tree: {path}")
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"removed {path}")
        assert not (d / ".git").exists(), name
        print(f"{name} stripped @ {info['sha']}")
    out = ROOT / "reports" / "source_versions.json"
    out.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {out}")
    print("umbrella .git intact:", umbrella.is_dir())


if __name__ == "__main__":
    main()
