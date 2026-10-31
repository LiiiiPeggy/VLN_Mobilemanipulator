#!/usr/bin/env python3
"""Fallback download for SAM ViT-L when Facebook CDN returns 403."""
import os, time, urllib.request
from pathlib import Path

SHARED = Path(os.environ.get("VLN_SHARED", "/shared"))
PROXY = os.environ.get("https_proxy") or ""
UA = "Mozilla/5.0"
URLS = [
    "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth",
]
out = SHARED / "checkpoints/sam/sam_vit_l_0b3195.pth"
out.parent.mkdir(parents=True, exist_ok=True)
min_bytes = 1_100_000_000
if out.exists() and out.stat().st_size >= min_bytes:
    print("SKIP", out, out.stat().st_size)
    raise SystemExit(0)

def opener(use_proxy: bool):
    if use_proxy and PROXY:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        )
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))

for url in URLS:
    for use_proxy in (True, False):
        try:
            print("GET", url, "proxy=", use_proxy, flush=True)
            t0 = time.time()
            existing = out.stat().st_size if out.exists() else 0
            headers = {"User-Agent": UA}
            if existing:
                headers["Range"] = f"bytes={existing}-"
            req = urllib.request.Request(url, headers=headers)
            with opener(use_proxy).open(req, timeout=600) as r:
                code = getattr(r, "status", None) or r.getcode()
                mode = "ab" if existing and code == 206 else "wb"
                with open(out, mode) as f:
                    n = 0
                    while True:
                        c = r.read(1024 * 1024)
                        if not c:
                            break
                        f.write(c)
                        n += len(c)
                        if n % (64 * 1024 * 1024) < 1024 * 1024:
                            print(f"  ... {out.stat().st_size/1e9:.2f} GB", flush=True)
            print("OK", out, out.stat().st_size, f"{time.time()-t0:.1f}s", flush=True)
            if out.stat().st_size >= min_bytes:
                alias = out.parent / "sam_l.pt"
                if alias.exists() or alias.is_symlink():
                    alias.unlink()
                alias.symlink_to(out.name)
                print("LINK", alias, flush=True)
                raise SystemExit(0)
        except SystemExit:
            raise
        except Exception as e:
            print("FAIL", e, flush=True)
print("ALL_FAILED")
raise SystemExit(2)
