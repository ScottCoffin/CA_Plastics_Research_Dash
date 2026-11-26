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
        ("/11th Hour Project", "11th Hour Project"),
        ("  - Surfrider Foundation, ", "Surfrider Foundation"),
        ('"Ocean Allies"', "Ocean Allies"),
        ("\u201cOcean Allies\u201d", "Ocean Allies"),
        ("'Ocean Allies'", "Ocean Allies"),
        ('"Ocean Allies', "Ocean Allies"),
        ("Ocean Allies\u201d", "Ocean Allies"),
        ("R.I.S.E.", "R.I.S.E."),
        ("Example Co.", "Example Co."),
        (".Reef Watch", "Reef Watch"),
        ("Zero Waste / Basura Cero", "Zero Waste / Basura Cero"),
        ("Plastic-Free Seas", "Plastic-Free Seas"),
        ("Ocean's Allies", "Ocean's Allies"),
        ("Mar \u2022 Sin Pl\u00e1stico \u00b7", "Mar \u2022 Sin Pl\u00e1stico"),
        ("  Example   Reef  ~|_", "Example Reef"),
        ("\u4e1c\u6d77 \u201c\u6d77\u6d0b\u201d", "\u4e1c\u6d77 \u201c\u6d77\u6d0b\u201d"),
        ("///", "///"),
        ('"', '"'),
        ("", ""),
        (None, ""),
    ],
)
def test_display_name_strips_stray_edge_punctuation(raw, expected) -> None:
    assert admission.clean_display_name(raw) == expected


def test_display_name_is_never_empty_when_the_input_is_not() -> None:
    for raw in ("///", "-", " ~ ", '""'):
        assert admission.clean_display_name(raw) != ""


def test_display_name_cleaning_keeps_the_group_id_of_the_raw_name(registry) -> None:
    raw = "/11th Hour Project"
    result = _admit([RawEntry(raw, "Belgium", "https://11thhour.example.org")], registry)
    (record,) = result.records
    assert record["name"] == "11th Hour Project"
    assert record["name_alt"] == []
    domain = admission.registrable_domain("https://11thhour.example.org")
    assert record["group_id"] == admission.group_id_for(admission.normalise_text(raw), "BE", domain)


def test_name_alt_takes_the_cleaned_form_and_never_the_raw_form(registry) -> None:
    entries = [
        RawEntry("/example reef society", "Norway", "https://example-reef.no"),
        RawEntry("/Example Reef Society", "Norway", "https://example-reef.no"),
    ]
    (record,) = _admit(entries, registry).records
    assert record["name"] == "example reef society"
    assert record["name_alt"] == ["Example Reef Society"]


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


# ---------------------------------------------------------------------------
# Roster QC (CG-ROSTER-QC): entities, placeholders, automatic and reviewed merges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["-", "N/A", "Tbc", "Tes", "hhh", "??", "none"])
def test_placeholder_names_are_quarantined_not_published(registry, name) -> None:
    result = _admit([RawEntry(name, "Norway", None)], registry)
    assert result.records == []
    assert [row["reason"] for row in result.ambiguous] == ["placeholder name"]
    assert result.placeholders == 1


@pytest.mark.parametrize("name", ["USP", "FNE", "SIO"])
def test_real_short_acronyms_are_kept(registry, name) -> None:
    result = _admit([RawEntry(name, "Norway", "https://example-acro.no")], registry)
    assert [r["name"] for r in result.records] == [name]
    assert result.placeholders == 0


def test_html_entities_are_decoded_but_the_id_hashes_the_raw_name(registry) -> None:
    raw = "Example Rivers &amp; Lakes"
    result = _admit([RawEntry(raw, "Norway", "https://example-rivers.no")], registry)
    (record,) = result.records
    assert record["name"] == "Example Rivers & Lakes"
    assert record["group_id"] == admission.group_id_for(raw, "NO", "example-rivers.no")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("a tip: tap e.V.", "a tip: tap"),
        ("The Example Group Ltd", "Example Group"),
        ("BAN Toxics, Inc.", "BAN Toxics"),
        ("Less Plastic CIC", "Less Plastic"),
        ("Example S.A.", "Example"),
        ("Example gGmbH", "example"),
        ("Café Verde", "Cafe Verde"),
        ("Plastic-Free Delaware", "Plastic Free Delaware"),
        ("Let's Do It! TOGO", "Let’s Do It TOGO"),
    ],
)
def test_merge_key_treats_punctuation_legal_form_and_the_as_noise(left, right) -> None:
    assert admission.merge_key(left) == admission.merge_key(right)


def test_merge_key_keeps_generic_words() -> None:
    assert admission.merge_key("Example Foundation") != admission.merge_key("Example")
    assert admission.merge_key("Example Association") != admission.merge_key("Example")


def test_auto_merge_collapses_within_a_country_only(registry) -> None:
    entries = [
        RawEntry("a tip: tap", "Germany", "https://atiptap.org/"),
        RawEntry("a tip: tap e.V.", "Germany", "https://www.atiptap.org"),
        RawEntry("a tip: tap e.V.", "France", "https://atiptap.fr"),
    ]
    result = _admit(entries, registry)
    assert len(result.records) == 2
    (german,) = [r for r in result.records if r["country"] == "DE"]
    assert german["name"] == "a tip: tap e.V."
    assert german["name_alt"] == ["a tip: tap"]
    assert result.dupe_review == []
    assert len(result.auto_merges) == 1
    assert result.auto_merges[0]["name_drop"] == "a tip: tap"


