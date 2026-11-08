#!/usr/bin/env python3
"""Compare discovery metrics: Hold baseline vs label-map batch."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path("/media/ubuntu/D/VLN_shared/runs/habitat_rangercr10/apexnav_real")


def load_batch(jsonl: Path):
    return [json.loads(l) for l in jsonl.read_text().splitlines() if l.strip()]


def ep_metrics(row: dict) -> dict:
    run = BASE / row["run_id"]
    steps = []
    if (run / "steps.jsonl").is_file():
        steps = [json.loads(l) for l in (run / "steps.jsonl").read_text().splitlines() if l.strip()]
    nd = [int(s.get("n_detections") or 0) for s in steps]
    plans = Counter()
    jl = run / "native_diag" / "native_plan_diag.jsonl"
    if jl.is_file():
        for l in jl.read_text().splitlines():
            if l.strip():
                plans[json.loads(l).get("result")] += 1
    first_det = next((s["step"] for s, n in zip(steps, nd) if n > 0), None)
    first_search = None
    for s in steps:
        er = s.get("expl_result")
        # SEARCH_BEST_OBJECT == 1 in ApexNav RESULT enum used by adapter hist
        name = s.get("expl_result_name")
        if er == 1 or (isinstance(name, str) and "SEARCH_BEST" in name):
            first_search = s["step"]
            break
    # Prefer plan diag for SEARCH_BEST presence
    has_search_best = plans.get("SEARCH_BEST_OBJECT", 0) > 0
    if has_search_best and first_search is None:
        # recover from plan diag timestamps via step alignment: first step with expl_result==1
        for s in steps:
            if int(s.get("expl_result") or -1) == 1:
                first_search = s["step"]
                break
    tl = {}
    if (run / "target_label.json").is_file():
        tl = json.loads((run / "target_label.json").read_text())
    det_to_search = None
    if first_det is not None and first_search is not None and first_search >= first_det:
        det_to_search = first_search - first_det
    return {
        "id": row.get("episode_list_id"),
        "cat": row.get("category") or tl.get("object_category"),
        "label": tl.get("label"),
        "label_mapped": tl.get("label_mapped"),
        "sum_ndet": sum(nd),
        "n_pos": sum(1 for v in nd if v > 0),
        "has_valid_candidate": sum(nd) > 0,
        "has_search_best": has_search_best,
        "plans": dict(plans),
        "first_det_step": first_det,
        "first_search_step": first_search,
        "det_to_search_steps": det_to_search,
        "sr_proxy": bool(row.get("objectnav_success_proxy")),
        "fail_class": row.get("fail_class"),
        "term": row.get("termination"),
        "final_dtg": row.get("final_dtg"),
        "n_steps": row.get("n_steps"),
    }


def summarize(name: str, rows: list) -> dict:
    mets = [ep_metrics(r) for r in rows]
    return {
        "batch": name,
        "n": len(mets),
        "n_valid_candidate": sum(1 for m in mets if m["has_valid_candidate"]),
        "n_search_best": sum(1 for m in mets if m["has_search_best"]),
        "sr_proxy": sum(1 for m in mets if m["sr_proxy"]),
        "fail": dict(Counter(m["fail_class"] for m in mets)),
        "det_to_search_mean": (
            sum(m["det_to_search_steps"] for m in mets if m["det_to_search_steps"] is not None)
            / max(1, sum(1 for m in mets if m["det_to_search_steps"] is not None))
        ),
        "episodes": mets,
    }


def main():
    paths = [Path(p) for p in sys.argv[1:]]
    out = {}
    for p in paths:
        out[p.stem] = summarize(p.stem, load_batch(p))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
