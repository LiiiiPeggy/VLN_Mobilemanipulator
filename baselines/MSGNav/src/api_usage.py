################################
# Adapter: aggregate OpenAI-compatible usage for MSGNav cost probes.
# Enable via MSGNAV_API_USAGE_LOG=/path/to/usage.jsonl (append JSON lines).
################################
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Optional

_lock = threading.Lock()
_stats = {
    "calls": 0,
    "ok": 0,
    "errors": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "models": {},
}


def _log_path() -> Optional[str]:
    p = os.getenv("MSGNAV_API_USAGE_LOG", "").strip()
    return p or None


def record_completion(model: str, response: Any = None, error: str = None) -> None:
    usage = None
    if response is not None:
        usage = getattr(response, "usage", None)
    pt = ct = tt = 0
    if usage is not None:
        pt = int(getattr(usage, "prompt_tokens", 0) or 0)
        ct = int(getattr(usage, "completion_tokens", 0) or 0)
        tt = int(getattr(usage, "total_tokens", 0) or (pt + ct))
    with _lock:
        _stats["calls"] += 1
        if error:
            _stats["errors"] += 1
        else:
            _stats["ok"] += 1
        _stats["prompt_tokens"] += pt
        _stats["completion_tokens"] += ct
        _stats["total_tokens"] += tt
        m = _stats["models"].setdefault(
            model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        )
        m["calls"] += 1
        m["prompt_tokens"] += pt
        m["completion_tokens"] += ct
        m["total_tokens"] += tt
        snap = {
            "ts": time.time(),
            "model": model,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": tt,
            "error": error,
            "cum": {
                "calls": _stats["calls"],
                "ok": _stats["ok"],
                "errors": _stats["errors"],
                "prompt_tokens": _stats["prompt_tokens"],
                "completion_tokens": _stats["completion_tokens"],
                "total_tokens": _stats["total_tokens"],
            },
        }
    path = _log_path()
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")


def dump_summary(path: str) -> dict:
    with _lock:
        data = dict(_stats)
        data["models"] = {k: dict(v) for k, v in _stats["models"].items()}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data


def get_stats() -> dict:
    with _lock:
        return {
            **{k: v for k, v in _stats.items() if k != "models"},
            "models": {k: dict(v) for k, v in _stats["models"].items()},
        }


################################
