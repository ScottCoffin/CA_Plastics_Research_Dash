"""Tests for organisations-only admission, normalisation, dedupe and region mapping (CG-3).

Covers spec T-ORG, T-NRM, T-DUP and T-RGN (docs/BFFP.md section 4.4; A4-D20, A4-C3).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from atlas.groups import admission
from atlas.groups.roster import RawEntry, parse_members_org
from atlas.regions.registry import load_registry

SAMPLE = Path(__file__).resolve().parent / "fixtures" / "groups" / "bffp_members_org_sample.json"
RETRIEVED = "2026-11-26"


@pytest.fixture(scope="module")
def registry():
    return load_registry()


@pytest.fixture(scope="module")
def ambassador_map(registry):
    return admission.ambassador_region_map(registry)


def _admit(entries, registry):
    return admission.admit(entries, retrieved_on=RETRIEVED, registry=registry)


# ---------------------------------------------------------------------------
# Normalisation (T-NRM)
# ---------------------------------------------------------------------------


def test_text_is_nfc_trimmed_and_space_collapsed() -> None:
    decomposed = "Café   Network  "
    assert admission.normalise_text(decomposed) == "Café Network"
    assert admission.normalise_text(None) == ""


def test_original_script_is_kept_verbatim() -> None:
    assert admission.normalise_text("  Асоциация   Пример ") == "Асоциация Пример"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example-reef.org", "https://example-reef.org"),
        ("https://www.example-reef.org/about", "https://www.example-reef.org/about"),
        ("http://example-shore.org.uk", "http://example-shore.org.uk"),
        ("n/a", None),
        ("   ", None),
        ("", None),
        (None, None),
        ("https://exa mple.org", None),
        ("info@example.org", None),
        ("ftp://example.org", None),
        ("https://localhost", None),
    ],
)
def test_urls_keep_scheme_or_add_https_and_drop_invalid(raw, expected) -> None:
    assert admission.normalise_url(raw) == expected


@pytest.mark.parametrize(
    ("url", "domain"),
    [
        ("https://www.example-reef.org/about", "example-reef.org"),
        ("https://news.example.co.uk", "example.co.uk"),
        ("example-bay.be", "example-bay.be"),
        (None, None),
    ],
)
def test_registrable_domain(url, domain) -> None:
    assert admission.registrable_domain(admission.normalise_url(url) if url else None) == domain


def test_group_id_is_stable_and_shaped() -> None:
    first = admission.group_id_for("Example Reef Society", "NO", "example-reef.no")
    second = admission.group_id_for("example reef society", "NO", "example-reef.no")
    assert first == second
    assert re.fullmatch(r"cg_[0-9a-f]{16}", first)
    assert first != admission.group_id_for("Example Reef Society", "BE", "example-reef.no")


# ---------------------------------------------------------------------------
# Country and region mapping (T-RGN)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "iso"),
    [
        ("Mainland China", "CN"),
        ("China", "CN"),
        ("USA", "US"),
        ("United States", "US"),
        ("UK", "GB"),
        ("Korea, Republic of", "KR"),
        ("NO", "NO"),
        ("Norway", "NO"),
        ("Belgium", "BE"),
        ("Atlantis", None),
        ("", None),
        (None, None),
    ],
)
def test_country_names_map_to_iso(name, iso) -> None:
    assert admission.iso_for_country(name) == iso


def test_norway_and_belgium_map_to_registry_regions(ambassador_map) -> None:
    assert ambassador_map["NO"] == "norway"
    assert ambassador_map["BE"] == "belgium"


def test_us_stays_country_level_and_california_is_not_derived(ambassador_map) -> None:
    assert "US" not in ambassador_map
    assert "california" not in ambassador_map.values()
    assert admission.region_for("US", ambassador_map) == (None, "Northern America")


def test_unknown_country_is_region_unknown(ambassador_map) -> None:
    assert admission.region_for(None, ambassador_map) == (None, "region_unknown")
    assert admission.m49_subregion(None) == "region_unknown"


def test_m49_sub_region_for_a_country(ambassador_map) -> None:
    assert admission.region_for("CN", ambassador_map) == (None, "Eastern Asia")
    assert admission.region_for("NO", ambassador_map) == ("norway", "Northern Europe")


def test_m49_table_covers_repo_country_list() -> None:
    codes, _ = admission._country_tables()
    missing = sorted(code for code in codes if admission.m49_subregion(code) == "region_unknown")
    # French Southern Territories (TF) is not placed in a sub-region here; see the report.
    assert missing == ["TF"]


# ---------------------------------------------------------------------------
# Classification (T-ORG)
# ---------------------------------------------------------------------------


def test_free_mail_website_is_excluded_individual() -> None:
    verdict = admission.classify("Example Person", "https://gmail.com/x")
    assert verdict.org_status == "excluded_individual"


def test_personal_profile_url_is_excluded_individual() -> None:
    verdict = admission.classify(
        "Example Organisation", admission.normalise_url("https://www.linkedin.com/in/example")
    )
    assert verdict.org_status == "excluded_individual"


def test_company_page_is_not_mistaken_for_a_person() -> None:
    url = admission.normalise_url("https://www.linkedin.com/company/example-reef")
    assert admission.classify("Example Reef Co", url).org_status == "source_declared_org"


def test_weak_personal_name_without_url_is_ambiguous() -> None:
    verdict = admission.classify("Pieter Dunmore", None)
    assert verdict.org_status == "ambiguous"


def test_organisational_keyword_prevents_the_weak_signal() -> None:
    assert admission.classify("Example Reef Network", None).org_status == "source_declared_org"
    assert admission.classify("Asociación Ejemplo", None).org_status == "source_declared_org"


def test_heuristics_never_promote_and_source_declared_stays_admitted() -> None:
    assert admission.classify("Example Reef Society", "https://example-reef.org").org_status == (
        "source_declared_org"
    )


def test_admit_keeps_only_admitted_statuses_and_drops_excluded(registry) -> None:
    result = _admit(parse_members_org(SAMPLE.read_bytes()), registry)
    statuses = {record["org_status"] for record in result.records}
    assert statuses <= set(admission.ADMITTED_STATUSES)
    assert result.excluded == 2
    assert [a["name"] for a in result.ambiguous] == ["Pieter Dunmore"]
    names = {record["name"] for record in result.records}
    assert "Pieter Dunmore" not in names
    assert "Zara Quillfeather" not in names
    assert result.admitted_by_status == {
        "source_declared_org": len(result.records),
        "heuristic_org": 0,
        "human_confirmed_org": 0,
    }


def test_public_record_fields_follow_the_allow_list(registry) -> None:
    result = _admit(parse_members_org(SAMPLE.read_bytes()), registry)
    record = next(r for r in result.records if r["name"] == "Example Coast Alliance")
    assert record["country"] == "NO"
    assert record["ambassador_region"] == "norway"
    assert record["region"] == "Northern Europe"
    assert record["bffp_listed"] is True
    assert record["bffp_listed_asof"] == RETRIEVED
    assert record["roster_retrieved_at"] == RETRIEVED
    assert record["name_alt"] == []
    assert set(record) == {
        "group_id",
        "name",
        "name_alt",
        "country",
        "region",
        "ambassador_region",
        "url",
        "bffp_listed",
        "bffp_listed_asof",
        "org_status",
        "roster_retrieved_at",
    }


def test_records_sorted_by_country_then_name(registry) -> None:
    result = _admit(parse_members_org(SAMPLE.read_bytes()), registry)
    keys = [(r["country"] or "", r["name"]) for r in result.records]
    assert keys == sorted(keys)


def test_regions_follow_country_for_belgium_and_us(registry) -> None:
    entries = [
        RawEntry("Example Bay Collective", "Belgium", "example-bay.be"),
        RawEntry("Example Harbour Trust", "USA", "https://www.example-harbour.org"),
    ]
    by_name = {r["name"]: r for r in _admit(entries, registry).records}
    assert by_name["Example Bay Collective"]["ambassador_region"] == "belgium"
    assert by_name["Example Harbour Trust"]["ambassador_region"] is None
    assert by_name["Example Harbour Trust"]["country"] == "US"


# ---------------------------------------------------------------------------
# Dedupe (T-DUP)
# ---------------------------------------------------------------------------


def test_exact_duplicates_collapse_and_keep_the_other_spelling(registry) -> None:
    result = _admit(parse_members_org(SAMPLE.read_bytes()), registry)
    keepers = [r for r in result.records if r["name"].casefold() == "example river keepers"]
    assert len(keepers) == 1
    assert keepers[0]["name_alt"] == ["example river keepers"]
    assert result.duplicates_collapsed == 1


def test_near_duplicate_goes_to_review_and_both_are_kept(registry) -> None:
    result = _admit(parse_members_org(SAMPLE.read_bytes()), registry)
    names = {r["name"] for r in result.records}
    assert {"Example Coast Alliance", "Example Coast Alliances"} <= names
    (pair,) = [p for p in result.dupe_review if p["country"] == "NO"]
    assert pair["reason"] == "similar name"
    assert {pair["name_a"], pair["name_b"]} == {"Example Coast Alliance", "Example Coast Alliances"}


def test_same_registrable_domain_within_a_country_is_reviewed(registry) -> None:
    entries = [
        RawEntry("Example Reef Society", "Norway", "https://example-reef.no"),
        RawEntry("Example Lagoon Forum", "Norway", "https://www.example-reef.no/forum"),
    ]
    result = _admit(entries, registry)
    assert len(result.records) == 2
    assert [p["reason"] for p in result.dupe_review] == ["same registrable domain"]


def test_social_host_is_not_a_duplicate_key(registry) -> None:
    entries = [
        RawEntry("Example Reef Society", "Norway", "https://facebook.com/reef"),
        RawEntry("Example Lagoon Forum", "Norway", "https://facebook.com/lagoon"),
    ]
    assert _admit(entries, registry).dupe_review == []


def test_bffp_country_spellings_and_artefacts() -> None:
    from atlas.groups.admission import iso_for_country

    assert iso_for_country("Korea (Republic of)") == "KR"
    assert iso_for_country("Taiwan; Republic of China (ROC)") == "TW"
    assert iso_for_country("Congo (Democratic Republic of the)") == "CD"
    assert iso_for_country("Kenya<") == "KE"
    # A broken source value and a non-country stay unmapped (region_unknown).
    assert iso_for_country("eSwatini<") is None
    assert iso_for_country("Global") is None
    assert iso_for_country("Eswatini") == "SZ"


def test_an_email_address_as_the_name_is_excluded() -> None:
    from atlas.groups.admission import classify

    assert classify("someone@example.com", None).org_status == "excluded_individual"
    assert (
        classify("Example River Keepers", "https://example.org/a@b.co").org_status
        == "excluded_individual"
    )
    assert (
        classify("Example River Keepers", "https://example.org").org_status == "source_declared_org"
    )
