#!/usr/bin/env python3
# ################################
# VLN adapt: finalize validity JSON → markdown + valid-only list (no score filter)
# ################################
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--validity",
        type=Path,
        default=ROOT
        / "reports/ranger_category_eval_20261116/lists/independent_list_validity_v1.json",
    )
    ap.add_argument(
        "--out_dir",
        type=Path,
        default=ROOT / "reports/ranger_category_eval_20261116/lists",
    )
    args = ap.parse_args()
    doc = json.loads(args.validity.read_text())
    rows = doc["episodes"]

    # Post-rule: adapted_start ok=False ⇒ invalid (full-robot gate), even if no pen
    for r in rows:
        reasons = r.get("reasons") or []
        if "adapted_start_not_ok_flag" in reasons and r.get("status") == "valid":
            r["status"] = "invalid"
            r["reasons"] = reasons + ["reclassified_adapted_start_not_ok"]

    counts = Counter(r["status"] for r in rows)
    by_cat = defaultdict(Counter)
    for r in rows:
        by_cat[r["category"]][r["status"]] += 1
    reason_c = Counter()
    for r in rows:
        for reason in r.get("reasons") or []:
            if r["status"] != "valid":
                reason_c[reason] += 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    md = [
        "# 独立清单有效性表 v1",
        "",
        f"- code_git_sha: `{doc.get('code_git_sha')}`",
        f"- n_checked: **{len(rows)}** / 120",
        f"- counts: `{dict(counts)}`",
        f"- elapsed_sec: {doc.get('elapsed_sec')}",
        "- 原始清单未删条目；本表仅标注 valid/invalid。",
        "- **未**按 SR/SEARCH/可见性筛选。",
        "",
        "## 逐类",
        "",
        "| category | valid | invalid | pending |",
        "|----------|------:|--------:|--------:|",
    ]
    for cat in sorted(by_cat):
        c = by_cat[cat]
        md.append(
            f"| {cat} | {c.get('valid',0)} | {c.get('invalid',0)} | {c.get('pending',0)} |"
        )
    md += ["", "## 无效原因（可重复计）", "", "```", str(dict(reason_c)), "```", ""]
    md += [
        "## 逐例",
        "",
        "| id | cat | status | reasons | spawn_source | init_pen |",
        "|----|-----|--------|---------|--------------|----------|",
    ]
    for r in rows:
        md.append(
            f"| {r['id']} | {r['category']} | {r['status']} | "
            f"{';'.join(r.get('reasons') or [])} | {r.get('spawn_source')} | "
            f"{r.get('initial_penetration')} |"
        )
    (args.out_dir / "independent_list_validity_v1.md").write_text("\n".join(md) + "\n")

    doc["counts"] = {
        "valid": counts.get("valid", 0),
        "invalid": counts.get("invalid", 0),
        "pending": counts.get("pending", 0),
    }
    doc["postprocess"] = "adapted_start_not_ok → invalid"
    # Write sidecar (validity JSON may be root-owned while validator runs)
    (args.out_dir / "independent_list_validity_v1_post.json").write_text(
        json.dumps(doc, indent=2) + "\n"
    )
    try:
        args.validity.write_text(json.dumps(doc, indent=2) + "\n")
    except PermissionError:
        print("note: could not rewrite source validity (permission); wrote _post.json")

    valid_eps = [r for r in rows if r["status"] == "valid"]
    (args.out_dir / "independent_valid_only_v1.json").write_text(
        json.dumps(
            {
                "name": "independent_valid_only_v1",
                "source_validity": str(args.validity),
                "n": len(valid_eps),
                "episodes": valid_eps,
                "note": "Subset for formal runs; original 120 list unchanged.",
            },
            indent=2,
        )
        + "\n"
    )
    print(dict(counts), "valid_only", len(valid_eps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
