"""PLAT-4b slice 3: Tier B country aggregates from the global partition (synthetic tables only)."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build.tier_b import (
    SCHEMA_VERSION,
    TIER_B_MIN_WORKS,
    build,
    encode,
    validate,
)
from atlas.ingest.global_partition import (
    SCREENING_UNSCREENED,
    WORK_REGIONS_SCHEMA,
    WORKS_SCHEMA,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_tier_b.py"
GENERATED = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
AUTHOR_KEY_PARTS = ("author", "person", "orcid", "abstract")


def _work(
    index: int,
    *,
    year: int | None,
    pmid: str | None = None,
    retracted: bool = False,
    topic: int | None = None,
) -> dict[str, Any]:
    topic_id = None if topic is None else f"T{topic}"
    return {
        "work_id": f"W{index}",
        "doi": None,
        "pmid": pmid,
        "title": "synthetic title",
        "publication_year": year,
        "publication_date": None if year is None else f"{year}-06-01",
        "type": "article",
        "language": "en",
        "primary_topic_id": topic_id,
        "primary_topic_name": None if topic is None else f"Topic {topic}",
        "primary_topic_field": None,
        "is_retracted": retracted,
        "cited_by_count": 0,
        "screening_status": SCREENING_UNSCREENED,
        "query_version": "plastic-test",
        "query_hash": "hash-test",
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    """US: 50 works (tier B at the threshold). CN: 49 (tier C). DE: 1. One registry region."""
    works: list[dict[str, Any]] = []
    regions: list[dict[str, str]] = []
    index = 0

    def add(codes: Sequence[str], region_codes: Sequence[str] = (), **fields: Any) -> None:
        nonlocal index
        index += 1
        works.append(_work(index, **fields))
        for code in codes:
            regions.append(
                {
                    "work_id": f"W{index}",
                    "region_kind": "country",
                    "region_code": code,
                    "basis": "institution_country",
                }
            )
        for code in region_codes:
            regions.append(
                {
                    "work_id": f"W{index}",
                    "region_kind": "registry_region",
                    "region_code": code,
                    "basis": "registry_predicate",
                }
            )

    # US: 20 in 2020, 25 in 2025, 3 in the partial current year, 1 before 1970, 1 undated.
    for _ in range(20):
        add(["US"], year=2020, pmid="1", topic=2)
    for position in range(25):
        add(["US"], year=2025, topic=1 if position % 2 else 2, retracted=position == 0)
    for _ in range(3):
        add(["US"], year=2026, topic=3)
    add(["US"], year=1960, topic=4)
    add(["US"], year=None)
    # CN: 49 works; one retracted; one of them also matches the registry region.
    for position in range(49):
        add(
            ["CN"],
            ["examplepred"] if position < 2 else [],
            year=2025,
            pmid="9" if position == 0 else None,
            retracted=position == 1,
            topic=5,
        )
    # DE: one partial-year work, no topic.
    add(["DE"], year=2026)

    works_path = tmp_path / "works.parquet"
    regions_path = tmp_path / "work_regions.parquet"
    pq.write_table(pa.Table.from_pylist(works, schema=WORKS_SCHEMA), works_path)
    pq.write_table(pa.Table.from_pylist(regions, schema=WORK_REGIONS_SCHEMA), regions_path)
    return works_path, regions_path


@pytest.fixture
def payload(tmp_path: Path) -> dict[str, Any]:
    works_path, regions_path = _fixture(tmp_path)
    return build(works_path, regions_path, generated_at=GENERATED, names={"US": "United States"})


def _country(payload: Mapping[str, Any], iso: str) -> dict[str, Any]:
    return next(entry for entry in payload["countries"] if entry["iso"] == iso)


def test_per_country_counts_and_years(payload: dict[str, Any]) -> None:
    us = _country(payload, "US")
    assert us["works_total"] == 50
    assert us["works_with_pmid"] == 20
    assert us["first_year"] == 1960
    assert us["works_outside_years"] == 2  # one before 1970, one undated
    years = {row["year"]: row["count"] for row in us["works_by_year"]}
    assert years[2020] == 20
    assert years[2025] == 25
    assert years[1970] == 0
    assert sum(years.values()) == 48
    # Retractions are not published (absent from the list results; see RETRACTIONS_NOTE).
    assert "works_retracted" not in us and "share_retracted" not in us


def test_partial_current_year_is_flagged(payload: dict[str, Any]) -> None:
    us = _country(payload, "US")
    assert payload["years"] == {"first": 1970, "last_complete": 2025, "partial": 2026}
    assert us["works_by_year"][-1] == {"year": 2026, "count": 3, "partial": True}
    assert us["works_by_year"][-2] == {"year": 2025, "count": 25}
    assert sum(1 for row in us["works_by_year"] if row.get("partial")) == 1
    assert us["works_by_year"][0]["year"] == 1970


def test_tier_threshold(payload: dict[str, Any]) -> None:
    assert TIER_B_MIN_WORKS == 50
    assert _country(payload, "US")["tier"] == "B"
    assert _country(payload, "CN")["tier"] == "C"
    assert _country(payload, "DE")["tier"] == "C"
    assert payload["tier_counts"] == {"B": 1, "C": 2}


def test_top_topics_order_and_limit(payload: dict[str, Any]) -> None:
    us = _country(payload, "US")
    topics = us["top_primary_topics"]
    assert [topic["id"] for topic in topics] == ["T2", "T1", "T3", "T4"]
    assert [topic["count"] for topic in topics] == [33, 12, 3, 1]
    assert topics[0] == {"id": "T2", "name": "Topic 2", "count": 33}
    assert len(payload["countries"][0]["top_primary_topics"]) <= 10


def test_top_topics_ties_break_on_id(payload: dict[str, Any]) -> None:
    cn = _country(payload, "CN")
    assert cn["top_primary_topics"] == [{"id": "T5", "name": "Topic 5", "count": 49}]
    assert _country(payload, "DE")["top_primary_topics"] == []


def test_names_fall_back_to_code(payload: dict[str, Any]) -> None:
    assert _country(payload, "US")["name"] == "United States"
    assert _country(payload, "CN")["name"] == "CN"


def test_countries_sorted_and_registry_block(payload: dict[str, Any]) -> None:
    isos = [entry["iso"] for entry in payload["countries"]]
    assert isos == sorted(isos) == ["CN", "DE", "US"]
    (region,) = payload["registry_regions"]
    assert region["region"] == "examplepred"
    assert region["matched_by"] == "region_predicate"
    assert region["works_total"] == 2
    assert region["tier"] == "C"
    assert region["works_by_year"][-2] == {"year": 2025, "count": 2}


def _blocks(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [payload, *payload["countries"], *payload["registry_regions"]]


def test_every_block_is_labelled_unscreened(payload: dict[str, Any]) -> None:
    for block in _blocks(payload):
        assert block["screening_status"] == SCREENING_UNSCREENED
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "unscreened" in payload["what_this_is_and_is_not"]["is"]


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.extend(_walk_keys(item))
    return keys


def test_no_person_level_keys(payload: dict[str, Any]) -> None:
    keys = [key.lower() for key in _walk_keys(payload)]
    assert keys
    for key in keys:
        assert not any(part in key for part in AUTHOR_KEY_PARTS), key


def test_validate_passes_and_catches_problems(payload: dict[str, Any]) -> None:
    assert validate(payload) == []
    broken = json.loads(json.dumps(payload))
    _country(broken, "US")["screening_status"] = "screened"
    _country(broken, "CN")["tier"] = "B"
    _country(broken, "DE")["works_outside_years"] = 5
    problems = validate(broken)
    assert any("unscreened" in problem for problem in problems)
    assert any("tier" in problem for problem in problems)
    assert any("year counts" in problem for problem in problems)
    broken["countries"][0]["author_names"] = ["x"]
    assert any("person-level" in problem for problem in validate(broken))


def test_encode_is_deterministic_and_round_trips(tmp_path: Path, payload: dict[str, Any]) -> None:
    text = encode(payload)
    assert text.endswith("}\n")
    assert "\r" not in text
    assert json.loads(text) == payload
    works_path, regions_path = _fixture(tmp_path)
    again = build(works_path, regions_path, generated_at=GENERATED, names={"US": "United States"})
    assert encode(again) == text


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("build_tier_b_cli", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_detects_stale_file_and_skips_without_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli = _load_cli()
    works_path, regions_path = _fixture(tmp_path)
    output = tmp_path / "countries.json"
    names = tmp_path / "absent_explore.json"
    base = ["--works", str(works_path), "--regions", str(regions_path)]
    assert cli.main([*base, "--names", str(names), "--output", str(output)]) == 0
    assert cli.main([*base, "--names", str(names), "--output", str(output), "--check"]) == 0

    # A changed input (no region rows left) makes the committed copy stale.
    pq.write_table(pa.Table.from_pylist([], schema=WORK_REGIONS_SCHEMA), regions_path)
    capsys.readouterr()
    assert cli.main([*base, "--names", str(names), "--output", str(output), "--check"]) == 1
    assert "stale" in capsys.readouterr().out

    # Without the ignored inputs the staleness check is skipped and the file still validates.
    absent = ["--works", str(tmp_path / "none.parquet"), "--regions", str(tmp_path / "none2")]
    assert cli.main([*absent, "--output", str(output), "--check"]) == 0
    assert "SKIP" in capsys.readouterr().out


def test_check_fails_on_invalid_committed_file(tmp_path: Path) -> None:
    cli = _load_cli()
    output = tmp_path / "countries.json"
    output.write_text(json.dumps({"schema_version": "other"}), encoding="utf-8")
    absent = ["--works", str(tmp_path / "none.parquet"), "--regions", str(tmp_path / "none2")]
    assert cli.main([*absent, "--output", str(output), "--check"]) == 1


def test_committed_countries_json_is_valid() -> None:
    committed = REPO_ROOT / "site" / "data" / "global" / "countries.json"
    if not committed.is_file():
        pytest.skip("countries.json not built yet")
    payload = json.loads(committed.read_text(encoding="utf-8"))
    assert validate(payload) == []
    assert payload["schema_version"] == SCHEMA_VERSION
    assert committed.stat().st_size < 1_500_000
