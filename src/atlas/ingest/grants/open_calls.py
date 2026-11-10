"""California Grants Portal open-calls panel (S8.9).

The portal lists grants *offered* (funding calls), not awards.  This module reads
its public-domain CSV, keeps rows that are open and plastic-related, and writes the
``site/data/open_calls.json`` payload used by the Funding tab.

Open means status ``active`` or ``forecasted`` and an application deadline that is
today or later (or ``Ongoing``).  Plastic-related means the S2.3 classifier
(``classify_plastic_text`` with ``config/queries.yml``) matches, or one of
``FUNDING_TERMS`` appears.  Exclusions in ``queries.yml`` override both paths.

``FUNDING_TERMS`` are keyword-only. Bare ``recycl`` and ``packaging`` were dropped
because every live match was non-plastic (water recycling, loans). See
``docs/api_notes/ca_grants_portal.md``.

A failed fetch or an unusable CSV yields status ``deferred``; the caller must then
leave the existing JSON untouched.
"""

from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from atlas.nlp.labels import classify_plastic_text

SOURCE_URL = (
    "https://publish.data.ca.gov/dataset/e1b1c799-cdd4-4219-af6d-93b79747fffb/"
    "resource/111c8c88-21f6-453c-ae2c-b4785a0624f5/download/california-grants-portal-data.csv"
)
DATASET_URL = "https://data.ca.gov/dataset/california-grants-portal"
LICENCE = "Other (Public Domain)"
OPEN_STATUSES = ("active", "forecasted")
ONGOING = "ongoing"
FUNDING_TERMS = (
    "marine debris",
    "litter",
    "trash",
    "plastic pollution",
    "microplastic",
    "single-use",
    "packaging waste",
    "plastic recycl",
    "plastic waste",
)  # bare "recycl"/"packaging" dropped 2026-11-10: all live hits were water recycling etc.
REQUIRED_COLUMNS = (
    "PortalID",
    "Status",
    "AgencyDept",
    "Title",
    "Purpose",
    "Description",
    "Categories",
    "ApplicationDeadline",
    "GrantURL",
    "EstAvailFunds",
)
TEXT_COLUMNS = ("Title", "Purpose", "Description", "Categories")
_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


class FetchError(RuntimeError):
    """The CSV could not be downloaded."""


def decode_csv(payload: bytes) -> str:
    """Decode UTF-8 (with BOM allowed); the portal sometimes ships cp1252 bytes."""

    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        return payload.decode("cp1252", errors="replace")


def fetch_csv(
    url: str = SOURCE_URL,
    *,
    timeout: float = 120,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> str:
    """Download the CSV and return its decoded text."""

    request = urllib.request.Request(url, headers={"User-Agent": "CA-Plastics-Research-Atlas/S8.9"})
    try:
        with opener(request, timeout=timeout) as response:
            payload = response.read()
    except (OSError, ValueError) as exc:  # URLError and HTTPError are OSError subclasses
        raise FetchError(f"fetch failed: {type(exc).__name__}") from exc
    return decode_csv(payload)


def parse_csv(text: str) -> list[dict[str, str]]:
    """Parse CSV text and require the columns this module uses."""

    reader = csv.DictReader(io.StringIO(text, newline=""))
    fieldnames = reader.fieldnames or []
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"CSV is missing columns: {', '.join(missing)}")
    return [dict(row) for row in reader]


def _clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalise_deadline(value: object) -> str | None:
    """Return ``"ongoing"``, an ISO ``YYYY-MM-DD`` date, or ``None`` when unusable."""

    text = _clean(value)
    if text.casefold() == ONGOING:
        return ONGOING
    match = _DATE_PATTERN.match(text)
    if match is None:
        return None
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return None
    return match.group(1)


def is_open(row: Mapping[str, Any], today: date) -> bool:
    """Status must be open and the deadline today or later (or ongoing)."""

    if _clean(row.get("Status")).casefold() not in OPEN_STATUSES:
        return False
    deadline = normalise_deadline(row.get("ApplicationDeadline"))
    if deadline is None:
        return False
    return deadline == ONGOING or deadline >= today.isoformat()


def is_plastic(row: Mapping[str, Any], query_config: Mapping[str, Any]) -> bool:
    """Classifier match or funding-language keyword, unless a query exclusion applies."""

    text = " ".join(_clean(row.get(column)) for column in TEXT_COLUMNS)
    decision = classify_plastic_text(text, query_config)
    if any(hit.startswith("exclude:") for hit in decision.hits):
        return False
    if decision.related:
        return True
    lowered = text.casefold()
    return any(term in lowered for term in FUNDING_TERMS)


def build_payload(
    rows: Sequence[Mapping[str, Any]],
    *,
    query_config: Mapping[str, Any],
    today: date,
    generated_at: str,
    source_url: str = SOURCE_URL,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Select open plastic-related calls and return (payload, counts)."""

    open_rows = [row for row in rows if is_open(row, today)]
    selected = [row for row in open_rows if is_plastic(row, query_config)]
    calls = []
    for row in selected:
        calls.append(
            {
                "portal_id": _clean(row.get("PortalID")),
                "title": _clean(row.get("Title")),
                "agency": _clean(row.get("AgencyDept")),
                "deadline": normalise_deadline(row.get("ApplicationDeadline")),
                "status": _clean(row.get("Status")).casefold(),
                "url": _clean(row.get("GrantURL")) or None,
                "categories": [
                    c.strip() for c in _clean(row.get("Categories")).split(";") if c.strip()
                ],
                "est_funding": _clean(row.get("EstAvailFunds")) or None,
            }
        )
    # Dated calls first by deadline, then ongoing calls; ties broken by title and ID.
    calls.sort(
        key=lambda c: (
            c["deadline"] == ONGOING,
            "" if c["deadline"] == ONGOING else c["deadline"],
            c["title"].casefold(),
            c["portal_id"],
        )
    )
    payload = {
        "generated_at": generated_at,
        "source_url": source_url,
        "licence": LICENCE,
        "calls": calls,
    }
    counts = {"rows": len(rows), "open": len(open_rows), "plastic_open": len(calls)}
    return payload, counts


def write_payload(payload: Mapping[str, Any], path: Path) -> None:
    """Write deterministic JSON (sorted keys, LF newlines) via a temporary file."""

    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def refresh(
    *,
    output: Path,
    query_config: Mapping[str, Any],
    today: date,
    generated_at: str,
    csv_path: Path | None = None,
    fetch: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Build the payload from ``csv_path`` or a fetch.  Defers (no write) on failure."""

    try:
        if csv_path is not None:
            text = decode_csv(csv_path.read_bytes())
        else:
            text = (fetch or fetch_csv)()
        rows = parse_csv(text)
    except (FetchError, ValueError, csv.Error) as exc:
        return {"status": "deferred", "reason": str(exc), "output": str(output)}
    payload, counts = build_payload(
        rows, query_config=query_config, today=today, generated_at=generated_at
    )
    write_payload(payload, output)
    return {"status": "written", "output": str(output), **counts}
