"""Carry the owner's AT-1 audit labels into ``curation/overrides_works.csv``.

The audit CSVs (``docs/QUERY_AUDIT_REVIEW.csv`` for v2, ``docs/QUERY_AUDIT_REVIEW_V3.csv``
for the v3 repeat sample) hold owner judgements of whether a work is about plastic
pollution. Those judgements outrank the keyword rules:

- ``not_relevant`` -> ``exclude = true``: the work leaves the public corpus, and authors
  lose its credit.
- ``relevant`` -> ``plastic_related = true``.
- ``unsure`` and blank labels are not carried.

When both files label a work, the later (v3) file wins. Rows in the overrides file whose
reason does not start with the audit marker are preserved unchanged. Offline and
idempotent; ``--check`` exits 1 when the committed file is stale.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

AUDIT_FILES = (Path("docs/QUERY_AUDIT_REVIEW.csv"), Path("docs/QUERY_AUDIT_REVIEW_V3.csv"))
OVERRIDES = Path("curation/overrides_works.csv")
HEADER = ["work_id", "field", "value", "reason", "reviewed_by", "reviewed_at"]
MARKER = "AT-1 owner audit label"
AUDIT_DATE = {
    "QUERY_AUDIT_REVIEW.csv": "2026-11-10",
    "QUERY_AUDIT_REVIEW_V3.csv": "2026-11-11",
}


def audit_rows(paths: tuple[Path, ...] = AUDIT_FILES) -> list[dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                label = (row.get("review_label") or "").strip()
                work_id = (row.get("work_id") or "").strip().rsplit("/", 1)[-1]
                if not work_id or label not in {"relevant", "not_relevant"}:
                    continue
                labels[work_id] = {
                    "label": label,
                    "reviewer": (row.get("reviewer") or "owner").strip() or "owner",
                    "date": AUDIT_DATE.get(path.name, ""),
                    "source": path.name,
                }
    rows = []
    for work_id in sorted(labels):
        item = labels[work_id]
        excluded = item["label"] == "not_relevant"
        rows.append(
            {
                "work_id": work_id,
                "field": "exclude" if excluded else "plastic_related",
                "value": "true",
                "reason": f"{MARKER} ({item['source']}): {item['label']}",
                "reviewed_by": item["reviewer"],
                "reviewed_at": item["date"],
            }
        )
    return rows


def render(existing: Path = OVERRIDES, paths: tuple[Path, ...] = AUDIT_FILES) -> str:
    kept: list[dict[str, str]] = []
    if existing.exists():
        with existing.open(encoding="utf-8", newline="") as stream:
            kept = [
                row
                for row in csv.DictReader(stream)
                if not (row.get("reason") or "").startswith(MARKER)
            ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=HEADER, lineterminator="\n")
    writer.writeheader()
    for row in [*kept, *audit_rows(paths)]:
        writer.writerow({key: row.get(key, "") for key in HEADER})
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OVERRIDES)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = render(args.output)
    current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
    if args.check:
        if current != text:
            print(f"{args.output} is stale; run scripts/build_audit_overrides.py", file=sys.stderr)
            return 1
        return 0
    args.output.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {text.count(chr(10)) - 1} override rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
