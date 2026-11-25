"""REG-1: region page payloads (region-v1) from synthetic inputs only."""

from __future__ import annotations

import copy
import gzip
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlas.build.region_pages import (
    AMBASSADORS,
    SCHEMA_VERSION,
    SECTION_IDS,
    RegionConfigError,
    build_region_payload,
    encode,
    read_work_countries,
    scan_authorships,
    section_status,
    unconfirmed_items,
    validate_config,
    validate_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_region_pages.py"


def _script():
    spec = importlib.util.spec_from_file_location("build_region_pages", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _item(name: str, status: str = "to_confirm") -> dict[str, Any]:
    return {"name": name, "url": "", "kind": "funder", "status": status, "note": "placeholder"}


def _config(iso: str = "NO") -> dict[str, Any]:
    sections = []
    for section_id in SECTION_IDS:
        sections.append(
            {
                "id": section_id,
                "title": section_id.replace("_", " ").title(),
                "summary": "Synthetic summary.",
                "needs": "Synthetic need.",
                "items": [_item(f"{section_id} candidate")],
            }
        )
    return {
        "schema_version": 1,
        "slug": "synthetic",
        "name": "Synthetic",
        "iso": iso,
        "tier": "A",
        "languages": ["en"],
        "local_search_terms": [
            {"term": "term", "language": "en", "status": "to_confirm", "note": "synthetic"}
        ],
        "sections": sections,
    }


def _countries_payload() -> dict[str, Any]:
    def entry(iso: str, total: int, first: int, pmid: int) -> dict[str, Any]:
        years = list(range(1970, 2025))
        by_year = [{"year": y, "count": 0} for y in years]
        by_year[-1]["count"] = total - 1  # 2024: put all but one work there
        by_year[-2]["count"] = 1  # 2023
        series = by_year + [{"year": 2025, "count": 0, "partial": True}]
        return {
            "iso": iso,
            "name": iso,
            "tier": "C",
            "screening_status": "unscreened_query_hit",
            "works_total": total,
            "works_outside_years": 0,
            "works_with_pmid": pmid,
            "first_year": first,
            "top_primary_topics": [
                {"id": "T1", "name": "Topic one", "count": 5},
                {"id": "T2", "name": "Topic two", "count": 3},
            ],
            "works_by_year": series,
        }

    return {
        "schema_version": "plat4b-v1",
        "generated_at": "2026-11-25T12:00:00Z",
        "years": {"first": 1970, "last_complete": 2024, "partial": 2025},
        "countries": [entry("NO", 3, 2001, 1), entry("BE", 1, 2010, 0)],
    }


def _authorship(author_id, name, countries, institutions):
    return {
        "author": {
            "id": f"https://openalex.org/{author_id}" if author_id else None,
            "display_name": name,
            "orcid": "https://orcid.org/0000-0000-0000-0000",
            "email": None,
        }
        if name
        else {"id": None, "display_name": None},
        "countries": countries,
        "institutions": institutions,
        "raw_affiliation_strings": ["Some Univ, Oslo, Norway"],
        "affiliations": [],
    }


def _institution(inst_id, name, country, ror=None, kind="education"):
    return {
        "id": f"https://openalex.org/{inst_id}",
        "display_name": name,
        "country_code": country,
        "ror": ror,
        "type": kind,
    }


def _write_pages(tmp_path: Path, works: list[dict[str, Any]]) -> Path:
    pages = tmp_path / "raw" / "pages"
    pages.mkdir(parents=True)
    header = {"record_type": "page_header", "query_version": "v", "query_hash": "h"}
    path = pages / "0001.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        for work in works:
            handle.write(json.dumps(work) + "\n")
    return pages


@pytest.fixture
def synthetic(tmp_path: Path):
    """Three works: two with a Norway author, one Norway+Sweden, one Belgium-only."""
    works = [
        {
            "id": "https://openalex.org/W1",
            "authorships": [
                _authorship(
                    "A1",
                    "Ada Test",
                    ["NO"],
                    [_institution("I1", "Uni Oslo", "NO", "https://ror.org/1")],
                ),
                _authorship(
                    "A2",
                    "Bo Test",
                    ["SE"],
                    [_institution("I2", "Uni Lund", "SE")],
                ),
            ],
        },
        {
            "id": "https://openalex.org/W2",
            "authorships": [
                _authorship(
                    "A1",
                    "Ada Test",
                    ["NO"],
                    [_institution("I1", "Uni Oslo", "NO", "https://ror.org/1")],
                ),
                _authorship(
                    "A3",
                    "Cy Test",
                    [],
                    [_institution("I1", "Uni Oslo", "NO", "https://ror.org/1")],
                ),
            ],
        },
        {
            "id": "https://openalex.org/W3",
            "authorships": [
                _authorship(
                    "A4",
                    "Di Test",
                    ["BE"],
                    [_institution("I9", "Uni Gent", "BE")],
                ),
            ],
        },
    ]
    pages = _write_pages(tmp_path, works)
    regions_rows = [
        {"work_id": "W1", "region_kind": "country", "region_code": "NO"},
        {"work_id": "W1", "region_kind": "country", "region_code": "SE"},
        {"work_id": "W2", "region_kind": "country", "region_code": "NO"},
        {"work_id": "W3", "region_kind": "country", "region_code": "BE"},
        {"work_id": "W1", "region_kind": "registry_region", "region_code": "x"},
    ]
    return pages, regions_rows


def _build(synthetic, iso: str = "NO") -> dict[str, Any]:
    pages, rows = synthetic
    work_countries = read_work_countries(rows)
    wanted = {w for w, codes in work_countries.items() if iso in codes}
    authorships = scan_authorships(sorted(pages.glob("*.jsonl.gz")), wanted)
    return build_region_payload(
        slug="norway" if iso == "NO" else "belgium",
        name="Norway" if iso == "NO" else "Belgium",
        iso=iso,
        config=_config(iso),
        countries_payload=_countries_payload(),
        work_countries=work_countries,
        authorships=authorships,
        names={"SE": "Sweden"},
    )


def test_payload_has_schema_labels_and_no_problems(synthetic) -> None:
    payload = _build(synthetic)
    assert payload["schema_version"] == SCHEMA_VERSION == "region-v1"
    assert payload["status"] == "in_preparation"
    assert payload["screening_status"] == "unscreened_query_hit"
    assert payload["ambassadors"] == AMBASSADORS
    assert payload["generated_at"] == "2026-11-25T12:00:00Z"
    assert [s["id"] for s in payload["sections"]] == list(SECTION_IDS)
    assert validate_payload(payload, _countries_payload()) == []


def test_series_and_stats_equal_the_countries_entry(synthetic) -> None:
    payload = _build(synthetic)
    entry = next(c for c in _countries_payload()["countries"] if c["iso"] == "NO")
    assert payload["works_by_year"] == [
        {"year": row["year"], "count": row["count"], "partial": bool(row.get("partial", False))}
        for row in entry["works_by_year"]
    ]
    assert payload["stats"] == {
        "works_total": 3,
        "first_year": 2001,
        "last_complete_year": 2024,
        "works_with_pmid": 1,
    }
    assert payload["top_topics"] == [
        {"id": "T1", "name": "Topic one", "count": 5},
        {"id": "T2", "name": "Topic two", "count": 3},
    ]


def test_equality_check_fails_when_series_differs(synthetic) -> None:
    payload = _build(synthetic)
    payload["works_by_year"][0]["count"] += 1
    problems = validate_payload(payload, _countries_payload())
    assert any("works_by_year differs" in p for p in problems)


def test_institutions_count_only_the_country_and_partners_exclude_it(synthetic) -> None:
    payload = _build(synthetic)
    assert payload["top_institutions"] == [
        {
            "id": "I1",
            "name": "Uni Oslo",
            "ror": "https://ror.org/1",
            "type": "education",
            "works": 2,
        }
    ]
    assert payload["partner_countries"] == [{"iso": "SE", "name": "Sweden", "works": 1}]


def test_researchers_have_only_id_name_and_works(synthetic) -> None:
    payload = _build(synthetic)
    assert payload["top_researchers"] == [
        {"id": "A1", "name": "Ada Test", "works": 2},
        {"id": "A3", "name": "Cy Test", "works": 1},
    ]
    for row in payload["top_researchers"]:
        assert set(row) == {"id", "name", "works"}
    assert "Bo Test" not in json.dumps(payload["top_researchers"])
    assert "orcid" not in encode(payload)


def test_person_key_is_rejected_by_validator(synthetic) -> None:
    payload = _build(synthetic)
    payload["top_researchers"][0]["orcid"] = "0000-0000-0000-0000"
    problems = validate_payload(payload)
    assert any("top_researchers row carries keys" in p for p in problems)


def test_scan_reads_only_wanted_works_and_slims_authorships(synthetic) -> None:
    pages, rows = synthetic
    found = scan_authorships(sorted(pages.glob("*.jsonl.gz")), {"W3"})
    assert list(found) == ["W3"]
    assert found["W3"][0]["author_id"] == "A4"
    assert set(found["W3"][0]) == {"author_id", "author_name", "countries", "institutions"}


def test_encode_is_deterministic_lf_and_round_trips(synthetic) -> None:
    payload = _build(synthetic)
    text = encode(payload)
    assert text == encode(_build(synthetic))
    assert "\r" not in text and text.endswith("\n")
    assert json.loads(text) == payload


def test_placeholder_rule_every_item_has_status_and_unconfirmed_are_listed(synthetic) -> None:
    payload = _build(synthetic)
    assert all(
        item["status"] in ("to_confirm", "draft", "confirmed")
        for section in payload["sections"]
        for item in section["items"]
    )
    flagged = unconfirmed_items(payload["sections"])
    assert len(flagged) == len(SECTION_IDS)
    assert all(section["status"] == "placeholder" for section in payload["sections"])


def test_section_status_levels() -> None:
    assert section_status([_item("a")]) == "placeholder"
    assert section_status([_item("a", "confirmed")]) == "confirmed"
    assert section_status([_item("a", "confirmed"), _item("b")]) == "draft"


def test_config_rejects_a_missing_status_and_a_bad_status() -> None:
    config = _config()
    del config["sections"][0]["items"][0]["status"]
    with pytest.raises(RegionConfigError, match="missing keys"):
        validate_config(config)
    config = _config()
    config["sections"][1]["items"][0]["status"] = "verified"
    with pytest.raises(RegionConfigError, match="has status"):
        validate_config(config)


def test_config_rejects_wrong_section_order_and_http_urls() -> None:
    config = _config()
    config["sections"] = list(reversed(config["sections"]))
    with pytest.raises(RegionConfigError, match="sections must be exactly"):
        validate_config(config)
    config = _config()
    config["sections"][0]["items"][0]["url"] = "http://example.org/"
    with pytest.raises(RegionConfigError, match="url must be https"):
        validate_config(config)


def test_config_needs_a_note_and_a_two_letter_iso() -> None:
    config = _config()
    config["sections"][0]["items"][0]["note"] = " "
    with pytest.raises(RegionConfigError, match="needs a note"):
        validate_config(config)
    with pytest.raises(RegionConfigError, match="two capital letters"):
        validate_config(_config(iso="NOR"))


def test_validator_flags_expert_wording_and_missing_schema_keys(synthetic) -> None:
    payload = _build(synthetic)
    payload["sections"][0]["summary"] = "Ask the local experts."
    assert any("expert" in p for p in validate_payload(payload))
    broken = copy.deepcopy(_build(synthetic))
    del broken["stats"]
    assert any("top-level keys differ" in p for p in validate_payload(broken))


def test_unknown_country_fails_loudly() -> None:
    with pytest.raises(KeyError, match="no entry"):
        build_region_payload(
            slug="x",
            name="X",
            iso="FR",
            config=_config("FR"),
            countries_payload=_countries_payload(),
            work_countries={},
            authorships={},
        )


def test_real_region_configs_validate_and_match_the_registry() -> None:
    script = _script()
    slugs = sorted(region.slug for region in script.eligible_regions())
    assert slugs == ["belgium", "norway"]
    for slug in slugs:
        raw = (REPO_ROOT / "regions" / slug / "region.yml").read_text(encoding="utf-8")
        config = validate_config(yaml.safe_load(raw))
        assert config["slug"] == slug
        assert [s["id"] for s in config["sections"]] == list(SECTION_IDS)
        for section in config["sections"]:
            assert section["needs"].strip()


def test_real_region_json_files_pass_the_schema_when_present() -> None:
    countries_path = REPO_ROOT / "site" / "data" / "global" / "countries.json"
    if not countries_path.is_file():
        pytest.skip("countries.json absent")
    countries = json.loads(countries_path.read_text(encoding="utf-8"))
    for slug in ("norway", "belgium"):
        path = REPO_ROOT / "site" / "data" / slug / "region.json"
        if not path.is_file():
            pytest.skip(f"{slug}/region.json absent")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert validate_payload(payload, countries) == []


def test_generated_at_is_not_the_clock(synthetic) -> None:
    # The payload takes countries.json's generated_at, so a rebuild is byte-identical.
    stamp = datetime(2026, 11, 25, 12, 0, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert _build(synthetic)["generated_at"] == stamp


def test_not_relevant_items_validate_but_leave_the_page() -> None:
    """AMB-1: an ambassador's "not relevant" keeps the item (positions are ids) and hides it."""
    from atlas.build.region_pages import build_sections

    config = yaml.safe_load(
        (REPO_ROOT / "regions" / "norway" / "region.yml").read_text(encoding="utf-8")
    )
    first = config["sections"][0]["items"][0]
    first["status"] = "not_relevant"
    validate_config(config)
    sections = build_sections(config)
    assert first["name"] not in [item["name"] for item in sections[0]["items"]]
