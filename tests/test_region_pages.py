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
    assert slugs == ["belgium", "california", "norway"]
    for slug in slugs:
        # The builder's loader drops California's site wiring keys before region-v1 validation.
        config = script._load_config(REPO_ROOT / "regions" / slug / "region.yml")
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
    sections = build_sections(config, "norway")
    assert first["name"] not in [item["name"] for item in sections[0]["items"]]


def test_item_ids_are_positions_in_region_yml_and_survive_a_hidden_item() -> None:
    """item_id is slug:section:index in region.yml, counted before not_relevant items are hidden."""
    from atlas.build.region_pages import build_sections

    config = yaml.safe_load(
        (REPO_ROOT / "regions" / "norway" / "region.yml").read_text(encoding="utf-8")
    )
    section = config["sections"][0]
    assert len(section["items"]) >= 2
    section["items"][0]["status"] = "not_relevant"
    shown = build_sections(config, "norway")[0]["items"]
    # The second item keeps index 1 although the first one is hidden.
    assert shown[0]["name"] == section["items"][1]["name"]
    assert shown[0]["item_id"] == f"norway:{section['id']}:1"
    assert [item["item_id"] for item in shown] == [
        f"norway:{section['id']}:{index}" for index in range(1, len(section["items"]))
    ]
    assert all(set(item) == {"item_id", "name", "url", "kind", "status", "note"} for item in shown)


# --- REG-CA: the default region (California) page ----------------------------------------------


def _slim(author_id, name, countries, institutions):
    return {
        "author_id": author_id,
        "author_name": name,
        "countries": countries,
        "institutions": [
            {"id": i, "name": n, "ror": None, "type": "education", "country_code": c}
            for i, n, c in institutions
        ],
    }


def _california_region():
    script = _script()
    return next(r for r in script.eligible_regions() if r.slug == "california")


def _california_countries() -> dict[str, Any]:
    years = [{"year": y, "count": 0} for y in range(1970, 2025)]
    years[-1]["count"] = 2
    years.append({"year": 2025, "count": 0, "partial": True})
    registry = {
        "region": "california",
        "matched_by": "region_predicate",
        "tier": "B",
        "screening_status": "unscreened_query_hit",
        "works_total": 3,
        "works_by_year": years,
        "works_outside_years": 0,
        "works_with_pmid": 1,
        "first_year": 1990,
        "top_primary_topics": [{"id": "T1", "name": "Topic one", "count": 2}],
    }
    base = _countries_payload()
    return {**base, "countries": base["countries"], "registry_regions": [registry]}


def test_california_payload_counts_come_from_the_registry_block_and_iso_is_us_ca() -> None:
    script = _script()
    region = _california_region()
    countries = _california_countries()
    assert script._iso(region) == "US-CA"
    # W1 and W2 are California-matched; W3 is a US work outside the registry match.
    work_countries = {
        "W1": frozenset({"US", "NO"}),
        "W2": frozenset({"US", "CN"}),
        "W3": frozenset({"US"}),
    }
    authorships = {
        "W1": [
            _slim("A1", "Ann", ["US"], [("I1", "Stanford University", "US")]),
            _slim("A3", "Cy", ["US"], [("I9", "Utah Institute", "US")]),
        ],
        "W2": [
            _slim("A1", "Ann", ["US"], [("I1", "Stanford University", "US")]),
            _slim("A4", "Di", ["CN"], [("I5", "Peking Institute", "CN")]),
        ],
        "W3": [_slim("A9", "Ed", ["US"], [("I1", "Stanford University", "US")])],
    }
    payload = script.build_california_payload(
        region=region,
        config=_config("US"),
        countries_payload=countries,
        work_countries=work_countries,
        authorships=authorships,
        registry_works=frozenset({"W1", "W2"}),
        registry_institutions=frozenset({"I1"}),
        names={"CN": "China", "NO": "Norway"},
    )
    assert payload["iso"] == "US-CA"
    assert payload["slug"] == "california"
    assert payload["stats"]["works_total"] == 3
    assert payload["stats"]["first_year"] == 1990
    # Institutions: only California registry institutions on the matched works.
    assert payload["top_institutions"] == [
        {"id": "I1", "name": "Stanford University", "ror": None, "type": "education", "works": 2}
    ]
    # Partners: other countries on the matched works; the US is never listed.
    assert [p["iso"] for p in payload["partner_countries"]] == ["CN", "NO"]
    # Researchers: authors with a US institution or country on the matched works.
    assert [(r["id"], r["works"]) for r in payload["top_researchers"]] == [("A1", 2), ("A3", 1)]
    assert validate_payload(payload, script._validation_view(region, countries)) == []


def test_california_validation_view_points_the_registry_block_at_us_ca() -> None:
    script = _script()
    region = _california_region()
    view = script._validation_view(region, _california_countries())
    assert [c["iso"] for c in view["countries"]] == ["US-CA"]
    # Norway and Belgium validate against countries.json unchanged.
    norway = next(r for r in script.eligible_regions() if r.slug == "norway")
    assert script._validation_view(norway, _countries_payload())["countries"][0]["iso"] == "NO"


def test_real_california_region_json_matches_the_registry_block_and_is_to_confirm() -> None:
    countries_path = REPO_ROOT / "site" / "data" / "global" / "countries.json"
    path = REPO_ROOT / "site" / "data" / "california" / "region.json"
    if not countries_path.is_file() or not path.is_file():
        pytest.skip("countries.json or california/region.json absent")
    script = _script()
    region = _california_region()
    countries = json.loads(countries_path.read_text(encoding="utf-8"))
    block = next(r for r in countries["registry_regions"] if r["region"] == "california")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["iso"] == "US-CA"
    assert payload["stats"]["works_total"] == block["works_total"]
    assert payload["stats"]["first_year"] == block["first_year"]
    assert payload["works_by_year"] == series_block_of(block)
    assert validate_payload(payload, script._validation_view(region, countries)) == []
    assert [s["id"] for s in payload["sections"]] == list(SECTION_IDS)
    for section in payload["sections"]:
        for item in section["items"]:
            assert item["status"] == "to_confirm"
            assert item["note"].strip()
    # No US entry among the partner countries.
    assert all(p["iso"] != "US" for p in payload["partner_countries"])


def test_california_partition_registry_works_equal_the_registry_block() -> None:
    script = _script()
    if not (script.DEFAULT_REGIONS.is_file() and script.DEFAULT_WORKS.is_file()):
        pytest.skip("ignored partition absent")
    countries = json.loads(
        (REPO_ROOT / "site" / "data" / "global" / "countries.json").read_text(encoding="utf-8")
    )
    block = next(r for r in countries["registry_regions"] if r["region"] == "california")
    inputs = script._partition_inputs([_california_region()])
    assert len(inputs.registry_works) == block["works_total"]


def series_block_of(entry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"year": row["year"], "count": row["count"], "partial": bool(row.get("partial", False))}
        for row in entry["works_by_year"]
    ]