def test_auto_merge_keeper_prefers_a_website_then_no_double_question_mark(registry) -> None:
    entries = [
        RawEntry("Example Plastic Watch CIC", "Norway", None),
        RawEntry("Example Plastic Watch Ltd", "Norway", "https://example-watch.no"),
        RawEntry("Let??s Do It Ghana", "Ghana", None),
        RawEntry("Let's Do It Ghana", "Ghana", "https://letsdo.example.gh"),
    ]
    result = _admit(entries, registry)
    by_name = {r["name"]: r for r in result.records}
    assert set(by_name) == {"Example Plastic Watch Ltd", "Let's Do It Ghana"}
    assert by_name["Example Plastic Watch Ltd"]["name_alt"] == ["Example Plastic Watch CIC"]
    assert by_name["Let's Do It Ghana"]["name_alt"] == ["Let??s Do It Ghana"]


def test_generic_word_pairs_are_not_auto_merged(registry) -> None:
    entries = [
        RawEntry("Example Foundation", "Norway", "https://example-found.no"),
        RawEntry("Example", "Norway", "https://example-plain.no"),
    ]
    assert len(_admit(entries, registry).records) == 2


def _two_norwegian_groups():
    return [
        RawEntry("Example Reef Society", "Norway", "https://example-reef.no"),
        RawEntry("Example Lagoon Forum", "Norway", "https://www.example-reef.no/forum"),
    ]


def test_reviewed_different_suppresses_the_pair_from_review(registry) -> None:
    entries = _two_norwegian_groups()
    first = _admit(entries, registry)
    keep_id, drop_id = (r["group_id"] for r in first.records)
    merge = {
        "group_id_keep": keep_id,
        "group_id_drop": drop_id,
        "decided_at": "2026-11-26T00:00:00Z",
        "decision": "different",
    }
    result = admission.admit(entries, retrieved_on=RETRIEVED, registry=registry, merges=[merge])
    assert len(result.records) == 2
    assert result.dupe_review == []


def test_reviewed_same_merges_the_drop_into_the_keep(registry) -> None:
    entries = _two_norwegian_groups()
    first = _admit(entries, registry)
    ids = {r["name"]: r["group_id"] for r in first.records}
    merge = {
        "group_id_keep": ids["Example Reef Society"],
        "group_id_drop": ids["Example Lagoon Forum"],
        "decided_at": "2026-11-26T00:00:00Z",
        "decision": "same",
    }
    result = admission.admit(entries, retrieved_on=RETRIEVED, registry=registry, merges=[merge])
    (record,) = result.records
    assert record["name"] == "Example Reef Society"
    assert record["name_alt"] == ["Example Lagoon Forum"]
    assert result.reviewed_merges_applied == 1
    assert result.dupe_review == []


def test_reviewed_merge_with_an_unknown_id_is_counted_not_applied(registry) -> None:
    merge = {
        "group_id_keep": "cg_0000000000000000",
        "group_id_drop": "cg_1111111111111111",
        "decided_at": "2026-11-26T00:00:00Z",
        "decision": "same",
    }
    result = admission.admit(
        _two_norwegian_groups(), retrieved_on=RETRIEVED, registry=registry, merges=[merge]
    )
    assert len(result.records) == 2
    assert result.reviewed_merges_unmatched == 1


def test_read_merges_header_only_missing_and_invalid(tmp_path: Path) -> None:
    header_only = tmp_path / "group_merges.csv"
    header_only.write_text("group_id_keep,group_id_drop,decided_at,decision\n", encoding="utf-8")
    assert admission.read_merges(header_only) == []
    assert admission.read_merges(tmp_path / "missing.csv") == []
    header_only.write_text(
        "group_id_keep,group_id_drop,decided_at,decision\ncg_a,cg_b,2026-11-26,maybe\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        admission.read_merges(header_only)


def test_excluded_hosts_never_make_a_same_host_pair() -> None:
    def rec(gid: str, url: str, country: str = "NO") -> dict:
        return {"group_id": gid, "name": gid, "name_alt": [], "country": country, "url": url}

    records = [
        rec("a", "https://sites.google.com/view/a"),
        rec("b", "https://sites.google.com/view/b"),
        rec("c", "https://facebook.com/c"),
        rec("d", "https://www.facebook.com/d"),
        rec("e", "https://bit.ly/e"),
        rec("f", "https://bit.ly/f"),
        rec("g", "https://example-host.no/x/http://broken.example/y"),
        rec("h", "https://example-host.no/y"),
        rec("i", "https://example-host.no/z"),
        rec("j", "https://example-host.no/w", country="SE"),
    ]
    pairs = admission.same_host_pairs(records)
    assert [(p["group_id_a"], p["group_id_b"]) for p in pairs] == [("h", "i")]
    assert admission.excluded_host("https://bit.ly/q")
    assert not admission.excluded_host("https://example-host.no/q")


def test_name_correction_keeps_the_old_name_and_is_idempotent() -> None:
    from atlas.groups.build import merge_records

    record = {
        "group_id": "cg_1",
        "name": "old name",
        "name_alt": ["other"],
        "country": "NO",
        "region": "Northern Europe",
        "ambassador_region": None,
        "url": None,
        "bffp_listed": True,
        "bffp_listed_asof": RETRIEVED,
        "org_status": "source_declared_org",
        "roster_retrieved_at": RETRIEVED,
    }
    admission.apply_name_correction(record, "New Name")
    assert record["name"] == "New Name"
    assert record["name_alt"] == ["other", "old name"]
    once = merge_records([record], None, {"cg_1": "New Name"})
    twice = merge_records([record], None, {"cg_1": "New Name"})
    assert once == twice
    assert once[0]["name"] == "New Name"
    assert once[0]["name_alt"] == ["other", "old name"]
