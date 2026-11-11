"""Read and write owner decisions in ``curation/grant_relevance.csv`` (S11.3).

Pure-Python helpers behind the local Streamlit review app
(``scripts/review_grant_relevance_app.py``). Each save rewrites the whole file
through the ``csv`` module, keeps the header, row order and line endings, and
replaces the file atomically, so untouched rows stay byte-identical. Grant
details (title, abstract, PIs, ...) come from the local
``data/interim/grants/grants_merged.parquet`` and are only joined for display;
they are never written back.

``assist_plastic_related`` keeps Haiku's suggestion permanently, so an owner's
choice can always be compared with it. ``plastic_related`` is the value the export
uses: the owner's choice when confirmed or changed, and Haiku's value when pending
or unsure. Files without the column are loaded with it filled from ``plastic_related``.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

REVIEW_CSV = Path("curation/grant_relevance.csv")
GRANTS_PARQUET = Path("data/interim/grants/grants_merged.parquet")
HEADER = (
    "grant_key",
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
DETAIL_FIELDS = (
    "grant_key",
    "source",
    "source_award_id",
    "title",
    "abstract",
    "pi_names",
    "org",
    "org_state",
    "start",
    "end",
    "amount",
    "currency",
    "funder",
    "program",
    "url",
)
NOTE_MARKER = " | owner: "
VIEWS = ("Pending", "Low confidence pending", "All", "Owner-confirmed", "Owner-changed")


@dataclass
class GrantReviewTable:
    header: list[str]
    rows: list[dict[str, str]]
    line_terminator: str

    def counts(self) -> Counter[str]:
        """Rows per ``owner_review`` value."""
        return Counter(row["owner_review"] for row in self.rows)


def load_grant_reviews(path: Path = REVIEW_CSV) -> GrantReviewTable:
    raw = path.read_bytes().decode("utf-8")
    terminator = "\r\n" if "\r\n" in raw else "\n"
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    fieldnames = tuple(reader.fieldnames or ())
    if fieldnames not in (HEADER, LEGACY_HEADER):
        raise ValueError(f"{path}: header must be {','.join(HEADER)}")
    rows = list(reader)
    seen: set[str] = set()
    for row in rows:
        if row["grant_key"] in seen:
            raise ValueError(f"{path}: grant_key {row['grant_key']} is listed more than once")
        seen.add(row["grant_key"])
        if fieldnames == LEGACY_HEADER:
            row["assist_plastic_related"] = row["plastic_related"]
    return GrantReviewTable(header=list(HEADER), rows=rows, line_terminator=terminator)


def save_grant_reviews(table: GrantReviewTable, path: Path = REVIEW_CSV) -> None:
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


def _row(table: GrantReviewTable, grant_key: str) -> dict[str, str]:
    for row in table.rows:
        if row["grant_key"] == grant_key:
            return row
    raise KeyError(grant_key)


def _clean_note(note: str) -> str:
    # One line per row keeps the CSV greppable; csv quoting handles commas and quotes.
    return " ".join(note.split())


def record_decision(
    table: GrantReviewTable,
    grant_key: str,
    plastic_related: bool | None,
    reviewer: str,
    note: str = "",
    today: date | None = None,
) -> str:
    """Record the owner's decision; ``None`` means unsure. Returns the new ``owner_review``."""
    initials = reviewer.strip()
    if not initials:
        raise ValueError("reviewer initials are required with a decision")
    row = _row(table, grant_key)
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


def reset_to_pending(table: GrantReviewTable, grant_key: str) -> None:
    """Return a row to the pending queue with Haiku's value restored."""
    row = _row(table, grant_key)
    row["plastic_related"] = "true" if haiku_value(row) else "false"
    row["owner_review"] = "pending"


def load_grant_details(path: Path = GRANTS_PARQUET) -> dict[str, dict[str, Any]]:
    """Grant details keyed by ``grant_key``; a missing or unusable file gives an empty dict."""
    if not Path(path).exists():
        return {}
    names = pq.read_schema(path).names
    if "grant_key" not in names:
        return {}
    columns = [name for name in DETAIL_FIELDS if name in names]
    details: dict[str, dict[str, Any]] = {}
    for record in pq.read_table(path, columns=columns).to_pylist():
        details.setdefault(str(record["grant_key"]), record)
    return details


def merged_view(
    rows: list[dict[str, str]], details: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """CSV rows joined to their grant details; CSV fields win on any name clash."""
    return [{**details.get(row["grant_key"], {}), **row} for row in rows]


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
        for field in ("title", "abstract", "org", "pi_names", "grant_key")
    )
    return needle in hay.lower()


def select_view(items: list[dict[str, Any]], view: str, search: str = "") -> list[dict[str, Any]]:
    """Items in the view, low-confidence first, then by ``grant_key``."""
    shown = [item for item in items if in_view(item, view, search)]
    return sorted(shown, key=lambda item: (item["confidence"] != "low", item["grant_key"]))


def format_years(start: Any, end: Any) -> str:
    first = str(start)[:4] if start else ""
    last = str(end)[:4] if end else ""
    if first and last:
        return f"{first}–{last}"
    return first or last


def format_amount(amount: Any, currency: Any) -> str:
    if amount is None or amount == "":
        return ""
    try:
        text = f"{float(amount):,.0f}"
    except (TypeError, ValueError):
        text = str(amount)
    return f"{text} {currency}".strip() if currency else text
