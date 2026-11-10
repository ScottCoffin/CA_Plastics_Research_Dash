"""Tests for the S8.10 grants export: mapping, funder type, amount basis, aggregates, privacy."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build import grants_export as ge
from atlas.ingest.grants.schema import GRANT_SCHEMA

GENERATED = "2026-11-09T00:00:00Z"
SECRET = "SYNTHETIC SECRET ABSTRACT TEXT"


def _grant(**overrides: object) -> dict:
    base: dict = {
        "grant_key": "0000000000000001",
        "source": "nih_reporter",
        "source_award_id": "SYN-1",
        "title": "Synthetic microplastic study",
        "abstract": SECRET,
        "pi_names": ["Ada Lovelace", "Grace Hopper", "Alan Turing", "Extra Person"],
        "org": "Synthetic University",
        "org_ror": None,
        "org_state": "CA",
        "start": date(2024, 10, 1),
        "end": date(2026, 9, 30),
        "amount": 100000.456,
        "currency": "USD",
        "funder": "NIH",
        "program": "NIEHS",
        "funder_chain": ["NIH", "NIEHS"],
        "url": "https://example.test/award/1",
        "plastic_related": True,
        "domain_tags": ["air"],
        "ca_led": True,
        "ca_sampling_flag": None,
    }
    base.update(overrides)
    return base


def _synthetic_rows() -> list[dict]:
    return [
        _grant(),
        _grant(
            grant_key="0000000000000002",
            source="nsf_awards",
            source_award_id="SYN-2",
            org="Other Institute",
            org_state="NY",
            start=date(2024, 3, 1),
            amount=50000.0,
            funder="NSF",
            program="EnvE",
            funder_chain=["NSF"],
            ca_led=False,
            plastic_related=None,
            domain_tags=[],
        ),
        _grant(
            grant_key="0000000000000003",
            source="ca_sea_grant",
            source_award_id="SYN-3",
            org="Synthetic CSU Campus",
            org_state="CA",
            start=date(2025, 7, 1),
            amount=None,
            currency=None,
            funder="California Ocean Protection Council (OPC); NOAA",
            program="Healthy Coastal Ecosystems",
            funder_chain=["California Ocean Protection Council", "California Sea Grant"],
            plastic_related=False,
            domain_tags=["air", "wastewater_and_treatment"],
        ),
        _grant(
            grant_key="0000000000000004",
            source="opc_council",
            source_award_id="SYN-4",
            org=None,
            org_state=None,
            start=None,
            end=None,
            amount=250000.0,
            funder="California Ocean Protection Council",
            program="Council approval",
            funder_chain=["California Ocean Protection Council"],
            ca_led=None,
        ),
        _grant(
            grant_key="0000000000000005",
            source="usaspending",
            source_award_id="SYN-5",
            org="Synthetic Company",
            org_state=None,
            start=date(2024, 1, 15),
            amount=7000.0,
            funder="Environmental Protection Agency",
            program="EPA",
            funder_chain=["Environmental Protection Agency", "EPA Office"],
            pi_names=[],
            ca_led=None,
        ),
        _grant(
            grant_key="0000000000000006",
            source="zz_unknown_feed",
            source_award_id="SYN-6",
            org="Synthetic University",
            start=date(2023, 6, 1),
            amount=10.0,
            funder="Mystery Fund",
            funder_chain=["Mystery Fund"],
        ),
    ]


INSTITUTIONS = [
    {"display_name": "Synthetic University", "ror_id": "https://ror.org/0abc", "atlas_type": "UC"},
    {"display_name": "Other Institute", "ror_id": None, "atlas_type": "nonprofit/NGO"},
    {"display_name": "Synthetic CSU Campus", "ror_id": None, "atlas_type": "CSU"},
    {"display_name": "Synthetic Company", "ror_id": None, "atlas_type": "company"},
    {"display_name": "Ambiguous Lab", "ror_id": None, "atlas_type": "company"},
    {"display_name": "Ambiguous Lab", "ror_id": None, "atlas_type": "private"},
]


def _payload(rows: list[dict] | None = None) -> dict:
    return ge.build_payload(
        _synthetic_rows() if rows is None else rows,
        INSTITUTIONS,
        generated_at=GENERATED,
    )


def _write_merged(path: Path, rows: list[dict]) -> Path:
    table = pa.Table.from_pylist(rows, schema=GRANT_SCHEMA)
    pq.write_table(table, path)
    return path


def test_funder_type_by_source() -> None:
    assert ge.funder_type("nih_reporter") == "federal"
    assert ge.funder_type("nsf_awards") == "federal"
    assert ge.funder_type("usaspending") == "federal"
    assert ge.funder_type("ca_sea_grant") == "state"
    assert ge.funder_type("opc_council") == "state"
    assert ge.funder_type("scc_board") == "state"
    assert ge.funder_type("zz_unknown_feed") == "other"


def test_fiscal_year_conventions() -> None:
    # Federal fiscal year runs October to September and takes the ending year.
    assert ge.fiscal_year(date(2024, 10, 1), "nih_reporter") == 2025
    assert ge.fiscal_year(date(2024, 9, 30), "nih_reporter") == 2024
    # State fiscal year runs July to June.
    assert ge.fiscal_year(date(2024, 7, 1), "opc_council") == 2025
    assert ge.fiscal_year(date(2024, 6, 30), "opc_council") == 2024
    # Other sources use the calendar year.
    assert ge.fiscal_year(date(2024, 3, 1), "zz_unknown_feed") == 2024
    assert ge.fiscal_year(None, "nih_reporter") is None


def test_amount_basis_per_source_and_default() -> None:
    assert "fiscal-year total cost" in ge.amount_basis("nih_reporter")
    assert "estimatedTotalAmt" in ge.amount_basis("nsf_awards")
    assert "obligated" in ge.amount_basis("usaspending")
    assert "as announced" in ge.amount_basis("ca_sea_grant")
    assert ge.amount_basis("zz_unknown_feed") == ge.DEFAULT_AMOUNT_BASIS


def test_row_mapping_fields_and_pi_limit() -> None:
    payload = _payload()
    rows = {row["grant_key"]: row for row in payload["rows"]}
    nih = rows["0000000000000001"]
    assert set(nih) == set(ge.ROW_KEYS)
    assert nih["pi_names"] == ["Ada Lovelace", "Grace Hopper", "Alan Turing"]
    assert nih["amount"] == 100000.46
    assert nih["start"] == "2024-10-01"
    assert nih["fiscal_year"] == 2025
    assert nih["funder_type"] == "federal"
    assert nih["funder_chain"] == ["NIH", "NIEHS"]
    assert nih["institution_type"] == "UC"  # joined on exact normalized name
    assert nih["plastic_related"] is True
    assert nih["ca_led"] is True

    sea = rows["0000000000000003"]
    assert sea["amount"] is None and sea["currency"] is None
    assert sea["funder_type"] == "state"
    assert sea["plastic_related"] is False
    assert sea["institution_type"] == "CSU"

    nsf = rows["0000000000000002"]
    assert nsf["plastic_related"] is None  # unknown stays null, never false
    assert nsf["ca_led"] is False
    assert nsf["domain_tags"] == []


def test_institution_type_join_and_unknown_fallbacks() -> None:
    rows = {row["grant_key"]: row for row in _payload()["rows"]}
    assert rows["0000000000000005"]["institution_type"] == "company"
    # Conflicting institution types for one name never guess.
    _, by_name = ge.build_institution_index(INSTITUTIONS)
    assert by_name["ambiguous lab"] == "unknown"
    assert ge.institution_type("Ambiguous Lab", None, {}, by_name) == "unknown"
    assert rows["0000000000000004"]["institution_type"] == "unknown"  # no org
    assert rows["0000000000000006"]["institution_type"] == "UC"


def test_ror_join_preferred_when_present() -> None:
    by_ror, by_name = ge.build_institution_index(INSTITUTIONS)
    assert by_ror == {"0abc": "UC"}
    assert ge.institution_type("Unrelated Name", "https://ror.org/0abc", by_ror, by_name) == "UC"
    assert ge.institution_type("Ambiguous Lab", None, by_ror, by_name) == "unknown"


def test_no_abstract_or_contact_fields_leak() -> None:
    payload = _payload()
    text = json.dumps(payload)
    assert SECRET not in text
    assert "abstract" not in text
    assert "email" not in text.lower()
    for row in payload["rows"]:
        assert set(row) == set(ge.ROW_KEYS)


def test_sources_and_counts() -> None:
    payload = _payload()
    assert payload["counts"] == {"input_rows": 6, "exported_rows": 6, "undated_rows": 1}
    assert payload["sources"]["nih_reporter"]["rows"] == 1
    assert payload["sources"]["ca_sea_grant"]["amount_rows"] == 0
    assert payload["sources"]["zz_unknown_feed"]["funder_type"] == "other"
    assert payload["caveat"] == ge.CAVEAT


def test_aggregates_match_row_totals() -> None:
    payload = _payload()
    rows = [row for row in payload["rows"] if row["fiscal_year"] is not None]
    by_year = payload["aggregates"]["by_year_funder_type"]
    assert sum(item["count"] for item in by_year) == len(rows)
    for item in by_year:
        members = [
            row
            for row in rows
            if row["fiscal_year"] == item["fiscal_year"]
            and row["funder_type"] == item["funder_type"]
        ]
        assert item["count"] == len(members)
        assert item["amount_sum"] == round(sum(r["amount"] or 0 for r in members), 2)
        assert item["amount_count"] == sum(r["amount"] is not None for r in members)

    by_type = payload["aggregates"]["by_institution_type"]
    assert sum(item["count"] for item in by_type) == len(payload["rows"])
    assert {item["institution_type"] for item in by_type} >= {"UC", "unknown"}


def test_output_is_deterministic_and_order_independent(tmp_path: Path) -> None:
    rows = _synthetic_rows()
    first = ge.serialize(_payload(rows))
    second = ge.serialize(_payload(list(reversed(rows))))
    assert first == second
    rows_out = json.loads(first)["rows"]
    order = [(row["start"] or "9999-12-31", row["grant_key"]) for row in rows_out]
    assert order == sorted(order)


def test_duplicate_grant_keys_are_rejected() -> None:
    rows = _synthetic_rows()
    rows[1]["grant_key"] = rows[0]["grant_key"]
    with pytest.raises(ValueError, match="unique"):
        _payload(rows)


def test_build_from_paths_writes_compact_file_with_small_gzip(tmp_path: Path) -> None:
    merged = _write_merged(tmp_path / "grants_merged.parquet", _synthetic_rows())
    institutions = tmp_path / "institutions.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "display_name": row["display_name"],
                    "ror_id": row["ror_id"],
                    "atlas_type": row["atlas_type"],
                }
                for row in INSTITUTIONS
            ]
        ),
        institutions,
    )
    output = tmp_path / "out" / "grants.json"
    summary = ge.build_from_paths(
        merged=merged,
        institutions=institutions,
        dedupe_map=None,
        output=output,
        generated_at=GENERATED,
    )
    assert summary["exported_rows"] == 6
    assert summary["gzip_bytes"] < 1_000_000
    data = output.read_bytes()
    assert data == ge.serialize(json.loads(data))
    again = tmp_path / "again.json"
    ge.build_from_paths(
        merged=merged,
        institutions=institutions,
        dedupe_map=None,
        output=again,
        generated_at=GENERATED,
    )
    assert again.read_bytes() == data
