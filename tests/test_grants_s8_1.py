"""Unit tests for the S8.1 grant schema and normalization library."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from atlas.ingest.grants import (
    GRANT_COLUMNS,
    GRANT_SCHEMA,
    grant_key,
    normalize_grant,
    validate_grants,
    write_grants_parquet,
)

FIXTURE = Path("tests/fixtures/s8_1_grants.json")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")

GOLDEN_KEY = "80a2a46282e95427"  # grant_key("SYNTH_FUNDER_A", "SYNTH-0001"); frozen.

QUERY_CONFIG = {
    "core_terms": ["microplastic", "plastic debris"],
    "exclusions": ["retirement"],
    "tier_2_terms": [],
    "qualified_terms": [],
}
TAXONOMY_CONFIG = {
    "domain_tags": [
        {"id": "occurrence_and_monitoring", "seed_concepts": ["occurrence", "monitoring"]},
        {"id": "wastewater_and_treatment", "seed_concepts": ["wastewater", "effluent"]},
    ]
}


def _normalize(raw: dict, source: str = "TEST_SOURCE") -> dict:
    return normalize_grant(raw, source=source, query_config=QUERY_CONFIG, taxonomy=TAXONOMY_CONFIG)


def _base(**extra: object) -> dict:
    raw: dict = {"source_award_id": "TEST-0001", "title": "Synthetic grant title"}
    raw.update(extra)
    return raw


def _valid_row(**overrides: object) -> dict:
    row = _normalize(_base(title="Microplastic synthetic study"))
    row.update(overrides)
    return row


# --- schema -----------------------------------------------------------------


def test_columns_match_c3_order() -> None:
    assert GRANT_COLUMNS == (
        "grant_key",
        "source",
        "source_award_id",
        "title",
        "abstract",
        "pi_names",
        "org",
        "org_ror",
        "org_state",
        "start",
        "end",
        "amount",
        "currency",
        "funder",
        "program",
        "funder_chain",
        "url",
        "plastic_related",
        "domain_tags",
        "ca_led",
        "ca_sampling_flag",
    )
    assert GRANT_SCHEMA.names == list(GRANT_COLUMNS)


def test_schema_types_and_nullability() -> None:
    types = {field.name: field.type for field in GRANT_SCHEMA}
    assert types["start"] == pa.date32()
    assert types["end"] == pa.date32()
    assert types["amount"] == pa.float64()
    assert types["pi_names"] == pa.list_(pa.string())
    assert types["funder_chain"] == pa.list_(pa.string())
    assert types["domain_tags"] == pa.list_(pa.string())
    for name in ("plastic_related", "ca_led", "ca_sampling_flag"):
        assert types[name] == pa.bool_()
        assert GRANT_SCHEMA.field(name).nullable
    for name in ("grant_key", "source", "source_award_id", "title"):
        assert not GRANT_SCHEMA.field(name).nullable


# --- grant_key --------------------------------------------------------------


def test_grant_key_golden_value_is_frozen() -> None:
    assert grant_key("SYNTH_FUNDER_A", "SYNTH-0001") == GOLDEN_KEY


def test_grant_key_shape() -> None:
    key = grant_key("SYNTH_FUNDER_A", "SYNTH-0002")
    assert len(key) == 16
    assert set(key) <= set("0123456789abcdef")


def test_grant_key_strips_both_parts() -> None:
    assert grant_key("  SYNTH_FUNDER_A ", " SYNTH-0001\t") == GOLDEN_KEY


def test_grant_key_is_case_sensitive() -> None:
    assert grant_key("synth_funder_a", "SYNTH-0001") != GOLDEN_KEY


def test_grant_key_separator_prevents_boundary_collision() -> None:
    assert grant_key("ab", "c") != grant_key("a", "bc")


@pytest.mark.parametrize(
    ("source", "award"),
    [("", "SYNTH-1"), ("   ", "SYNTH-1"), (None, "SYNTH-1"), ("SRC", ""), ("SRC", "  ")],
)
def test_grant_key_rejects_blank_parts(source: object, award: object) -> None:
    with pytest.raises(ValueError):
        grant_key(source, award)  # type: ignore[arg-type]


# --- normalize_grant: text, identifiers, and organisation fields -------------


def test_normalize_trims_strings_and_derives_key() -> None:
    row = _normalize(
        {
            "source_award_id": "  TEST-0009 ",
            "title": "  Trimmed title  ",
            "abstract": "   ",
            "org": "  Synthetic Org ",
            "funder": " Synthetic Funder ",
            "program": "",
            "url": " https://example.invalid/x ",
        },
        source=" TEST_SOURCE ",
    )
    assert row["source"] == "TEST_SOURCE"
    assert row["source_award_id"] == "TEST-0009"
    assert row["grant_key"] == grant_key("TEST_SOURCE", "TEST-0009")
    assert row["title"] == "Trimmed title"
    assert row["abstract"] is None
    assert row["org"] == "Synthetic Org"
    assert row["funder"] == "Synthetic Funder"
    assert row["program"] is None
    assert row["url"] == "https://example.invalid/x"


def test_normalize_requires_source_award_id_and_title() -> None:
    with pytest.raises(ValueError, match="source_award_id"):
        _normalize({"title": "Synthetic"})
    with pytest.raises(ValueError, match="title"):
        _normalize({"source_award_id": "TEST-1", "title": "   "})
    with pytest.raises(ValueError, match="source is required"):
        normalize_grant(_base(), source="", query_config=QUERY_CONFIG, taxonomy=TAXONOMY_CONFIG)


def test_org_ror_url_prefix_is_removed() -> None:
    assert _normalize(_base(org_ror="https://ror.org/00synth001"))["org_ror"] == "00synth001"
    assert _normalize(_base(org_ror="  "))["org_ror"] is None


def test_pi_names_and_funder_chain_are_ordered_lists() -> None:
    row = _normalize(
        _base(
            pi_names=[" Test Investigator One ", "", "Test Investigator Two"],
            funder_chain=["Synthetic Pass-Through Agency", "Synthetic State Sea Grant"],
        )
    )
    assert row["pi_names"] == ["Test Investigator One", "Test Investigator Two"]
    assert row["funder_chain"] == [
        "Synthetic Pass-Through Agency",
        "Synthetic State Sea Grant",
    ]


def test_list_fields_reject_bare_strings() -> None:
    with pytest.raises(ValueError, match="pi_names"):
        _normalize(_base(pi_names="Test Investigator One"))
    with pytest.raises(ValueError, match="funder_chain"):
        _normalize(_base(funder_chain="Synthetic Agency"))


# --- dates -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2024-07-01", date(2024, 7, 1)),
        ("2025-01", date(2025, 1, 1)),
        ("2025", date(2025, 1, 1)),
        ("  2026-06-30 ", date(2026, 6, 30)),
        ("", None),
        (None, None),
    ],
)
def test_dates_parse_iso_precisions(text: object, expected: date | None) -> None:
    row = _normalize(_base(start=text, end=text))
    assert row["start"] == expected
    assert row["end"] == expected


@pytest.mark.parametrize("text", ["2025-13", "2025-02-30", "July 2025", "25-01-01", "2025/01/01"])
def test_invalid_dates_raise(text: str) -> None:
    with pytest.raises(ValueError, match="start"):
        _normalize(_base(start=text))


# --- amounts and currency ------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("$1,234.50", 1234.5),
        ("250000", 250000.0),
        (0, 0.0),
        (18750.5, 18750.5),
        ("  ", None),
        ("", None),
        (None, None),
    ],
)
def test_amount_parsing(value: object, expected: float | None) -> None:
    assert _normalize(_base(amount=value))["amount"] == expected


@pytest.mark.parametrize("value", ["-5", "-$1,000", "nan", "inf", "abc", True])
def test_amount_rejects_negative_non_finite_and_malformed(value: object) -> None:
    with pytest.raises(ValueError, match="amount"):
        _normalize(_base(amount=value))


def test_currency_is_uppercased_and_validated() -> None:
    assert _normalize(_base(currency="usd"))["currency"] == "USD"
    assert _normalize(_base(currency=" "))["currency"] is None
    with pytest.raises(ValueError, match="currency"):
        _normalize(_base(currency="US"))


# --- CA flags and unknowns ---------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "ca_led"),
    [("ca", True), ("CA", True), ("NY", False), ("or", False)],
)
def test_ca_led_follows_known_state(state: str, ca_led: bool) -> None:
    row = _normalize(_base(org_state=state))
    assert row["org_state"] == state.upper()
    assert row["ca_led"] is ca_led


def test_unknown_state_keeps_ca_led_none() -> None:
    for state in (None, "", "   "):
        row = _normalize(_base(org_state=state))
        assert row["org_state"] is None
        assert row["ca_led"] is None


def test_malformed_state_raises() -> None:
    with pytest.raises(ValueError, match="org_state"):
        _normalize(_base(org_state="California"))


def test_ca_sampling_flag_stays_unknown() -> None:
    assert _normalize(_base(org_state="CA"))["ca_sampling_flag"] is None


def test_minimal_record_keeps_optional_fields_unknown() -> None:
    row = _normalize(_base())
    for column in ("abstract", "org", "org_ror", "org_state", "start", "end", "amount"):
        assert row[column] is None, column
    for column in ("currency", "funder", "program", "url", "ca_led", "ca_sampling_flag"):
        assert row[column] is None, column
    assert row["pi_names"] == []
    assert row["funder_chain"] == []
    assert row["domain_tags"] == []
    assert set(row) == set(GRANT_COLUMNS)


# --- provisional plastic relevance and domain tags ----------------------------------


def test_plastic_relevance_positive_title() -> None:
    row = _normalize(_base(title="Microplastic abundance in estuarine sediment"))
    assert row["plastic_related"] is True


def test_plastic_relevance_negative_title() -> None:
    row = _normalize(_base(title="Municipal pension administration review"))
    assert row["plastic_related"] is False


def test_abstract_contributes_to_relevance_and_domain_tags() -> None:
    row = _normalize(
        _base(
            title="Coastal planning",
            abstract="Monitoring microplastic loads in wastewater effluent.",
        )
    )
    assert row["plastic_related"] is True
    assert row["domain_tags"] == ["occurrence_and_monitoring", "wastewater_and_treatment"]


def test_real_config_files_classify_fixture_positive() -> None:
    query_config = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    row = normalize_grant(
        _base(title="Microplastic abundance in California beach sediments"),
        source="TEST_SOURCE",
        query_config=query_config,
        taxonomy=taxonomy,
    )
    assert row["plastic_related"] is True


# --- validation --------------------------------------------------------------------


def test_validate_accepts_normalized_rows() -> None:
    second = _normalize(_base(title="Microplastic synthetic study", source_award_id="TEST-0002"))
    validate_grants([_valid_row(), second])


def test_validate_rejects_duplicate_grant_key() -> None:
    with pytest.raises(ValueError, match="duplicate grant_key"):
        validate_grants([_valid_row(), _valid_row()])


def test_validate_reports_every_problem() -> None:
    bad = _valid_row()
    bad["title"] = ""
    bad["amount"] = -1.0
    bad.pop("url")
    with pytest.raises(ValueError) as error:
        validate_grants([bad, _valid_row(ca_led="yes")])
    message = str(error.value)
    assert "row 0: title is required" in message
    assert "row 0: amount" in message
    assert "row 0: missing columns ['url']" in message
    assert "row 1: ca_led must be a boolean or null" in message


def test_validate_rejects_grant_key_mismatch() -> None:
    with pytest.raises(ValueError, match="grant_key does not match"):
        validate_grants([_valid_row(grant_key="0000000000000000")])


def test_validate_rejects_extra_columns() -> None:
    row = _valid_row()
    row["extra"] = 1
    with pytest.raises(ValueError, match="unexpected columns"):
        validate_grants([row])


def test_validate_rejects_non_null_unknown_as_false_coercion() -> None:
    row = _valid_row(ca_sampling_flag=0)
    with pytest.raises(ValueError, match="ca_sampling_flag"):
        validate_grants([row])


# --- parquet ---------------------------------------------------------------------


def _fixture_rows() -> list[dict]:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    query_config = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    return [
        normalize_grant(
            copy.deepcopy(item["raw"]),
            source=item["source"],
            query_config=query_config,
            taxonomy=taxonomy,
        )
        for item in records
    ]


def test_fixture_is_small_synthetic_and_validates() -> None:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert 0 < len(records) <= 20
    assert all(item["raw"]["source_award_id"].startswith("SYNTH-") for item in records)
    rows = _fixture_rows()
    validate_grants(rows)
    assert len({row["grant_key"] for row in rows}) == len(rows)


def test_parquet_round_trip_preserves_schema_and_values(tmp_path: Path) -> None:
    rows = _fixture_rows()
    target = tmp_path / "grants.parquet"
    write_grants_parquet(rows, target)
    table = pq.read_table(target)
    assert table.schema.equals(GRANT_SCHEMA)
    assert table.column_names == list(GRANT_COLUMNS)
    expected = sorted(rows, key=lambda row: row["grant_key"])
    assert table.to_pylist() == expected
    assert [p.name for p in tmp_path.iterdir()] == ["grants.parquet"]


def test_parquet_order_is_deterministic(tmp_path: Path) -> None:
    rows = _fixture_rows()
    forward = tmp_path / "forward.parquet"
    reverse = tmp_path / "reverse.parquet"
    write_grants_parquet(rows, forward)
    write_grants_parquet(list(reversed(rows)), reverse)
    keys_forward = [r["grant_key"] for r in pq.read_table(forward).to_pylist()]
    keys_reverse = [r["grant_key"] for r in pq.read_table(reverse).to_pylist()]
    assert keys_forward == sorted(keys_forward)
    assert keys_forward == keys_reverse


def test_write_refuses_invalid_rows(tmp_path: Path) -> None:
    target = tmp_path / "grants.parquet"
    with pytest.raises(ValueError):
        write_grants_parquet([_valid_row(), _valid_row()], target)
    assert not target.exists()
