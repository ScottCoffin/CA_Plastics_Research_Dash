"""Tests for the cg-v2 groups record schema and validator V1-V14 (Add-on A4, CG-4)."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from atlas.groups.schema import (
    ISO_639_1_CODES,
    derive_layer,
    load_taxonomy,
    quote_word_count,
    validate_group,
    validate_groups,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "groups"
BFFP = REPO / "docs" / "BFFP.md"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _base() -> dict[str, Any]:
    """A valid tagged record (the section 8.4 example, completed)."""
    return copy.deepcopy(_fixture("example_cg_ex001.json"))


KNOWN = {"cg_ex001"}


def _rule_ids(problems: list[str]) -> set[str]:
    return {p.split(":", 1)[0] for p in problems if p.startswith("V")}


# ---------------------------------------------------------------------------
# Passing records
# ---------------------------------------------------------------------------


def test_section_8_4_example_passes_with_its_group_id_known() -> None:
    assert validate_group(_base(), known_group_ids=KNOWN) == []


def test_verbatim_section_8_4_example_only_fails_on_known_gaps() -> None:
    # The spec example omits keys of section 8.2 and evidence for primary_activities, which V4
    # requires once primary_activities is set. Both gaps are reported, nothing else.
    problems = validate_group(_fixture("example_as_published_bffp.json"))
    assert "V4: evidence needs an entry for primary_activities" in problems
    assert all(p.startswith("SCHEMA: missing key") or p.startswith("V4:") for p in problems)


def test_untagged_roster_only_record_passes() -> None:
    assert validate_group(_fixture("roster_only_untagged.json")) == []


def test_cannot_determine_record_passes() -> None:
    assert validate_group(_fixture("cannot_determine_no_web.json")) == []


# ---------------------------------------------------------------------------
# One failing case per rule: each must report its own "V<n>:" prefix
# ---------------------------------------------------------------------------


def _set(key: str, value: Any) -> Any:
    def mutate(rec: dict[str, Any]) -> None:
        rec[key] = value

    return mutate


def _long_quote(rec: dict[str, Any]) -> None:
    rec["evidence"][0]["quote"] = " ".join(["word"] * 26)


def _drop_quote_and_not_stated(rec: dict[str, Any]) -> None:
    rec["evidence"][0]["quote"] = None
    rec["evidence"][0]["not_stated"] = False


def _both_quote_and_not_stated(rec: dict[str, Any]) -> None:
    rec["evidence"][0]["not_stated"] = True


def _no_centrality_evidence(rec: dict[str, Any]) -> None:
    rec["evidence"] = [e for e in rec["evidence"] if e["facet"] != "plastics_centrality"]


def _too_many_places(rec: dict[str, Any]) -> None:
    rec["places"] = ["US-CA", "US-OR", "US-WA", "US-NY", "US-TX", "US-FL"]


def _too_many_activities(rec: dict[str, Any]) -> None:
    rec["primary_activities"] = [
        "advocacy_campaigning",
        "policy_governance",
        "legal_action",
        "education_awareness",
        "cleanup_removal",
        "other",
    ]


def _science_without_research(rec: dict[str, Any]) -> None:
    rec["participation_in_science"] = "contributory"


def _bffp_without_date(rec: dict[str, Any]) -> None:
    rec["bffp_listed_asof"] = None


def _personal_key(rec: dict[str, Any]) -> None:
    rec["contact_person"] = {"role": "coordinator"}


def _email_value(rec: dict[str, Any]) -> None:
    rec["name_alt"] = ["write to jane.doe@example.org"]


def _ambassador_id(rec: dict[str, Any]) -> None:
    rec["ambassador_id"] = "amb_123"


def _reviewed_by_nested(rec: dict[str, Any]) -> None:
    rec["evidence"][0]["reviewed_by"] = "amb_456"


def _unknown_parent(rec: dict[str, Any]) -> None:
    rec["parent_group_id"] = "cg_missing"


def _affiliation_without_quote(rec: dict[str, Any]) -> None:
    rec["stated_affiliations"] = [
        {
            "target_group_id": None,
            "target_name": "Partner Organisation",
            "relation": "partner_of",
            "evidence": {
                "url": "https://example.org/partners",
                "accessed_at": "2026-11-26",
                "quote": None,
                "not_stated": True,
            },
        }
    ]


def _excluded_key(rec: dict[str, Any]) -> None:
    rec["excluded_count"] = 3


def _ambiguous_string(rec: dict[str, Any]) -> None:
    rec["name_alt"] = ["12 ambiguous entries were set aside"]


FAILING_CASES: list[tuple[str, Any]] = [
    ("V1", _set("layer", "adjacent")),
    ("V2", _set("entity_type", None)),
    ("V3", _long_quote),
    ("V3", _drop_quote_and_not_stated),
    ("V3", _both_quote_and_not_stated),
    ("V4", _no_centrality_evidence),
    ("V5", _too_many_places),
    ("V5", _too_many_activities),
    ("V6", _science_without_research),
    ("V7", _bffp_without_date),
    ("V8", _personal_key),
    ("V8", _email_value),
    ("V9", _ambassador_id),
    ("V9", _reviewed_by_nested),
    ("V10", _unknown_parent),
    ("V11", _affiliation_without_quote),
    ("V12", _set("org_status", "ambiguous")),
    ("V12", _set("org_status", "excluded_individual")),
    ("V13", _set("website_languages", ["en", "xx"])),
    ("V14", _excluded_key),
    ("V14", _ambiguous_string),
]


@pytest.mark.parametrize(
    ("rule", "mutate"), FAILING_CASES, ids=lambda v: getattr(v, "__name__", str(v))
)
def test_each_rule_reports_its_own_prefix(rule: str, mutate: Any) -> None:
    rec = _base()
    mutate(rec)
    problems = validate_group(rec, known_group_ids=KNOWN)
    assert problems, "mutated record should fail"
    assert any(p.startswith(f"{rule}:") for p in problems), problems


def test_v2_tagged_status_requires_geographic_scope_and_activities() -> None:
    rec = _base()
    rec["geographic_scope"] = None
    rec["primary_activities"] = []
    problems = validate_group(rec, known_group_ids=KNOWN)
    assert any(
        p.startswith("V2: status ambassador_tagged requires geographic_scope") for p in problems
    )
    assert any(
        p.startswith("V2: status ambassador_tagged requires primary_activities") for p in problems
    )


def test_v2_cannot_determine_centrality_needs_cannot_determine_status() -> None:
    rec = _base()
    rec["plastics_centrality"] = "cannot_determine"
    rec["layer"] = "untagged"
    problems = validate_group(rec, known_group_ids=KNOWN)
    assert any(p.startswith("V2: plastics_centrality cannot_determine") for p in problems)


def test_v2_cannot_determine_status_needs_reason() -> None:
    rec = _fixture("cannot_determine_no_web.json")
    rec["cannot_determine_reason"] = None
    assert any(p.startswith("V2:") for p in validate_group(rec))


def test_v2_reason_without_cannot_determine_status_is_rejected() -> None:
    rec = _base()
    rec["cannot_determine_reason"] = "dead_link"
    assert any(p.startswith("V2:") for p in validate_group(rec, known_group_ids=KNOWN))


def test_v3_quote_of_exactly_25_words_passes() -> None:
    rec = _base()
    rec["evidence"][0]["quote"] = " ".join(["word"] * 25)
    assert validate_group(rec, known_group_ids=KNOWN) == []


def test_v5_tagged_record_needs_at_least_one_activity() -> None:
    rec = _base()
    rec["primary_activities"] = []
    problems = validate_group(rec, known_group_ids=KNOWN)
    assert any(p.startswith("V5:") for p in problems)


def test_v6_not_applicable_passes_without_research_monitoring() -> None:
    rec = _base()
    rec["participation_in_science"] = "not_applicable"
    assert validate_group(rec, known_group_ids=KNOWN) == []


def test_v10_is_skipped_without_known_ids() -> None:
    rec = _base()
    rec["parent_group_id"] = "cg_missing"
    assert validate_group(rec) == []


def test_v10_checks_affiliation_targets() -> None:
    rec = _base()
    rec["stated_affiliations"] = [
        {
            "target_group_id": "cg_missing",
            "target_name": None,
            "relation": "member_of",
            "evidence": {
                "url": "https://example.org/members",
                "accessed_at": "2026-11-26",
                "quote": "Member of the coalition since 2020.",
                "not_stated": False,
            },
        }
    ]
    problems = validate_group(rec, known_group_ids=KNOWN)
    assert any(p.startswith("V10: stated_affiliations[0].target_group_id") for p in problems)


def test_v11_affiliation_with_quote_passes() -> None:
    rec = _base()
    rec["stated_affiliations"] = [
        {
            "target_group_id": "cg_ex001",
            "target_name": None,
            "relation": "partner_of",
            "evidence": {
                "url": "https://example.org/partners",
                "accessed_at": "2026-11-26",
                "quote": "We work with our partners on beach cleanups.",
                "not_stated": False,
            },
        }
    ]
    assert validate_group(rec, known_group_ids=KNOWN) == []


def test_v13_accepts_all_iso_639_1_codes_and_rejects_uppercase() -> None:
    rec = _base()
    rec["website_languages"] = ["EN"]
    assert any(p.startswith("V13:") for p in validate_group(rec, known_group_ids=KNOWN))
    assert validate_group(_base(), known_group_ids=KNOWN) == []


def test_non_mapping_record_is_reported() -> None:
    assert validate_group(["not", "a", "record"]) == ["SCHEMA: record must be a JSON object"]  # type: ignore[arg-type]


def test_missing_required_key_is_reported() -> None:
    rec = _base()
    del rec["region"]
    assert "SCHEMA: missing key 'region'" in validate_group(rec, known_group_ids=KNOWN)


def test_bad_country_and_url_are_reported() -> None:
    rec = _base()
    rec["country"] = "usa"
    rec["url"] = "example.org without a scheme"
    problems = validate_group(rec, known_group_ids=KNOWN)
    assert any("country" in p for p in problems)
    assert any("url" in p for p in problems)
    # http and https are both accepted (many group sites are still http).
    rec2 = _base()
    rec2["url"] = "http://example.org"
    assert not any("url" in p for p in validate_group(rec2, known_group_ids=KNOWN))


def test_place_codes_accept_iso_3166_2_and_reject_lowercase() -> None:
    rec = _base()
    rec["places"] = ["US", "US-CA", "NO-03"]
    assert validate_group(rec, known_group_ids=KNOWN) == []
    rec["places"] = ["us-ca"]
    assert any("places value 'us-ca'" in p for p in validate_group(rec, known_group_ids=KNOWN))


# ---------------------------------------------------------------------------
# File-level checks
# ---------------------------------------------------------------------------


def test_validate_groups_reports_duplicates_and_cross_references() -> None:
    first = _base()
    duplicate = _base()
    orphan = _base()
    orphan["group_id"] = "cg_ex002"
    orphan["parent_group_id"] = "cg_nope"
    problems = validate_groups([first, duplicate, orphan])
    assert any(p.startswith("V10: cg_ex001: duplicate group_id") for p in problems)
    assert any(p.startswith("V10: cg_ex002: parent_group_id 'cg_nope'") for p in problems)


def test_validate_groups_passes_a_clean_file() -> None:
    roster = _fixture("roster_only_untagged.json")
    assert validate_groups([_base(), roster, _fixture("cannot_determine_no_web.json")]) == []


def test_validate_groups_problem_strings_keep_rule_prefix() -> None:
    rec = _base()
    rec["layer"] = "adjacent"
    problems = validate_groups([rec])
    assert problems and all(re.match(r"^(V\d+|SCHEMA): ", p) for p in problems)
    assert "V1" in _rule_ids(problems)


# ---------------------------------------------------------------------------
# Helpers, taxonomy and spec alignment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("centrality", "layer"),
    [
        ("primary", "core"),
        ("substantial", "core"),
        ("incidental", "adjacent"),
        ("none", "adjacent"),
        ("cannot_determine", "untagged"),
        (None, "untagged"),
    ],
)
def test_derive_layer_follows_v1(centrality: str | None, layer: str) -> None:
    assert derive_layer(centrality) == layer


def test_quote_word_count_splits_on_whitespace() -> None:
    assert quote_word_count("  one two\tthree\nfour ") == 4
    assert quote_word_count("") == 0
    assert quote_word_count(None) == 0


def test_iso_639_1_list_has_184_unique_two_letter_codes() -> None:
    assert len(ISO_639_1_CODES) == 184
    assert all(re.fullmatch(r"[a-z]{2}", code) for code in ISO_639_1_CODES)


def _spec_values(facet: str) -> list[str]:
    """Values for one facet row of docs/BFFP.md section 3, in the spec's order."""
    matches = [
        line.split("\t")
        for line in BFFP.read_text(encoding="utf-8").splitlines()
        if line.split("\t")[0] == facet and len(line.split("\t")) >= 3
    ]
    assert len(matches) == 1, facet
    cell = matches[0][2].split(";")[0]
    cell = cell.replace("working labels:", "").replace("scope:", "")
    return [value.strip() for value in cell.split(",")]


