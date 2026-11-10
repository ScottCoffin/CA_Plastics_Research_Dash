"""Offline acceptance check for S9.1 work-grant links.

Verifies the committed link table (schema, evidence fields, no uncertain links),
the QC document, and the spot-check document with its precision line. Makes no
network calls. Exits 0 on success and 1 with a list of failures otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
LINKS = ROOT / "data/processed/work_grant_links.parquet"
QC = ROOT / "docs/work_grant_links_qc.md"
SPOTCHECK = ROOT / "docs/S9_1_SPOTCHECK.md"

EXPECTED_COLUMNS = [
    "work_id",
    "grant_key",
    "grant_source",
    "evidence_type",
    "evidence_value",
    "confidence",
]
EVIDENCE_TYPES = {"openalex-award", "acknowledgement-match", "fixed-string"}


def main() -> int:
    failures: list[str] = []

    if not LINKS.exists():
        failures.append(f"missing {LINKS.relative_to(ROOT)}")
    else:
        table = pq.read_table(LINKS)
        if table.column_names != EXPECTED_COLUMNS:
            failures.append(f"columns {table.column_names} != {EXPECTED_COLUMNS}")
        rows = table.to_pylist()
        print(f"links: {len(rows)}")
        for position, row in enumerate(rows):
            for field in ("work_id", "grant_key", "evidence_type", "evidence_value"):
                if not row.get(field):
                    failures.append(f"row {position}: empty {field}")
            if row.get("evidence_type") not in EVIDENCE_TYPES:
                failures.append(
                    f"row {position}: unknown evidence_type {row.get('evidence_type')!r}"
                )
            if row.get("confidence") != "high":
                failures.append(f"row {position}: non-high confidence {row.get('confidence')!r}")
        keys = [(r["work_id"], r["grant_key"]) for r in rows]
        if len(keys) != len(set(keys)):
            failures.append("duplicate (work_id, grant_key) pairs")

    if not QC.exists():
        failures.append(f"missing {QC.relative_to(ROOT)}")

    if not SPOTCHECK.exists():
        failures.append(f"missing {SPOTCHECK.relative_to(ROOT)}")
    else:
        text = SPOTCHECK.read_text(encoding="utf-8")
        match = re.search(r"Precision\s*=.*?(\d+(?:\.\d+)?)%", text)
        if not match:
            failures.append("spot-check file has no 'Precision ... %' line")
        else:
            print(f"spot-check precision: {match.group(1)}%")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
