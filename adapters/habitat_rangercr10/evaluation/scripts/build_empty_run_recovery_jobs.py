#!/usr/bin/env python3
# ################################
# VLN adapt: queue recovery jobs for empty_run / crash rows (not score-based)
# ################################
"""Build a recovery TSV from formal JSONL. recovery_of keeps linkage; originals stay.

Rule (algorithm-agnostic): recover only when run_status in
{empty_run, crash, timeout, abort, missing_summary} OR shell_rc!=0 with n_steps==0.
Do NOT recover wrong_stop / budget / no_search failures.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RECOVERABLE = {"empty_run", "crash", "timeout", "abort", "missing_summary"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl", type=Path)
    ap.add_argument("--jobs_orig", type=Path, required=True)
    ap.add_argument("--out_tsv", type=Path, required=True)
    ap.add_argument("--out_json", type=Path, required=True)
    args = ap.parse_args()

    orig = {}
    for line in args.jobs_orig.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        orig[parts[0]] = parts

    rows = [json.loads(l) for l in args.jsonl.read_text().splitlines() if l.strip()]
    recover = []
    for r in rows:
        eid = r.get("episode_list_id")
        n_steps = r.get("n_steps_observed")
        shell_rc = r.get("shell_rc")
        status = r.get("run_status")
        need = status in RECOVERABLE or (
            shell_rc not in (None, 0) and (n_steps is None or int(n_steps) == 0)
        )
        if not need:
            continue
        if eid not in orig:
            continue
        recover.append(
            {
                "episode_list_id": eid,
                "recovery_of": eid,
                "reason": status,
                "shell_rc": shell_rc,
                "n_steps_observed": n_steps,
                "job": orig[eid],
            }
        )

    lines = ["\t".join(x["job"]) for x in recover]
    args.out_tsv.parent.mkdir(parents=True, exist_ok=True)
    args.out_tsv.write_text("\n".join(lines) + ("\n" if lines else ""))
    args.out_json.write_text(json.dumps({"n": len(recover), "episodes": recover}, indent=2) + "\n")
    print(f"recovery_jobs={len(recover)} -> {args.out_tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
