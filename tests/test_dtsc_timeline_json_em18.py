"""Tests for site/data/dtsc_timeline.json (Add-on A2 §7 Part B, EM-18)."""

from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMMITTED = ROOT / "site" / "data" / "dtsc_timeline.json"
SPEC_CAVEAT = (
    "Listing does not by itself create requirements; "
    "Priority Product designation is a separate rulemaking."
)


def _builder() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module("build_dtsc_timeline_json")
    finally:
        sys.path.remove(str(SCRIPTS))


def _payload() -> dict:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def test_committed_json_is_not_stale(tmp_path: Path) -> None:
    builder = _builder()
    assert builder.main(["--check"]) == 0
    stale = tmp_path / "dtsc_timeline.json"
    stale.write_text(COMMITTED.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert builder.main(["--check", "--output", str(stale)]) == 1
    assert builder.main(["--check", "--output", str(tmp_path / "missing.json")]) == 1


def test_caveat_matches_spec_sentence() -> None:
    payload = _payload()
    assert payload["caveat"] == SPEC_CAVEAT
    assert payload["schema_version"] == "em18.v1"
    assert payload["order"] == "newest_first"
    assert payload["caveat_detail"].strip()


def test_entries_are_newest_first_and_keep_dates_verbatim() -> None:
    entries = _payload()["entries"]
    assert entries, "timeline must not be empty"
    keys = [
        e["date_iso"]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["date_iso"])
        else e["date_iso"] + "-01"
        for e in entries
    ]
    assert keys == sorted(keys, reverse=True)
    assert len({e["id"] for e in entries}) == len(entries)
    assert entries[0]["date_as_stated"] == "1 October 2026"
    for entry in entries:
        assert isinstance(entry["date_as_stated"], str) and entry["date_as_stated"].strip()
        assert set(entry) >= {
            "id",
            "date_as_stated",
            "date_iso",
            "event",
            "source_label",
            "source_url",
            "kind",
        }


def test_source_urls_are_https_or_null() -> None:
    for entry in _payload()["entries"]:
        url = entry["source_url"]
        assert url is None or url.startswith("https://"), entry["id"]


def test_no_minderoo_text() -> None:
    assert "minderoo" not in COMMITTED.read_text(encoding="utf-8").lower()
