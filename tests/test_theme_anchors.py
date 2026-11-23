"""Offline tests for BQ-S6 theme anchors (scripts/build_theme_anchors.py, tests/fixtures).

No test touches the network or reads .env. The live path is exercised with a fake budget and a
fake request. The cache-consistency test runs only where the ignored raw cache exists locally.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "theme_anchors.json"
RAW_CACHE = ROOT / "data" / "interim" / "theme_anchors_raw.json"
WORKS = ROOT / "data" / "processed" / "normalized" / "works.parquet"
SPEC_DOI_COUNT = 42
LEAD_OVERRIDE_DOI = "10.1038/s41893-025-01672-z"
RECORD_KEYS = {
    "theme",
    "doi",
    "openalex_id",
    "title",
    "year",
    "venue",
    "type",
    "found_in_openalex",
    "in_atlas_corpus",
    "plastics_primary",
    "plastics_evidence",
    "decided_by",
}


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_theme_anchors", ROOT / "scripts" / "build_theme_anchors.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # NamedTuples look the module up in sys.modules while it is being executed.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> Any:
    return _load_module()


@pytest.fixture(scope="module")
def fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _all_records(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for key in ("anchors", "excluded", "not_found") for row in fixture[key]]


def test_schema_and_top_level_fields(fixture: dict[str, Any]) -> None:
    assert set(fixture) == {
        "schema",
        "generated_at",
        "source",
        "note",
        "anchors",
        "excluded",
        "not_found",
        "venue_distribution",
        "max_venue_share",
    }
    assert fixture["schema"] == "theme-anchors-v1"
    assert fixture["source"] == "A3 §5.8 BQ-S6"
    assert fixture["note"] == "anchors, not an estimate"
    datetime.fromisoformat(fixture["generated_at"])


def test_every_anchor_is_plastics_primary_with_short_evidence(fixture: dict[str, Any]) -> None:
    assert fixture["anchors"], "anchor set must not be empty"
    for row in fixture["anchors"]:
        assert row["plastics_primary"] is True, row["doi"]
        assert row["found_in_openalex"] is True, row["doi"]
        evidence = row["plastics_evidence"]
        assert evidence.strip(), row["doi"]
        assert len(evidence.split()) <= 30, row["doi"]


def test_records_have_the_documented_keys_and_no_abstract(fixture: dict[str, Any]) -> None:
    for row in _all_records(fixture):
        assert "abstract" not in row, row["doi"]
        assert set(row) >= RECORD_KEYS, row["doi"]
    for row in fixture["excluded"]:
        assert row["exclusion_reason"].strip(), row["doi"]
    for row in fixture["not_found"]:
        assert row["found_in_openalex"] is False, row["doi"]
        assert row["miss_reason"].strip(), row["doi"]


def test_dois_are_lowercase_and_unique_across_anchors(fixture: dict[str, Any]) -> None:
    dois = [row["doi"] for row in fixture["anchors"]]
    assert all(doi == doi.lower() for doi in dois)
    assert len(dois) == len(set(dois))


def test_every_spec_doi_appears_exactly_once(script: Any, fixture: dict[str, Any]) -> None:
    spec = script.all_dois()
    assert len(spec) == SPEC_DOI_COUNT == len(set(spec))
    seen = Counter(row["doi"] for row in _all_records(fixture))
    assert set(seen) == set(spec)
    assert all(count == 1 for count in seen.values()), seen.most_common(3)


def test_each_record_keeps_its_spec_theme(script: Any, fixture: dict[str, Any]) -> None:
    theme_of = {doi: theme for theme, dois in script.THEMES.items() for doi in dois}
    for row in _all_records(fixture):
        assert row["theme"] == theme_of[row["doi"]], row["doi"]


def test_excluded_set_is_empty_after_the_lead_decision(fixture: dict[str, Any]) -> None:
    assert fixture["excluded"] == []
    for row in fixture["excluded"]:
        assert row["plastics_primary"] in (False, "unclear"), row["doi"]


def test_lead_override_is_recorded_on_its_anchor_row(script: Any, fixture: dict[str, Any]) -> None:
    rows = {row["doi"]: row for row in fixture["anchors"]}
    lead_row = rows[LEAD_OVERRIDE_DOI]
    assert lead_row["decided_by"] == "lead"
    assert lead_row["plastics_evidence"] == script.LEAD_DECISIONS[LEAD_OVERRIDE_DOI]["evidence"]
    assert lead_row["theme"] == "ssbd"
    assert {row["decided_by"] for doi, row in rows.items() if doi != LEAD_OVERRIDE_DOI} == {
        "builder"
    }
    assert sum(1 for row in fixture["anchors"] if row["theme"] == "ssbd") == 1


def test_venue_distribution_and_max_share(fixture: dict[str, Any]) -> None:
    anchors = fixture["anchors"]
    distribution = fixture["venue_distribution"]
    assert sum(distribution.values()) == len(anchors)
    venues = Counter(row["venue"] or "(no venue)" for row in anchors)
    assert distribution == dict(venues.most_common())
    assert fixture["max_venue_share"] == round(max(venues.values()) / len(anchors), 3)
    assert fixture["max_venue_share"] < 0.5


def test_build_url_is_one_plain_doi_filter(script: Any) -> None:
    dois = script.all_dois()
    url = script.build_url(dois)
    assert url.count("filter=doi%3A") == 1
    assert url.count("https%3A%2F%2Fdoi.org%2F") == SPEC_DOI_COUNT
    assert "search" not in url and "title_and_abstract" not in url
    assert "per_page=50" in url
    assert "select=" in url
    with pytest.raises(ValueError):
        script.build_url(dois + ["10.1000/extra"] * 9)


def test_abstract_text_rebuilds_inverted_index(script: Any) -> None:
    inverted = {"a": [0, 3], "plastic": [1], "waste": [2]}
    assert script.abstract_text(inverted) == "a plastic waste a"
    assert script.abstract_text(None) == ""
    assert script.abstract_text({}) == ""


def test_check_decision_rejects_bad_judgements(script: Any) -> None:
    title = "Plastic waste inputs from land into the ocean"
    abstract = "We estimate the mass of land-based plastic waste."
    good = script.Decision(True, "Plastic waste inputs from land into the ocean")
    assert script.check_decision("10.x/a", good, title, abstract) is None
    not_verbatim = script.Decision(True, "Microplastics in soil")
    assert "verbatim" in script.check_decision("10.x/a", not_verbatim, title, abstract)
    no_evidence = script.Decision(True, "")
    assert "evidence" in script.check_decision("10.x/a", no_evidence, title, abstract)
    too_long = script.Decision(True, " ".join(["plastic"] * 31))
    assert "longer" in script.check_decision("10.x/a", too_long, title, abstract)
    excluded_no_reason = script.Decision("unclear", "")
    assert "reason" in script.check_decision("10.x/a", excluded_no_reason, title, abstract)
    excluded = script.Decision("unclear", "", "central subject is chemistry")
    assert script.check_decision("10.x/a", excluded, title, abstract) is None


def test_build_payload_requires_a_judgement_for_each_found_work(
    script: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    doi = "10.1126/science.1260352"
    record = {
        "id": "https://openalex.org/W1",
        "doi": f"https://doi.org/{doi}",
        "display_name": "Plastic waste inputs from land into the ocean",
        "publication_year": 2015,
        "type": "article",
        "primary_location": {"source": {"display_name": "Science"}},
        "abstract_inverted_index": None,
    }
    cache = {"fetched_at": "2026-11-22T00:00:00+00:00", "response": {"results": [record]}}
    monkeypatch.setattr(script, "DECISIONS", {})
    with pytest.raises(script.BuildError, match="no plastics judgement"):
        script.build_payload(cache, set(), set())

    monkeypatch.setattr(
        script,
        "DECISIONS",
        {doi: script.Decision(True, "Plastic waste inputs from land into the ocean")},
    )
    payload = script.build_payload(cache, set(), set())
    assert [row["doi"] for row in payload["anchors"]] == [doi]
    assert payload["anchors"][0]["in_atlas_corpus"] is False
    assert payload["anchors"][0]["openalex_id"] == "W1"
    assert len(payload["not_found"]) == SPEC_DOI_COUNT - 1


class _FakeBudget:
    cost_per_credit_usd = Decimal("0.0001")

    def reserve_error(self, *, cost_usd: Decimal, credits: Decimal) -> str | None:
        return "daily limit reached"


def test_live_is_refused_by_the_budget_guard(
    script: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def no_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("OpenAlex must not be called when the guard refuses")

    monkeypatch.setattr(script, "resolve_openalex_budget", lambda: _FakeBudget())
    monkeypatch.setattr(script, "_request_json", no_call)
    raw = tmp_path / "theme_anchors_raw.json"
    code = script.main(["--live", "--raw", str(raw), "--usage-log", str(tmp_path / "u.jsonl")])
    assert code == 1
    assert not raw.exists()


def test_live_does_not_overwrite_an_existing_cache(
    script: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def no_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("an existing cache must block a second paid call")

    monkeypatch.setattr(script, "_request_json", no_call)
    raw = tmp_path / "theme_anchors_raw.json"
    raw.write_text("{}", encoding="utf-8")
    code = script.main(["--live", "--raw", str(raw), "--usage-log", str(tmp_path / "u.jsonl")])
    assert code == 1
    assert raw.read_text(encoding="utf-8") == "{}"


def test_offline_build_needs_a_cache(script: Any, tmp_path: Path) -> None:
    code = script.main(["--raw", str(tmp_path / "missing.json"), "--output", str(tmp_path / "f")])
    assert code == 1


@pytest.mark.skipif(not RAW_CACHE.exists() or not WORKS.exists(), reason="needs local raw cache")
def test_committed_fixture_matches_the_local_cache(script: Any, fixture: dict[str, Any]) -> None:
    cache = json.loads(RAW_CACHE.read_text(encoding="utf-8"))
    work_ids, dois = script.load_corpus(WORKS)
    rebuilt = script.build_payload(cache, work_ids, dois)
    assert rebuilt == fixture
