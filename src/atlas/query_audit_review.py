"""Read and write owner labels in ``docs/QUERY_AUDIT_REVIEW.csv`` (AT-1 precision audit).

Pure-Python helpers behind the local Streamlit review app
(``scripts/review_query_audit_app.py``). A label belongs to a work, so writing one
updates every row with the same ``work_id`` (the sample repeats 51 works across
institution strata). Writes are atomic and keep the file's column order and line
endings, so unlabeled rows stay byte-identical.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REVIEW_CSV = Path("docs/QUERY_AUDIT_REVIEW.csv")
LABELS = {
    "relevant": "Relevant",
    "not_relevant": "Not relevant",
    "unsure": "Unsure",
}
LABEL_FIELDS = ("review_label", "reviewer", "noise_terms")


@dataclass
class ReviewTable:
    header: list[str]
    rows: list[dict[str, str]]
    line_terminator: str

    def works(self) -> list[dict[str, object]]:
        """One entry per ``work_id`` in first-seen order, listing its strata."""
        order: list[str] = []
        by_work: dict[str, dict[str, object]] = {}
        for row in self.rows:
            work_id = row["work_id"]
            if work_id not in by_work:
                order.append(work_id)
                by_work[work_id] = {**row, "institutions": []}
            institutions = by_work[work_id]["institutions"]
            assert isinstance(institutions, list)
            institutions.append(row["institution_name"])
        return [by_work[work_id] for work_id in order]

    def label_counts(self) -> Counter[str]:
        counts: Counter[str] = Counter()
        for work in self.works():
            counts[str(work.get("review_label") or "") or "unlabeled"] += 1
        return counts


def load_review(path: Path = REVIEW_CSV) -> ReviewTable:
    raw = path.read_bytes().decode("utf-8")
    terminator = "\r\n" if "\r\n" in raw else "\n"
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    header = list(reader.fieldnames or [])
    missing = [field for field in ("work_id", *LABEL_FIELDS) if field not in header]
    if missing:
        raise ValueError(f"{path} lacks columns {missing}")
    return ReviewTable(header=header, rows=list(reader), line_terminator=terminator)


def set_label(
    table: ReviewTable, work_id: str, label: str, reviewer: str, noise_terms: str = ""
) -> int:
    """Apply a label to every row of ``work_id``; return the number of rows changed."""
    if label not in LABELS and label != "":
        raise ValueError(f"label must be one of {sorted(LABELS)} or blank")
    if label and not reviewer.strip():
        raise ValueError("reviewer initials are required with a label")
    changed = 0
    for row in table.rows:
        if row["work_id"] == work_id:
            row["review_label"] = label
            row["reviewer"] = reviewer.strip() if label else ""
            row["noise_terms"] = noise_terms.strip() if label else ""
            changed += 1
    if not changed:
        raise KeyError(work_id)
    return changed


def save_review(table: ReviewTable, path: Path = REVIEW_CSV) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=table.header, lineterminator=table.line_terminator)
    writer.writeheader()
    writer.writerows(table.rows)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(buffer.getvalue().encode("utf-8"))
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise
