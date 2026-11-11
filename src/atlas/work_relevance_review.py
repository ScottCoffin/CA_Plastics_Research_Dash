"""Read and write owner decisions in ``curation/work_relevance.csv`` (S11.3).

Pure-Python helpers behind the local Streamlit review app
(``scripts/review_work_relevance_app.py``). Each save rewrites the whole file
through the ``csv`` module, keeps the header, row order and line endings, and
replaces the file atomically, so untouched rows stay byte-identical. Work
details (title, abstract, authors, ...) come from the OpenAlex JSON in
``data/interim/works_raw.parquet`` and are only joined for display; they are
never written back. Same decision rules as ``atlas.grant_relevance_review``.

``assist_plastic_related`` keeps Haiku's suggestion permanently, so an owner's
choice can always be compared with it. ``plastic_related`` is the value the export
uses: the owner's choice when confirmed or changed, and Haiku's value when pending
or unsure. Files without the column are loaded with it filled from ``plastic_related``.
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.ingest.abstract_qc import misattached_abstract_ids

REVIEW_CSV = Path("curation/work_relevance.csv")
WORKS_PARQUET = Path("data/interim/works_raw.parquet")

HEADER = (
    "work_id",
    "plastic_related",
    "assist_plastic_related",
    "confidence",
    "reason",
    "reviewer",
    "reviewed_at",
    "owner_review",
)
# Pre-S11.3 layout without ``assist_plastic_related``; loaded with that column filled in.
LEGACY_HEADER = tuple(name for name in HEADER if name != "assist_plastic_related")
NOTE_MARKER = " | owner: "
VIEWS = ("Pending", "Low confidence pending", "All", "Owner-confirmed", "Owner-changed")


@dataclass
class WorkReviewTable:
    header: list[str]
    rows: list[dict[str, str]]
    line_terminator: str

    def counts(self) -> Counter[str]:
        """Rows per ``owner_review`` value."""
        return Counter(row["owner_review"] for row in self.rows)


def load_work_reviews(path: Path = REVIEW_CSV) -> WorkReviewTable:
    raw = path.read_bytes().decode("utf-8")
    terminator = "\r\n" if "\r\n" in raw else "\n"
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    fieldnames = tuple(reader.fieldnames or ())
    if fieldnames not in (HEADER, LEGACY_HEADER):
        raise ValueError(f"{path}: header must be {','.join(HEADER)}")
    rows = list(reader)
    seen: set[str] = set()
    for row in rows:
        if row["work_id"] in seen:
            raise ValueError(f"{path}: work_id {row['work_id']} is listed more than once")
        seen.add(row["work_id"])
        if fieldnames == LEGACY_HEADER:
            row["assist_plastic_related"] = row["plastic_related"]
    return WorkReviewTable(header=list(HEADER), rows=rows, line_terminator=terminator)


def save_work_reviews(table: WorkReviewTable, path: Path = REVIEW_CSV) -> None:
    """Write the table atomically: temp file in the same directory, then replace."""
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


def haiku_value(row: dict[str, str]) -> bool:
    """Haiku's suggestion, kept in ``assist_plastic_related`` and never overwritten."""
    return (row.get("assist_plastic_related") or row["plastic_related"]) == "true"


def _row(table: WorkReviewTable, work_id: str) -> dict[str, str]:
    for row in table.rows:
        if row["work_id"] == work_id:
            return row
    raise KeyError(work_id)


def _clean_note(note: str) -> str:
    # One line per row keeps the CSV greppable; csv quoting handles commas and quotes.
    return " ".join(note.split())


def record_decision(
    table: WorkReviewTable,
    work_id: str,
    plastic_related: bool | None,
    reviewer: str,
    note: str = "",
    today: date | None = None,
) -> str:
    """Record the owner's decision; ``None`` means unsure. Returns the new ``owner_review``."""
    initials = reviewer.strip()
    if not initials:
        raise ValueError("reviewer initials are required with a decision")
    row = _row(table, work_id)
    prior = haiku_value(row)  # read before plastic_related is overwritten
    row["reviewer"] = initials
    row["reviewed_at"] = (today or datetime.now(UTC).date()).isoformat()
    cleaned = _clean_note(note)
    if cleaned:
        base = row["reason"].split(NOTE_MARKER, 1)[0]
        row["reason"] = f"{base}{NOTE_MARKER}{cleaned}"
    if plastic_related is None:
        # Unsure leaves the export on Haiku's value; the owner's earlier choice is discarded.
        row["plastic_related"] = "true" if prior else "false"
        row["owner_review"] = "unsure"
    else:
        row["plastic_related"] = "true" if plastic_related else "false"
        row["owner_review"] = "confirmed" if plastic_related == prior else "changed"
    return row["owner_review"]


