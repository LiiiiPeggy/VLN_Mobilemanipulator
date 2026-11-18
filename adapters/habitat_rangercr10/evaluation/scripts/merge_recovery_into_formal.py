#!/usr/bin/env python3
# ################################
# VLN adapt: merge recovery rows into formal set without double-counting
# ################################
"""Keep original empty/crash rows in archive; scoring uses latest successful
recovery when present, else original. recovery_of must match episode_list_id.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from write_formal_accounting_report import build, to_markdown  # noqa: E402
from summarize_category_metrics import summarize  # noqa: E402


def _load(path: Path):
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def merge(primary, recoveries):
    by_id = {r["episode_list_id"]: dict(r) for r in primary}
    archive_replaced = []
    for rec in recoveries:
        eid = rec.get("recovery_of") or rec.get("episode_list_id")
        if eid not in by_id:
            continue
        # only replace if recovery produced a real run (not missing_summary / empty)
        if rec.get("run_status") in (None, "missing_summary"):
            continue
        if rec.get("run_status") == "empty_run" and by_id[eid].get("run_status") == "empty_run":
            continue
        archive_replaced.append(
            {
                "episode_list_id": eid,
                "primary_run_id": by_id[eid].get("run_id"),
                "recovery_run_id": rec.get("run_id"),
                "primary_status": by_id[eid].get("run_status"),
                "recovery_status": rec.get("run_status"),
                "recovery_sr_proxy": rec.get("sr_proxy"),
            }
        )
        merged = dict(rec)
        merged["episode_list_id"] = eid
        merged["replaced_primary_run_id"] = by_id[eid].get("run_id")
        merged["archive_role"] = "formal_independent_v1_scored_via_recovery"
        by_id[eid] = merged
    return list(by_id.values()), archive_replaced


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--primary", type=Path, required=True)
    ap.add_argument("--recovery", type=Path, required=True)
    ap.add_argument("--validity", type=Path, required=True)
    ap.add_argument("--out_jsonl", type=Path, required=True)
    ap.add_argument("--out_accounting_json", type=Path, required=True)
    ap.add_argument("--out_accounting_md", type=Path, required=True)
    ap.add_argument("--out_summary", type=Path, required=True)
    ap.add_argument("--out_merge_log", type=Path, required=True)
    args = ap.parse_args()

    primary = _load(args.primary)
    recovery = _load(args.recovery)
    merged, replaced = merge(primary, recovery)
    args.out_jsonl.write_text("\n".join(json.dumps(r) for r in merged) + "\n")
    validity = json.loads(args.validity.read_text())
    doc = build(merged, validity)
    args.out_accounting_json.write_text(json.dumps(doc, indent=2) + "\n")
    args.out_accounting_md.write_text(to_markdown(doc))
    args.out_summary.write_text(json.dumps(summarize(merged), indent=2) + "\n")
    args.out_merge_log.write_text(
        json.dumps({"n_primary": len(primary), "n_recovery": len(recovery), "replaced": replaced}, indent=2)
        + "\n"
    )
    print(f"merged={len(merged)} replaced={len(replaced)} -> {args.out_jsonl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
