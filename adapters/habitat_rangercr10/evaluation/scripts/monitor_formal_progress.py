#!/usr/bin/env python3
# ################################
# VLN adapt: snapshot formal batch progress without touching the runner
# ################################
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report_dir", type=Path, required=True)
    ap.add_argument("--batch_id", required=True)
    ap.add_argument("--jobs", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = args.report_dir
    jobs_path = args.jobs or report / f"_jobs_{args.batch_id}.tsv"
    summary_path = report / f"batch_{args.batch_id}.jsonl"
    jobs = []
    if jobs_path.is_file():
        for line in jobs_path.read_text().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            jobs.append(parts[0])
    done_ids = []
    if summary_path.is_file():
        for line in summary_path.read_text().splitlines():
            if not line.strip():
                continue
            done_ids.append(json.loads(line).get("episode_list_id"))
    n_jobs = len(jobs)
    n_done = len(done_ids)
    current = None
    if n_done < n_jobs:
        current = jobs[n_done]
    snap = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "batch_id": args.batch_id,
        "n_jobs": n_jobs,
        "n_done": n_done,
        "n_remaining": max(0, n_jobs - n_done),
        "current_episode_list_id": current,
        "done_ids": done_ids,
        "pct": (100.0 * n_done / n_jobs) if n_jobs else 0.0,
    }
    out = args.out or report / f"progress_{args.batch_id}.json"
    out.write_text(json.dumps(snap, indent=2) + "\n")
    md = report / f"progress_{args.batch_id}.md"
    md.write_text(
        f"# Formal progress `{args.batch_id}`\n\n"
        f"- updated: {snap['ts_utc']}\n"
        f"- done: **{n_done}/{n_jobs}** ({snap['pct']:.1f}%)\n"
        f"- current: `{current}`\n"
        f"- remaining: {snap['n_remaining']}\n"
    )
    print(json.dumps(snap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
