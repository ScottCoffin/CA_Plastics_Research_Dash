"""Offline acceptance check for S9.2 work-dataset links.

Verifies the committed link table (schema, evidence types, uniqueness, high
confidence), the QC document, and the site render hooks. Makes no network calls.
Exits 0 on success and 1 with a list of failures otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
LINKS = ROOT / "data/processed/work_dataset_links.parquet"
QC = ROOT / "docs/work_dataset_links_qc.md"
INDEX = ROOT / "site/index.html"

EXPECTED_COLUMNS = [
    "work_id",
    "dataset_doi",
    "relation_type",
    "evidence_type",
    "evidence_value",
    "confidence",
]
EVIDENCE_TYPES = {"DataCite-relation", "DAS-match"}


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
            for field in ("work_id", "dataset_doi", "relation_type", "evidence_value"):
                if not row.get(field):
                    failures.append(f"row {position}: empty {field}")
            if row.get("evidence_type") not in EVIDENCE_TYPES:
                failures.append(
                    f"row {position}: unknown evidence_type {row.get('evidence_type')!r}"
                )
            if row.get("confidence") != "high":
                failures.append(f"row {position}: non-high confidence {row.get('confidence')!r}")
        keys = [(r["work_id"], r["dataset_doi"]) for r in rows]
        if len(keys) != len(set(keys)):
            failures.append("duplicate (work_id, dataset_doi) pairs")
        for evidence in sorted(EVIDENCE_TYPES):
            print(f"  {evidence}: {sum(r.get('evidence_type') == evidence for r in rows)}")

    if not QC.exists():
        failures.append(f"missing {QC.relative_to(ROOT)}")
    elif "# Work-dataset links QC (S9.2)" not in QC.read_text(encoding="utf-8"):
        failures.append("QC document heading missing")

    html = INDEX.read_text(encoding="utf-8")
    for needle in (
        '<script id="work-dataset-view-helpers">',
        "${workDatasetView.datasetsHtml(work)}",
        "${workDatasetView.linkedWorksHtml(row)}",
    ):
        if needle not in html:
            failures.append(f"site/index.html missing render hook {needle!r}")

    if failures:
        print("FAIL")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