def reset_to_pending(table: WorkReviewTable, work_id: str) -> None:
    """Return a row to the pending queue with Haiku's value restored."""
    row = _row(table, work_id)
    row["plastic_related"] = "true" if haiku_value(row) else "false"
    row["owner_review"] = "pending"


def _abstract(inverted: Any) -> str:
    if not isinstance(inverted, dict):
        return ""
    positions = sorted((p, word) for word, ps in inverted.items() for p in ps)
    return " ".join(word for _, word in positions)


def load_work_details(path: Path = WORKS_PARQUET) -> dict[str, dict[str, Any]]:
    """Work details keyed by ``work_id``; a missing or unusable file gives an empty dict."""
    if not Path(path).exists():
        return {}
    names = pq.read_schema(path).names
    if "openalex_id" not in names or "raw_json" not in names:
        return {}
    details: dict[str, dict[str, Any]] = {}
    for record in pq.read_table(path, columns=["openalex_id", "raw_json"]).to_pylist():
        work = json.loads(record["raw_json"] or "{}")
        authorships = work.get("authorships") or []
        authors = [(a.get("author") or {}).get("display_name") or "" for a in authorships]
        institutions = sorted(
            {
                inst.get("display_name") or ""
                for a in authorships
                for inst in a.get("institutions") or []
            }
            - {""}
        )
        source = (work.get("primary_location") or {}).get("source") or {}
        details[str(record["openalex_id"])] = {
            "title": work.get("display_name") or work.get("title") or "",
            "abstract": _abstract(work.get("abstract_inverted_index")),
            "year": work.get("publication_year"),
            "type": work.get("type") or "",
            "journal": source.get("display_name") or "",
            "doi": work.get("doi") or "",
            "url": work.get("id") or "",
            "authors": "; ".join(authors[:12]) + (" ..." if len(authors) > 12 else ""),
            "institutions": "; ".join(institutions[:12]),
            "cited_by_count": work.get("cited_by_count"),
        }
    # Hide abstracts OpenAlex attached to unrelated works (atlas.ingest.abstract_qc).
    rows = [{"work_id": key, **value} for key, value in details.items()]
    for work_id in misattached_abstract_ids(rows):
        details[work_id]["abstract"] = ""
        details[work_id]["abstract_note"] = (
            "OpenAlex abstract hidden: the same text is attached to several unrelated works."
        )
    return details


def merged_view(
    rows: list[dict[str, str]], details: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """CSV rows joined to their work details; CSV fields win on any name clash."""
    return [{**details.get(row["work_id"], {}), **row} for row in rows]


def in_view(item: dict[str, Any], view: str, search: str = "") -> bool:
    state = item["owner_review"]
    if view == "Pending" and state != "pending":
        return False
    if view == "Low confidence pending" and (state != "pending" or item["confidence"] != "low"):
        return False
    if view == "Owner-confirmed" and state != "confirmed":
        return False
    if view == "Owner-changed" and state != "changed":
        return False
    needle = search.strip().lower()
    if not needle:
        return True
    hay = " ".join(
        str(item.get(field) or "")
        for field in ("title", "abstract", "authors", "institutions", "journal", "work_id")
    )
    return needle in hay.lower()


def select_view(items: list[dict[str, Any]], view: str, search: str = "") -> list[dict[str, Any]]:
    """Items in the view, low-confidence first, then by ``work_id``."""
    shown = [item for item in items if in_view(item, view, search)]
    return sorted(shown, key=lambda item: (item["confidence"] != "low", item["work_id"]))


NO_ASSIST_REASON = "owner (no assist call)"


def record_owner_decision(
    table: WorkReviewTable,
    work_id: str,
    plastic_related: bool,
    reviewer: str,
    note: str = "",
    today: date | None = None,
) -> str:
    """Record a decision, appending a new row when the work has no Haiku call.

    A new row has ``assist_plastic_related`` and ``confidence`` empty and
    ``owner_review`` confirmed, so the export uses the owner's choice. Existing rows go
    through ``record_decision`` unchanged. Unsure is not supported for new rows (there is
    nothing to fall back to); the caller should skip the work instead.
    """
    if any(row["work_id"] == work_id for row in table.rows):
        return record_decision(table, work_id, plastic_related, reviewer, note, today)
    initials = reviewer.strip()
    if not initials:
        raise ValueError("reviewer initials are required with a decision")
    cleaned = _clean_note(note)
    table.rows.append(
        {
            "work_id": work_id,
            "plastic_related": "true" if plastic_related else "false",
            "assist_plastic_related": "",
            "confidence": "",
            "reason": NO_ASSIST_REASON + (f"{NOTE_MARKER}{cleaned}" if cleaned else ""),
            "reviewer": initials,
            "reviewed_at": (today or datetime.now(UTC).date()).isoformat(),
            "owner_review": "confirmed",
        }
    )
    return "confirmed"