@pytest.mark.parametrize(
    ("taxonomy_key", "facet"),
    [
        ("entity_type", "F1"),
        ("sector", "F2"),
        ("plastics_centrality", "F3"),
        ("primary_activities", "F4"),
        ("participation_in_science", "F5"),
        ("legal_form", "F6"),
        ("geographic_scope", "F7"),
        ("constituency", "F11"),
    ],
)
def test_taxonomy_order_matches_spec_section_3(taxonomy_key: str, facet: str) -> None:
    taxonomy = load_taxonomy()
    expected = _spec_values(facet)
    # Owner-approved additions, each logged in DECISIONS (A4 rule 10).
    for after, value in OWNER_ADDITIONS.get(taxonomy_key, ()):
        expected.insert(expected.index(after) + 1, value)
    assert list(taxonomy[taxonomy_key]) == expected


# key -> [(insert after, value)]: values the owner added to the spec's lists.
OWNER_ADDITIONS = {"sector": [("government", "joint_power_authority")]}  # A4-D25


def test_taxonomy_has_every_controlled_vocabulary() -> None:
    taxonomy = load_taxonomy()
    expected = {
        "entity_type",
        "sector",
        "plastics_centrality",
        "primary_activities",
        "participation_in_science",
        "legal_form",
        "geographic_scope",
        "constituency",
        "relation",
        "status",
        "layer",
        "source",
        "org_status",
        "cannot_determine_reason",
    }
    assert expected <= set(taxonomy)
    assert list(taxonomy["org_status"]) == [
        "source_declared_org",
        "heuristic_org",
        "human_confirmed_org",
    ]
    assert list(taxonomy["cannot_determine_reason"]) == [
        "no_web_presence",
        "dead_link",
        "language_barrier",
        "insufficient_information",
        "not_an_organisation",
        "conflict_of_interest",
    ]


def test_taxonomy_loader_rejects_wrong_schema(tmp_path: Path) -> None:
    bad = tmp_path / "taxonomy.yml"
    bad.write_text("schema: cg-v1\nsector: [a]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cg-v2"):
        load_taxonomy(bad)
