#!/usr/bin/env python3
"""Download publicly available VLN assets into /media/ubuntu/D/VLN_shared."""
from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SHARED = Path(os.environ.get("VLN_SHARED", "/shared"))
PROXY = os.environ.get("https_proxy") or os.environ.get("http_proxy") or ""
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"

JOBS = [
    # (url, relpath, expected_min_bytes, prefer_proxy)
    (
        "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth",
        "checkpoints/sam/sam_vit_h_4b8939.pth",
        2_400_000_000,
        False,
    ),
    (
        "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth",
        "checkpoints/sam/sam_vit_l_0b3195.pth",
        1_100_000_000,
        False,
    ),
    (
        "https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v1/objectnav_hm3d_v1.zip",
        "downloads/objectnav_hm3d_v1.zip",
        50_000_000,
        False,
    ),
    (
        "https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v2/objectnav_hm3d_v2.zip",
        "downloads/objectnav_hm3d_v2.zip",
        50_000_000,
        False,
    ),
    (
        "https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/m3d/v1/objectnav_mp3d_v1.zip",
        "downloads/objectnav_mp3d_v1.zip",
        5_000_000,
        False,
    ),
    (
        "https://dl.fbaipublicfiles.com/habitat/data/datasets/imagenav/hm3d/v3/instance_imagenav_hm3d_v3.zip",
        "downloads/instance_imagenav_hm3d_v3.zip",
        5_000_000,
        False,
    ),
    (
        "https://huggingface.co/GLIPModel/GLIP/resolve/main/glip_large_model.pth",
        "checkpoints/glip/glip_large_model.pth",
        1_000_000_000,
        True,
    ),
    (
        "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8x-worldv2.pt",
        "checkpoints/yolo_world/yolov8x-worldv2.pt",
        100_000_000,
        True,
    ),
]


def opener(use_proxy: bool):
    handlers = []
    if use_proxy and PROXY:
        handlers.append(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        )
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def fetch(url: str, path: Path, min_bytes: int, prefer_proxy: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.stat().st_size if path.exists() else 0
    if existing >= min_bytes:
        print(f"SKIP {path} ({existing})", flush=True)
        return True

    modes = [prefer_proxy, not prefer_proxy]
    for use_proxy in modes:
        try:
            print(
                f"GET {url} -> {path} (have={existing}, proxy={use_proxy})",
                flush=True,
            )
            t0 = time.time()
            headers = {"User-Agent": UA}
            if existing > 0:
                headers["Range"] = f"bytes={existing}-"
            req = urllib.request.Request(url, headers=headers)
            op = opener(use_proxy)
            with op.open(req, timeout=600) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                mode = "ab" if existing > 0 and code == 206 else "wb"
                if mode == "wb":
                    existing = 0
                wrote = 0
                with open(path, mode) as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        wrote += len(chunk)
                        if wrote % (64 * 1024 * 1024) < 1024 * 1024:
                            sz = path.stat().st_size
                            print(f"  ... {sz/1e9:.2f} GB", flush=True)
            sz = path.stat().st_size
            print(f"OK  {path} {sz} in {time.time()-t0:.1f}s", flush=True)
            if sz >= min_bytes:
                return True
            print(f"SMALL {path} {sz} < {min_bytes}, will retry", flush=True)
            existing = sz
        except Exception as e:
            print(f"FAIL proxy={use_proxy}: {e}", flush=True)
    return path.exists() and path.stat().st_size >= min_bytes


def main() -> int:
    print(f"SHARED={SHARED} PROXY={PROXY}", flush=True)
    ok = fail = 0
    for url, rel, vmin, pref in JOBS:
        path = SHARED / rel
        if fetch(url, path, vmin, pref):
            ok += 1
        else:
            fail += 1
    # MSGNav alias
    sam_l = SHARED / "checkpoints/sam/sam_vit_l_0b3195.pth"
    alias = SHARED / "checkpoints/sam/sam_l.pt"
    if sam_l.exists():
        if alias.exists() or alias.is_symlink():
            alias.unlink()
        alias.symlink_to(sam_l.name)
        print(f"LINK {alias} -> {sam_l.name}", flush=True)
    # yolo alias
    yw = SHARED / "checkpoints/yolo_world/yolov8x-worldv2.pt"
    if yw.exists():
        alias2 = SHARED / "checkpoints/yolo_world/yolov8x-world.pt"
        if alias2.exists() or alias2.is_symlink():
            alias2.unlink()
        alias2.symlink_to(yw.name)
    print(f"SUMMARY ok={ok} fail={fail}", flush=True)
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
