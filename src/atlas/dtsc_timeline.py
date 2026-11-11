"""Loader and validator for the curated DTSC regulatory timeline (Add-on A2 §7 Part B, EM-18).

The timeline is hand-curated in config/dtsc_timeline.yml. This module makes no network calls.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any

import yaml

CAVEAT = (
    "Listing does not by itself create requirements; "
    "Priority Product designation is a separate rulemaking."
)
REQUIRED_KEYS = (
    "id",
    "date_as_stated",
    "date_iso",
    "event",
    "source_label",
    "source_url",
    "kind",
)
TOP_LEVEL_KEYS = ("caveat", "caveat_detail", "order", "entries")
KINDS = frozenset({"workshop", "proposal", "background", "finalized", "effective", "work_plan"})
ENTRY_ID = re.compile(r"^dtsc-\d{2,}$")
DATE_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MONTH = re.compile(r"^\d{4}-\d{2}$")
FORBIDDEN_EVENT_TERMS = ("enforce", "effective in reducing", "implemented")

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "dtsc_timeline.yml"


class TimelineError(ValueError):
    """Raised when the curated timeline fails validation."""


def _sort_key(date_iso: str) -> str:
    """Return a sortable key; a month-only date sorts as the first day of that month."""
    return date_iso if DATE_DAY.match(date_iso) else f"{date_iso}-01"


def _check_date_iso(entry_id: str, value: Any) -> None:
    if not isinstance(value, str):
        raise TimelineError(f"{entry_id}: date_iso must be a string, got {value!r}")
    if DATE_DAY.match(value):
        try:
            _dt.date.fromisoformat(value)
        except ValueError as exc:
            raise TimelineError(f"{entry_id}: invalid calendar date {value!r}") from exc
    elif not DATE_MONTH.match(value):
        raise TimelineError(f"{entry_id}: date_iso must be YYYY-MM-DD or YYYY-MM, got {value!r}")
    else:
        month = int(value[5:7])
        if not 1 <= month <= 12:
            raise TimelineError(f"{entry_id}: invalid month in {value!r}")


def _check_url(entry_id: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.startswith("https://"):
        raise TimelineError(f"{entry_id}: source_url must be https or null, got {value!r}")


def _check_entry(entry: Any, index: int) -> str:
    if not isinstance(entry, dict):
        raise TimelineError(f"entry {index}: must be a mapping")
    entry_id = str(entry.get("id", f"entry {index}"))
    missing = [key for key in REQUIRED_KEYS if key not in entry]
    if missing:
        raise TimelineError(f"{entry_id}: missing keys {missing}")
    if not isinstance(entry["id"], str) or not ENTRY_ID.match(entry["id"]):
        raise TimelineError(f"{entry_id}: id must match dtsc-NN")
    for key in ("date_as_stated", "event", "source_label"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise TimelineError(f"{entry_id}: {key} must be a non-empty string")
    _check_date_iso(entry_id, entry["date_iso"])
    _check_url(entry_id, entry["source_url"])
    if entry["kind"] not in KINDS:
        raise TimelineError(f"{entry_id}: kind {entry['kind']!r} not in {sorted(KINDS)}")
    lowered = entry["event"].lower()
    for term in FORBIDDEN_EVENT_TERMS:
        if term in lowered:
            raise TimelineError(f"{entry_id}: event must not claim enforcement or implementation")
    return entry_id


def validate_timeline(data: Any) -> dict[str, Any]:
    """Validate an already-parsed timeline mapping and return it."""
    if not isinstance(data, dict):
        raise TimelineError("timeline must be a mapping")
    missing = [key for key in TOP_LEVEL_KEYS if key not in data]
    if missing:
        raise TimelineError(f"missing top-level keys {missing}")
    if data["caveat"] != CAVEAT:
        raise TimelineError("caveat must equal the required 'Always show' sentence exactly")
    if not isinstance(data["caveat_detail"], str) or not data["caveat_detail"].strip():
        raise TimelineError("caveat_detail must be a non-empty string")
    if data["order"] != "newest_first":
        raise TimelineError("order must be 'newest_first'")
    entries = data["entries"]
    if not isinstance(entries, list) or not entries:
        raise TimelineError("entries must be a non-empty list")

    seen: set[str] = set()
    previous_key: str | None = None
    for index, entry in enumerate(entries):
        entry_id = _check_entry(entry, index)
        if entry_id in seen:
            raise TimelineError(f"duplicate id {entry_id}")
        seen.add(entry_id)
        key = _sort_key(entry["date_iso"])
        if previous_key is not None and key > previous_key:
            raise TimelineError(f"{entry_id}: entries must be newest-first by date_iso")
        previous_key = key
    return data


def load_timeline(path: Path | str = DEFAULT_PATH) -> dict[str, Any]:
    """Load and validate the curated DTSC timeline YAML."""
    with Path(path).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return validate_timeline(data)
