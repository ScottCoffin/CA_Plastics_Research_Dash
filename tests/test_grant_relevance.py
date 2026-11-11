"""Tests for grant plastic relevance: title rule, abstract-only default, reviewed overrides.

Offline. Uses a small inline query config and synthetic records only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.build import grants_export as ge
from atlas.build.curation import GRANT_RELEVANCE_HEADER, load_grant_relevance
from atlas.ingest.grants.normalize import (
    TITLE_RULE_MAX_CHARS,
    grant_plastic_decision,
    normalize_grant,
    write_grants_parquet,
)

QUERY = {
    "version": "test",
    "core_terms": ["microplastic", "plastic pollution"],
    "qualified_terms": [],
    "tier_2_terms": [],
    "exclusions": ["sediment core"],
}
TAXONOMY: dict = {"domain_tags": []}


# --- grant_plastic_decision ---------------------------------------------------------


def test_title_hit_is_plastic_related() -> None:
    assert grant_plastic_decision("Microplastic loads in estuaries", "", QUERY) == (True, "title")


def test_title_hit_with_abstract_is_still_title_basis() -> None:
    decision = grant_plastic_decision("Microplastic loads", "Unrelated abstract.", QUERY)
    assert decision == (True, "title")


def test_abstract_only_mention_defaults_to_not_plastic() -> None:
    decision = grant_plastic_decision(
        "Equipment for coastal lab",
        "Instruments to measure e.g. microplastics in water samples.",
        QUERY,
    )
    assert decision == (False, "abstract_mention_only")


def test_no_match_is_none() -> None:
    assert grant_plastic_decision("Pension administration", "Budget review.", QUERY) == (
        False,
        "none",
    )


def test_title_longer_than_limit_falls_through_to_abstract_rule() -> None:
    long_title = "Microplastic " + "x" * TITLE_RULE_MAX_CHARS
    assert len(long_title) > TITLE_RULE_MAX_CHARS
    assert grant_plastic_decision(long_title, "", QUERY) == (False, "abstract_mention_only")


def test_title_at_limit_still_uses_title_rule() -> None:
    title = "Microplastic " + "x" * (TITLE_RULE_MAX_CHARS - len("Microplastic "))
    assert len(title) == TITLE_RULE_MAX_CHARS
    assert grant_plastic_decision(title, None, QUERY) == (True, "title")


def test_override_true_wins_over_rules() -> None:
    decision = grant_plastic_decision(
        "Pension administration",
        "Budget review.",
        QUERY,
        overrides={"KEY-1": True},
        grant_key="KEY-1",
    )
    assert decision == (True, "reviewed")


def test_override_false_wins_over_title_rule() -> None:
    decision = grant_plastic_decision(
        "Microplastic loads in estuaries",
        "",
        QUERY,
        overrides={"KEY-1": False},
        grant_key="KEY-1",
    )
    assert decision == (False, "reviewed")


def test_override_ignored_for_other_keys_or_missing_key() -> None:
    overrides = {"KEY-1": False}
    assert grant_plastic_decision(
        "Microplastic loads", "", QUERY, overrides=overrides, grant_key="KEY-2"
    ) == (True, "title")
    assert grant_plastic_decision(
        "Microplastic loads", "", QUERY, overrides=overrides, grant_key=None
    ) == (True, "title")


def test_exclusion_blocks_title_rule() -> None:
    assert grant_plastic_decision("Sediment core microplastic record", "", QUERY) == (
        False,
        "none",
    )


# --- normalize_grant uses the title and abstract rule -------------------------------


def _raw(**extra: object) -> dict:
    base: dict = {
        "source_award_id": "SYN-0001",
        "title": "Equipment purchase",
        "abstract": "Shared instruments, for example to measure microplastics.",
    }
    base.update(extra)
    return base


def test_normalize_grant_abstract_only_is_not_plastic() -> None:
    row = normalize_grant(_raw(), source="TEST_SOURCE", query_config=QUERY, taxonomy=TAXONOMY)
    assert row["plastic_related"] is False


def test_normalize_grant_title_hit_is_plastic() -> None:
    row = normalize_grant(
        _raw(title="Microplastic exposure"),
        source="TEST_SOURCE",
        query_config=QUERY,
        taxonomy=TAXONOMY,
    )
    assert row["plastic_related"] is True


# --- load_grant_relevance -----------------------------------------------------------


def _write_csv(
    path: Path, lines: list[str], header: str = ",".join(GRANT_RELEVANCE_HEADER)
) -> Path:
    path.write_text("\n".join([header, *lines]) + "\n", encoding="utf-8")
    return path


def test_loader_reads_true_and_false(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "r.csv",
        ["aaa,true,high,reason,owner,2026-11-10,pending", "bbb,FALSE,low,reason,owner,2026-11-10,"],
    )
    assert load_grant_relevance(path) == {"aaa": True, "bbb": False}


def test_loader_missing_file_is_empty(tmp_path: Path) -> None:
    assert load_grant_relevance(tmp_path / "absent.csv") == {}


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (["aaa,maybe,high,reason,owner,2026-11-10,pending"], "must be true or false"),
        (["aaa,,high,reason,owner,2026-11-10,pending"], "plastic_related is required"),
        ([",true,high,reason,owner,2026-11-10,pending"], "grant_key is required"),
        (
            [
                "aaa,true,high,r,owner,2026-11-10,pending",
                "aaa,false,high,r,owner,2026-11-10,pending",
            ],
            "listed more than once",
        ),
    ],
)
def test_loader_rejects_bad_rows(tmp_path: Path, lines: list[str], message: str) -> None:
    path = _write_csv(tmp_path / "r.csv", lines)
    with pytest.raises(ValueError, match=message):
        load_grant_relevance(path)


def test_loader_rejects_wrong_header(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path / "r.csv",
        ["aaa,true,high,r,owner,2026-11-10,pending"],
        header="grant_key,plastic_related",
    )
    with pytest.raises(ValueError, match="header must be"):
        load_grant_relevance(path)


# --- export applies the decision and overrides --------------------------------------


def _merged_fixture(tmp_path: Path) -> Path:
    specs = [
        ("SYN-A", "Microplastic exposure in fish", "", "2024-01-01"),
        ("SYN-B", "Equipment purchase", "e.g. microplastics in water samples.", "2024-02-01"),
        ("SYN-C", "Equipment purchase", "e.g. microplastics in water samples.", "2024-03-01"),
        ("SYN-D", "Pension review", "Budget.", "2024-04-01"),
    ]
    rows = [
        normalize_grant(
            {
                "source_award_id": award_id,
                "title": title,
                "abstract": abstract or None,
                "start": start,
            },
            source="TEST_SOURCE",
            query_config=QUERY,
            taxonomy=TAXONOMY,
        )
        for award_id, title, abstract, start in specs
    ]
    path = tmp_path / "grants_merged.parquet"
    write_grants_parquet(rows, path)
    return path


def _key(award_id: str) -> str:
    from atlas.ingest.grants.schema import grant_key

    return grant_key("TEST_SOURCE", award_id)


def test_export_recomputes_flag_and_applies_overrides(tmp_path: Path) -> None:
    merged = _merged_fixture(tmp_path)
    output = tmp_path / "grants.json"
    overrides = {_key("SYN-A"): False, _key("SYN-C"): True}
    summary = ge.build_from_paths(
        merged=merged,
        institutions=tmp_path / "missing_institutions.parquet",
        dedupe_map=None,
        output=output,
        generated_at="2026-11-10T00:00:00Z",
        query_config=QUERY,
        relevance=overrides,
    )
    assert summary["exported_rows"] == 4
    rows = json.loads(output.read_text(encoding="utf-8"))["rows"]
    by_start = {row["start"]: row["plastic_related"] for row in rows}
    assert by_start == {
        "2024-01-01": False,  # title hit, reviewed as not plastic
        "2024-02-01": False,  # abstract-only, unreviewed
        "2024-03-01": True,  # abstract-only, reviewed as plastic
        "2024-04-01": False,  # no match
    }


def test_export_without_query_config_keeps_merged_flag(tmp_path: Path) -> None:
    merged = _merged_fixture(tmp_path)
    output = tmp_path / "grants.json"
    ge.build_from_paths(
        merged=merged,
        institutions=tmp_path / "missing_institutions.parquet",
        dedupe_map=None,
        output=output,
        generated_at="2026-11-10T00:00:00Z",
    )
    rows = json.loads(output.read_text())["rows"]
    assert {row["start"]: row["plastic_related"] for row in rows}["2024-01-01"] is True


def test_strong_abstract_terms_outrank_assisted_calls_but_not_owner() -> None:
    config = {"version": "t", "core_terms": ["microplastic"]}
    abstract = "We will quantify micro-plastics and anthropogenic debris on beaches."
    assert grant_plastic_decision(
        "Cell biology",
        "nanoplastic pollution uptake",
        config,
        {"G3": False},
        "G3",
        owner_reviewed=frozenset(),
    ) == (True, "abstract_strong_term")
    haiku_false = {"G1": False, "G2": False}
    related, basis = grant_plastic_decision(
        "Beach ecology", abstract, config, haiku_false, "G1", owner_reviewed=frozenset()
    )
    assert (related, basis) == (True, "abstract_strong_term")
    related, basis = grant_plastic_decision(
        "Beach ecology", abstract, config, haiku_false, "G2", owner_reviewed={"G2"}
    )
    assert (related, basis) == (False, "owner")
    # Plasticity and plastic surgery are not strong terms.
    related, basis = grant_plastic_decision(
        "Neural plasticity",
        "plastic surgery outcomes",
        config,
        haiku_false,
        "G1",
        owner_reviewed=frozenset(),
    )
    assert basis == "reviewed" and related is False
    # Legacy callers (no owner_reviewed) keep every override authoritative.
    assert grant_plastic_decision("Beach ecology", abstract, config, haiku_false, "G1") == (
        False,
        "reviewed",
    )
