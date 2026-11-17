#!/usr/bin/env python3
"""Poll formal JSONL then write accounting. Does not kill other processes."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/ubuntu/locomani/VLN_Mobilemanipulator")
FORM = ROOT / "reports/ranger_category_eval_20261116/formal_fixed_gimbal_v1"
REP = ROOT / "reports/ranger_category_eval_20261116"
BATCH_ID = "formal150_full_20261117_190344"
JSONL = FORM / f"batch_{BATCH_ID}.jsonl"
META = FORM / f"batch_{BATCH_ID}_meta.json"
LOG = FORM / "finalize_watcher.log"
PIDFILE = FORM / "latest_full_pid.txt"
VALIDITY = REP / "lists/independent_list_validity_v1_post.json"
if not VALIDITY.is_file():
    VALIDITY = REP / "lists/independent_list_validity_v1.json"


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n"
    LOG.open("a").write(line)


def main() -> int:
    n_expect = 109
    if META.is_file():
        n_expect = int(json.loads(META.read_text()).get("n_jobs", 109))
    log(f"watch {JSONL} expect={n_expect}")
    while True:
        n = 0
        if JSONL.is_file():
            n = sum(1 for l in JSONL.read_text().splitlines() if l.strip())
        log(f"have={n}/{n_expect}")
        dead = False
        if PIDFILE.is_file():
            try:
                fp = int(PIDFILE.read_text().strip())
                Path(f"/proc/{fp}").stat()
            except Exception:
                dead = True
        if n >= n_expect or (dead and n > 0):
            break
        time.sleep(120)

    cmd = [
        sys.executable,
        str(ROOT / "adapters/habitat_rangercr10/evaluation/scripts/write_formal_accounting_report.py"),
        str(JSONL),
        "--validity",
        str(VALIDITY),
        "--out_json",
        str(FORM / f"accounting_{BATCH_ID}.json"),
        "--out_md",
        str(FORM / f"accounting_{BATCH_ID}.md"),
    ]
    log("running " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    log(f"accounting rc={r.returncode} out={r.stdout.strip()} err={r.stderr.strip()}")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "adapters/habitat_rangercr10/evaluation/scripts/summarize_category_metrics.py"),
            str(JSONL),
            "--out",
            str(FORM / f"summary_{BATCH_ID}.json"),
        ],
        check=False,
    )
    arch = {
        "archive_id": "formal_independent_v1_150_100",
        "batch_id": BATCH_ID,
        "role": "frozen_independent_eval",
        "jsonl": str(JSONL),
        "accounting": str(FORM / f"accounting_{BATCH_ID}.json"),
        "validity": str(VALIDITY),
        "camera_mode": "fixed_base_gimbal",
        "budget": {"max_steps": 150, "max_explore_actions": 100},
        "written_utc": datetime.now(timezone.utc).isoformat(),
        "n_rows_at_finalize": n,
        "note": "Per-run executor_version/SHA from artifacts; do not mix with short50 or hist 8/24.",
    }
    (REP / "archives/02_formal_independent_v1.json").write_text(json.dumps(arch, indent=2) + "\n")
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
