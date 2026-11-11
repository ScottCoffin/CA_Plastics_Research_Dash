from __future__ import annotations

from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build.curation import load_grant_relevance
from atlas.grant_relevance_review import (
    format_amount,
    format_years,
    haiku_value,
    load_grant_details,
    load_grant_reviews,
    merged_view,
    record_decision,
    reset_to_pending,
    save_grant_reviews,
    select_view,
)

HEADER = (
    "grant_key,plastic_related,assist_plastic_related,confidence,reason,reviewer,"
    "reviewed_at,owner_review"
)
LEGACY_HEADER = "grant_key,plastic_related,confidence,reason,reviewer,reviewed_at,owner_review"
FIXTURE_ROWS = [
    "aaa1,true,true,high,Plastics replacement,claude-haiku-assist,2026-11-10,pending",
    'bbb2,false,false,low,"State water planning, microplastic scoping",'
    "claude-haiku-assist,2026-11-10,pending",
    "ccc3,true,true,low,Marine debris cleanup,claude-haiku-assist,2026-11-10,confirmed",
    # Owner changed Haiku's true to false.
    "ddd4,false,true,high,Air quality,claude-haiku-assist,2026-11-10,changed",
    "eee5,true,true,high,Seafood safety,claude-haiku-assist,2026-11-10,pending",
]
LEGACY_ROWS = [
    "aaa1,true,high,Plastics replacement,claude-haiku-assist,2026-11-10,pending",
    "bbb2,false,low,Water planning,claude-haiku-assist,2026-11-10,pending",
]
TODAY = date(2026, 11, 11)


@pytest.fixture()
def csv_copy(tmp_path: Path) -> Path:
    path = tmp_path / "grant_relevance.csv"
    path.write_text("\n".join([HEADER, *FIXTURE_ROWS]) + "\n", encoding="utf-8", newline="")
    return path


def _row(path: Path, grant_key: str) -> dict[str, str]:
    table = load_grant_reviews(path)
    return next(row for row in table.rows if row["grant_key"] == grant_key)


def test_unchanged_save_is_byte_identical(csv_copy: Path) -> None:
    before = csv_copy.read_bytes()
    save_grant_reviews(load_grant_reviews(csv_copy), csv_copy)
    assert csv_copy.read_bytes() == before


def test_decision_rewrites_only_its_own_line(csv_copy: Path) -> None:
    before = csv_copy.read_text(encoding="utf-8").splitlines()
    table = load_grant_reviews(csv_copy)
    record_decision(table, "aaa1", True, " SC ", today=TODAY)
    save_grant_reviews(table, csv_copy)
    after = csv_copy.read_text(encoding="utf-8").splitlines()
    assert after[0] == before[0]
    assert after[2:] == before[2:]
    assert after[1] == "aaa1,true,true,high,Plastics replacement,SC,2026-11-11,confirmed"


def test_confirmed_versus_changed_compares_with_assist_column(csv_copy: Path) -> None:
    table = load_grant_reviews(csv_copy)
    assert record_decision(table, "aaa1", False, "SC", today=TODAY) == "changed"
    assert record_decision(table, "aaa1", True, "SC", today=TODAY) == "confirmed"
    assert record_decision(table, "bbb2", False, "SC", today=TODAY) == "confirmed"
    # ddd4 was changed away from Haiku's true; choosing true again matches Haiku.
    assert record_decision(table, "ddd4", True, "SC", today=TODAY) == "confirmed"
    assert record_decision(table, "ddd4", False, "SC", today=TODAY) == "changed"
    save_grant_reviews(table, csv_copy)
    assert _row(csv_copy, "aaa1")["plastic_related"] == "true"
    assert _row(csv_copy, "aaa1")["assist_plastic_related"] == "true"
    assert _row(csv_copy, "ddd4")["plastic_related"] == "false"
    assert _row(csv_copy, "ddd4")["owner_review"] == "changed"


def test_haiku_value_reads_the_assist_column() -> None:
    row = {"plastic_related": "false", "assist_plastic_related": "true", "owner_review": "changed"}
    assert haiku_value(row) is True
    assert haiku_value({"plastic_related": "true", "owner_review": "pending"}) is True


def test_unsure_restores_haiku_value(csv_copy: Path) -> None:
    table = load_grant_reviews(csv_copy)
    assert record_decision(table, "eee5", None, "SC", today=TODAY) == "unsure"
    # ddd4 was changed to false; skipping it puts Haiku's true back for the export.
    assert record_decision(table, "ddd4", None, "SC", today=TODAY) == "unsure"
    save_grant_reviews(table, csv_copy)
    row = _row(csv_copy, "eee5")
    assert row["owner_review"] == "unsure"
    assert row["plastic_related"] == "true"
    assert row["reviewer"] == "SC"
    ddd4 = _row(csv_copy, "ddd4")
    assert ddd4["plastic_related"] == "true"
    assert ddd4["assist_plastic_related"] == "true"


def test_reset_restores_haiku_value(csv_copy: Path) -> None:
    table = load_grant_reviews(csv_copy)
    reset_to_pending(table, "ddd4")
    reset_to_pending(table, "ccc3")
    save_grant_reviews(table, csv_copy)
    changed = _row(csv_copy, "ddd4")
    assert changed["owner_review"] == "pending"
    assert changed["plastic_related"] == "true"
    confirmed = _row(csv_copy, "ccc3")
    assert confirmed["owner_review"] == "pending"
    assert confirmed["plastic_related"] == "true"


