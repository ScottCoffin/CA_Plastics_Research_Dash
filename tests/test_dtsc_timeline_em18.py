"""Unit tests for the curated DTSC regulatory timeline loader (Add-on A2 §7 Part B, EM-18)."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.dtsc_timeline import (  # noqa: E402
    CAVEAT,
    DEFAULT_PATH,
    TimelineError,
    load_timeline,
    validate_timeline,
)


def _base() -> dict:
    with DEFAULT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "timeline.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def test_curated_file_loads_and_has_ten_entries():
    data = load_timeline(DEFAULT_PATH)
    assert len(data["entries"]) == 10
    assert data["order"] == "newest_first"


def test_caveat_is_exact_sentence():
    data = load_timeline(DEFAULT_PATH)
    assert data["caveat"] == CAVEAT
    assert CAVEAT == (
        "Listing does not by itself create requirements; "
        "Priority Product designation is a separate rulemaking."
    )
    assert "three exceptions" in data["caveat_detail"]


def test_nov_dec_jan_rows_present_and_dates_as_stated():
    by_id = {e["id"]: e for e in load_timeline(DEFAULT_PATH)["entries"]}
    assert by_id["dtsc-06"]["date_as_stated"] == "November 2025"
    assert by_id["dtsc-06"]["date_iso"] == "2025-11"
    assert by_id["dtsc-05"]["date_as_stated"] == "December 2025"
    assert by_id["dtsc-04"]["date_as_stated"] == "January 2026"
    assert by_id["dtsc-10"]["date_as_stated"] == "June 27, 2023"
    assert by_id["dtsc-10"]["date_iso"] == "2023-06-27"


def test_work_plan_entries_have_no_url():
    for entry in load_timeline(DEFAULT_PATH)["entries"]:
        if entry["kind"] == "work_plan":
            assert entry["source_url"] is None


def test_every_url_is_https_or_null():
    for entry in load_timeline(DEFAULT_PATH)["entries"]:
        url = entry["source_url"]
        assert url is None or url.startswith("https://")


def test_missing_top_level_key_rejected(tmp_path):
    data = _base()
    del data["caveat_detail"]
    with pytest.raises(TimelineError, match="missing top-level"):
        load_timeline(_write(tmp_path, data))


def test_caveat_must_match_exactly(tmp_path):
    data = _base()
    data["caveat"] = CAVEAT.rstrip(".")
    with pytest.raises(TimelineError, match="caveat"):
        load_timeline(_write(tmp_path, data))


def test_missing_entry_key_rejected(tmp_path):
    data = _base()
    del data["entries"][0]["source_label"]
    with pytest.raises(TimelineError, match="missing keys"):
        load_timeline(_write(tmp_path, data))


def test_duplicate_id_rejected(tmp_path):
    data = _base()
    data["entries"][1]["id"] = data["entries"][0]["id"]
    with pytest.raises(TimelineError, match="duplicate id"):
        load_timeline(_write(tmp_path, data))


@pytest.mark.parametrize("bad", ["2026-02-30", "2026-13", "June 2026", "2026/06/18"])
def test_bad_date_iso_rejected(tmp_path, bad):
    data = _base()
    data["entries"][2]["date_iso"] = bad
    with pytest.raises(TimelineError, match="date_iso|calendar|month"):
        load_timeline(_write(tmp_path, data))


def test_http_url_rejected(tmp_path):
    data = _base()
    data["entries"][0]["source_url"] = "http://dtsc.ca.gov/scp/"
    with pytest.raises(TimelineError, match="https"):
        load_timeline(_write(tmp_path, data))


def test_out_of_order_entries_rejected(tmp_path):
    data = _base()
    entries = data["entries"]
    entries[0], entries[1] = entries[1], entries[0]
    with pytest.raises(TimelineError, match="newest-first"):
        load_timeline(_write(tmp_path, data))


def test_month_only_sorts_as_first_of_month():
    # dtsc-05 is "2025-12" (sorts as 2025-12-01); dtsc-06 (index 5) is "2025-11".
    # Moving dtsc-06 to a December day after the December row is out of order.
    data = copy.deepcopy(_base())
    data["entries"][5]["date_iso"] = "2025-12-01"
    validate_timeline(data)
    data["entries"][5]["date_iso"] = "2025-12-02"
    with pytest.raises(TimelineError, match="newest-first"):
        validate_timeline(data)


@pytest.mark.parametrize(
    "phrase", ["enforce", "Enforcement", "effective in reducing", "implemented"]
)
def test_event_must_not_claim_enforcement(tmp_path, phrase):
    data = _base()
    data["entries"][3]["event"] = f"Comments; DTSC says this will be {phrase} later."
    with pytest.raises(TimelineError, match="enforcement or implementation"):
        load_timeline(_write(tmp_path, data))


def test_unknown_kind_rejected(tmp_path):
    data = _base()
    data["entries"][0]["kind"] = "rule"
    with pytest.raises(TimelineError, match="kind"):
        load_timeline(_write(tmp_path, data))
