"""Load and save owner review sheets (CSV) for the small Streamlit review apps.

Shared by ``scripts/review_institution_types_app.py`` and
``scripts/review_expert_photos_app.py``. Saving keeps the header order, the line
terminator (Excel may have rewritten the file with CRLF), and writes atomically
so a crash never leaves a half-written sheet.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ReviewSheet:
    path: Path
    header: list[str]
    rows: list[dict[str, str]]
    line_terminator: str
    key: str

    def find(self, key_value: str) -> dict[str, str]:
        for row in self.rows:
            if row[self.key] == key_value:
                return row
        raise KeyError(key_value)


def load_sheet(path: Path, *, key: str, required: tuple[str, ...] = ()) -> ReviewSheet:
    """Read a review CSV (UTF-8, optional BOM); require ``key`` and ``required`` columns."""

    raw = path.read_bytes().decode("utf-8-sig")
    terminator = "\r\n" if "\r\n" in raw else "\n"
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    header = list(reader.fieldnames or [])
    missing = [c for c in (key, *required) if c not in header]
    if missing:
        raise ValueError(f"{path}: missing column(s) {', '.join(missing)}")
    rows = [{c: (row.get(c) or "") for c in header} for row in reader]
    seen: set[str] = set()
    for row in rows:
        if row[key] in seen:
            raise ValueError(f"{path}: {key} {row[key]} is listed more than once")
        seen.add(row[key])
    return ReviewSheet(path, header, rows, terminator, key)


def save_sheet(sheet: ReviewSheet) -> None:
    """Write atomically: temp file in the same directory, then replace."""

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=sheet.header, lineterminator=sheet.line_terminator)
    writer.writeheader()
    writer.writerows(sheet.rows)
    handle, temp = tempfile.mkstemp(
        dir=sheet.path.parent, prefix=f".{sheet.path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(buffer.getvalue().encode("utf-8"))
        os.replace(temp, sheet.path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def set_fields(sheet: ReviewSheet, key_value: str, values: dict[str, str]) -> None:
    """Update one row in memory and save the sheet."""

    row = sheet.find(key_value)
    for column, value in values.items():
        if column not in sheet.header:
            raise KeyError(f"unknown column {column!r}")
        row[column] = value
    save_sheet(sheet)


def today_utc() -> str:
    return datetime.now(UTC).date().isoformat()