def test_note_is_quoted_and_not_stacked(csv_copy: Path) -> None:
    table = load_grant_reviews(csv_copy)
    note = 'check, "scope"\nagain'
    record_decision(table, "bbb2", False, "SC", note=note, today=TODAY)
    save_grant_reviews(table, csv_copy)
    reason = _row(csv_copy, "bbb2")["reason"]
    assert reason == 'State water planning, microplastic scoping | owner: check, "scope" again'
    lines = csv_copy.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 + len(FIXTURE_ROWS)
    assert lines[2].startswith('bbb2,false,false,low,"State water planning, microplastic scoping')

    table = load_grant_reviews(csv_copy)
    record_decision(table, "bbb2", False, "SC", note="second", today=TODAY)
    assert table.rows[1]["reason"] == "State water planning, microplastic scoping | owner: second"


def test_legacy_seven_column_file_gains_assist_column(tmp_path: Path) -> None:
    path = tmp_path / "legacy.csv"
    path.write_text("\n".join([LEGACY_HEADER, *LEGACY_ROWS]) + "\n", encoding="utf-8")
    table = load_grant_reviews(path)
    assert [row["assist_plastic_related"] for row in table.rows] == ["true", "false"]
    save_grant_reviews(table, path)
    assert path.read_text(encoding="utf-8").splitlines()[0] == HEADER
    assert load_grant_relevance(path) == {"aaa1": True, "bbb2": False}


def test_missing_parquet_is_tolerated(csv_copy: Path, tmp_path: Path) -> None:
    details = load_grant_details(tmp_path / "missing.parquet")
    assert details == {}
    table = load_grant_reviews(csv_copy)
    items = merged_view(table.rows, details)
    assert [item["grant_key"] for item in items] == [row["grant_key"] for row in table.rows]
    assert items[0]["reason"] == "Plastics replacement"


def test_parquet_details_join_and_csv_fields_win(csv_copy: Path, tmp_path: Path) -> None:
    grants = tmp_path / "grants_merged.parquet"
    pq.write_table(
        pa.table(
            {
                "grant_key": ["aaa1", "zzz9"],
                "title": ["Plastic reuse grant", "Unrelated"],
                "abstract": ["Abstract text", None],
                "reason": ["ignored", "ignored"],
                "start": ["2019-01-01", None],
                "end": ["2021-12-31", None],
                "amount": [150000.0, None],
                "currency": ["USD", None],
            }
        ),
        grants,
    )
    details = load_grant_details(grants)
    assert set(details) == {"aaa1", "zzz9"}
    items = merged_view(load_grant_reviews(csv_copy).rows, details)
    first = items[0]
    assert first["title"] == "Plastic reuse grant"
    assert first["reason"] == "Plastics replacement"
    assert format_years(first["start"], first["end"]) == "2019–2021"
    assert format_amount(first["amount"], first["currency"]) == "150,000 USD"
    assert format_years(None, None) == ""


def test_output_loads_with_curation_loader(csv_copy: Path) -> None:
    table = load_grant_reviews(csv_copy)
    record_decision(table, "aaa1", False, "SC", today=TODAY)
    record_decision(table, "eee5", None, "SC", today=TODAY)
    save_grant_reviews(table, csv_copy)
    assert load_grant_relevance(csv_copy) == {
        "aaa1": False,
        "bbb2": False,
        "ccc3": True,
        "ddd4": False,
        "eee5": True,
    }


def test_initials_and_keys_are_validated(csv_copy: Path) -> None:
    table = load_grant_reviews(csv_copy)
    with pytest.raises(ValueError, match="initials"):
        record_decision(table, "aaa1", True, "   ")
    with pytest.raises(KeyError):
        record_decision(table, "nope", True, "SC")
    with pytest.raises(KeyError):
        reset_to_pending(table, "nope")


def test_load_rejects_wrong_header_and_duplicates(tmp_path: Path) -> None:
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("grant_key,plastic_related\naaa1,true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        load_grant_reviews(wrong)
    duplicate = tmp_path / "duplicate.csv"
    duplicate.write_text("\n".join([HEADER, FIXTURE_ROWS[0], FIXTURE_ROWS[0]]) + "\n")
    with pytest.raises(ValueError, match="more than once"):
        load_grant_reviews(duplicate)


def test_views_sort_low_confidence_first_and_search(csv_copy: Path, tmp_path: Path) -> None:
    grants = tmp_path / "grants_merged.parquet"
    pq.write_table(
        pa.table(
            {
                "grant_key": ["aaa1", "bbb2", "ccc3", "ddd4", "eee5"],
                "title": ["Plastic reuse", "Water planning", "Marine debris", "Air", "Seafood"],
                "abstract": [None, None, None, None, "Mercury in fish"],
                "org": [None, "State Water Board", None, None, None],
                "pi_names": [None, None, None, None, None],
            }
        ),
        grants,
    )
    items = merged_view(load_grant_reviews(csv_copy).rows, load_grant_details(grants))
    pending = [item["grant_key"] for item in select_view(items, "Pending")]
    assert pending == ["bbb2", "aaa1", "eee5"]
    low_pending = [item["grant_key"] for item in select_view(items, "Low confidence pending")]
    assert low_pending == ["bbb2"]
    assert [item["grant_key"] for item in select_view(items, "Owner-confirmed")] == ["ccc3"]
    assert [item["grant_key"] for item in select_view(items, "Owner-changed")] == ["ddd4"]
    assert len(select_view(items, "All")) == 5
    assert [item["grant_key"] for item in select_view(items, "All", "marine")] == ["ccc3"]
    assert [item["grant_key"] for item in select_view(items, "All", "STATE WATER")] == ["bbb2"]
    assert [item["grant_key"] for item in select_view(items, "All", "mercury")] == ["eee5"]
