#!/usr/bin/env python3
"""Live / offline aggregate of ApexNav full-val record.txt failure reasons."""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

PAPER = {"dataset": "HM3D-v2 val", "n_episodes": 1000, "SR": 76.2, "SPL": 38.0}


def parse_record(rec: Path):
    failures = Counter()
    episodes = []
    if not rec.is_file():
        return episodes, failures
    blocks = re.split(r"(?=Scene ID: )", rec.read_text(errors="ignore"))
    for b in blocks:
        if "Scene ID:" not in b:
            continue
        m_scene = re.search(r"Scene ID:\s*(\S+)", b)
        m_ep = re.search(r"Episode ID:\s*(\S+)", b)
        m_res = re.search(r"success or not:\s*(.+)", b)
        m_lab = re.search(r"target to find is\s*(.+)", b)
        m_no = re.search(r"No\.(\d+) task is finished", b)
        m_sr = re.search(r"Average Success\s+\|\s+([\d.]+)%", b)
        m_spl = re.search(r"Average SPL\s+\|\s+([\d.]+)%", b)
        res = m_res.group(1).strip() if m_res else "unknown"
        failures[res] += 1
        episodes.append(
            {
                "n": int(m_no.group(1)) if m_no else None,
                "scene": m_scene.group(1) if m_scene else None,
                "episode_id": m_ep.group(1) if m_ep else None,
                "label": m_lab.group(1).strip() if m_lab else None,
                "result": res,
                "running_sr_pct": float(m_sr.group(1)) if m_sr else None,
                "running_spl_pct": float(m_spl.group(1)) if m_spl else None,
            }
        )
    episodes = list(reversed(episodes))  # chronological
    return episodes, failures


def summarize(out_dir: Path) -> dict:
    rec = out_dir / "videos_hm3dv2_val" / "record.txt"
    episodes, failures = parse_record(rec)
    n = len(episodes)
    n_succ = failures.get("success", 0)
    by_label = Counter()
    fail_by_label = Counter()
    for e in episodes:
        lab = e.get("label") or "?"
        by_label[lab] += 1
        if e["result"] != "success":
            fail_by_label[f"{lab}::{e['result']}"] += 1
    summary = {
        "paper_target": PAPER,
        "n_completed": n,
        "n_success": n_succ,
        "SR_pct": (100.0 * n_succ / n) if n else None,
        "final_running_sr_pct": episodes[-1]["running_sr_pct"] if episodes else None,
        "final_running_spl_pct": episodes[-1]["running_spl_pct"] if episodes else None,
        "gap_sr_pp": (
            None
            if not n
            else (100.0 * n_succ / n) - PAPER["SR"]
        ),
        "failure_hist": dict(failures.most_common()),
        "failure_share_pct": {
            k: round(100.0 * v / max(1, n - n_succ), 2)
            for k, v in failures.most_common()
            if k != "success"
        },
        "top_fail_by_label_reason": fail_by_label.most_common(20),
        "out_dir": str(out_dir),
        "record_exists": rec.is_file(),
        "record_bytes": rec.stat().st_size if rec.is_file() else 0,
    }
    (out_dir / "live_summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "failure_hist.json").write_text(json.dumps(dict(failures), indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Run output directory")
    ap.add_argument("--watch", type=int, default=0, help="Rescan every N seconds (0=once)")
    args = ap.parse_args()
    out = Path(args.out)
    while True:
        s = summarize(out)
        print(
            json.dumps(
                {
                    "n": s["n_completed"],
                    "SR": s["SR_pct"],
                    "SPL_running": s["final_running_spl_pct"],
                    "gap_sr_pp": s["gap_sr_pp"],
                    "failures": s["failure_hist"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if args.watch <= 0:
            break
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
