"""Offline tests for the global-denominator series (BQ-2.1, BQ-2.2).

Tiny in-memory and tmp_path fixtures only. Nothing here reads the data/ tree, site/data or the
network. The committed-config tests read config/denominator_series.yml and config/queries.yml only.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from atlas.analytics.denominators import (
    POLLUTION_CORE_PATH,
    QUERY_ROUTES,
    build_series,
    cache_key,
    cache_rows,
    corpus_rows,
    fetch_series_filters,
    filter_digest,
    load_corpus_records,
    load_denominator_cache,
    load_pollution_core,
    load_published_works,
    load_series_config,
    render_payload,
    resolve_cache_entries,
    route_family,
    trend_rows,
    validate_ratio_pairs,
)
from atlas.query import load_query_config

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_denominator_series.py"
QUERIES = ROOT / "config" / "queries.yml"
AS_OF = date(2026, 11, 22)
ARTICLE_UNIT = (
    "OpenAlex records of type article or review by publication year; exclude_types removed; "
    "duplicates not collapsed; retracted-flagged records included"
)
UNIT = (
    "OpenAlex records by publication year; exclude_types removed; duplicates not collapsed; "
    "retracted-flagged records included"
)
CURATED = "curated published works by publication year; one row per work"
QUERY_RUN = "openalex-works-20261110T010203Z"


def _entry(series_id: str, **overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": series_id,
        "label": f"fixture {series_id}",
        "counting_unit": UNIT,
        "source": "fixture",
        "scope": "global",
        "status": "available",
        "compute": "trend_global",
        "comparable_with": [],
        "beside_only": False,
        "note": "fixture",
    }
    entry.update(overrides)
    return entry


def _config(directory: Path, entries: list[dict[str, Any]]) -> Path:
    path = directory / "series.yml"
    path.write_text(yaml.safe_dump({"series": entries}, sort_keys=False), encoding="utf-8")
    return path


def _trend(by_year: dict[int, int], version: str = "plastic-v3.1") -> dict[str, Any]:
    return {
        "schema_version": "em7.v1",
        "query_version": version,
        "fetched_at": "2026-11-12T18:26:53+00:00",
        "source": "OpenAlex group_by publication_year",
        "by_year": {str(year): count for year, count in by_year.items()},
    }


def _record(route: str, year: int | None, *, ca: bool = True, retracted: bool = False) -> dict:
    return {"route": route, "year": year, "ca_any_author": ca, "is_retracted": retracted}


def _work(year: int | None, plastic: Any, *, retracted: bool = False) -> dict[str, Any]:
    return {"year": year, "plastic_related": plastic, "is_retracted": retracted}


def _rows(payload: dict[str, Any], sid: str) -> dict[int, dict[str, Any]]:
    return {row["year"]: row for row in payload["series"][sid]["years"]}


# --- config and ratio rules -------------------------------------------------------------------


def test_committed_config_declares_the_expected_series_and_ratio_pairs():
    specs = load_series_config(ROOT / "config" / "denominator_series.yml")

    assert {sid: spec.status for sid, spec in specs.items()} == {
        "A": "available",
        "A-article_review": "available",
        "B": "available",
        "B-article_review": "available",
        "B2": "waits_for",
        "C": "available",
        "D": "available",
    }
    assert specs["B2"].waits_for == "BQ-S3"
    assert specs["A"].cache_series == "A-all"
    assert specs["B"].cache_series == "B-all"
    assert specs["A"].counting_unit == specs["B"].counting_unit == specs["C"].counting_unit
    assert specs["A-article_review"].counting_unit == specs["B-article_review"].counting_unit
    assert specs["A"].counting_unit != specs["A-article_review"].counting_unit
    assert {frozenset(pair) for pair in validate_ratio_pairs(specs)} == {
        frozenset({"A", "B"}),
        frozenset({"A", "C"}),
        frozenset({"A-article_review", "B-article_review"}),
    }
    for first, second in validate_ratio_pairs(specs):
        assert specs[first].sensitivity == specs[second].sensitivity
    assert specs["D"].beside_only and specs["D"].comparable_with == ()
    assert all("D" not in spec.comparable_with for spec in specs.values())


def test_unit_mismatch_ratio_raises(tmp_path):
    path = _config(
        tmp_path,
        [
            _entry("A", comparable_with=["C"]),
            _entry("C", counting_unit=CURATED, comparable_with=["A"], scope="california"),
        ],
    )
    with pytest.raises(ValueError, match="not like-for-like: counting_unit differs"):
        load_series_config(path)


def test_one_sided_comparable_with_raises(tmp_path):
    path = _config(tmp_path, [_entry("A", comparable_with=["C"]), _entry("C", scope="california")])
    with pytest.raises(ValueError, match="does not list it back"):
        load_series_config(path)


def test_beside_only_series_is_never_divided(tmp_path):
    path = _config(
        tmp_path,
        [
            _entry("A", comparable_with=["D"]),
            _entry(
                "D",
                counting_unit=UNIT,
                scope="california",
                compute="published_plastic_related",
                comparable_with=["A"],
                beside_only=True,
            ),
        ],
    )
    with pytest.raises(ValueError, match="never divided"):
        load_series_config(path)


def test_bad_status_and_missing_wait_task_raise(tmp_path):
    with pytest.raises(ValueError, match="unknown status"):
        load_series_config(_config(tmp_path, [_entry("A", status="maybe")]))
    pending = _entry("B", status="pending_fetch", compute=None)
    with pytest.raises(ValueError, match="needs a waits_for task"):
        load_series_config(_config(tmp_path, [pending]))


# --- building series --------------------------------------------------------------------------


def test_pending_series_are_listed_with_status_and_not_counted(tmp_path):
    specs = load_series_config(
        _config(
            tmp_path,
            [
                _entry("A", comparable_with=["B"]),
                _entry(
                    "B",
                    status="pending_fetch",
                    compute=None,
                    waits_for="BQ-2.2",
                    comparable_with=["A"],
                ),
            ],
        )
    )
    payload = build_series(
        specs,
        trend_global=_trend({2025: 10}),
        as_of=AS_OF,
        expected_query_version="plastic-v3.1",
    )

    assert "B" not in payload["series"]
    assert payload["not_computed"]["B"]["status"] == "pending_fetch"
    assert payload["not_computed"]["B"]["waits_for"] == "BQ-2.2"
    assert payload["ratio_pairs"] == []


def test_available_series_without_input_raises(tmp_path):
    specs = load_series_config(_config(tmp_path, [_entry("A")]))
    with pytest.raises(ValueError, match="trend_global input is missing"):
        build_series(specs, trend_global=None, as_of=AS_OF)


def test_trend_for_another_query_version_raises(tmp_path):
    specs = load_series_config(_config(tmp_path, [_entry("A")]))
    with pytest.raises(ValueError, match="active query is 'plastic-v3.1'"):
        build_series(
            specs,
            trend_global=_trend({2025: 10}, version="plastic-v3.0"),
            as_of=AS_OF,
            expected_query_version="plastic-v3.1",
        )


def test_partial_year_flag_marks_as_of_year_and_later(tmp_path):
    specs = load_series_config(_config(tmp_path, [_entry("A")]))
    payload = build_series(
        specs,
        trend_global=_trend({2024: 5, 2025: 7, 2026: 3, 2027: 1}),
        as_of=AS_OF,
        expected_query_version="plastic-v3.1",
    )

    rows = _rows(payload, "A")
    assert payload["last_complete_year"] == 2025
    assert [rows[y]["partial_year"] for y in (2024, 2025, 2026, 2027)] == [
        False,
        False,
        True,
        True,
    ]
    assert rows[2026]["retracted"] is None  # A cannot split retractions


def test_trend_rows_keep_all_types_and_count_as_given():
    rows = trend_rows(_trend({2000: 4}), as_of=AS_OF, expected_query_version="plastic-v3.1")
    assert rows == [{"year": 2000, "count": 4, "retracted": None, "partial_year": False}]


def test_corpus_counts_query_route_california_records_and_separates_retractions():
    records = [
        _record(QUERY_RUN, 2020),
        _record(QUERY_RUN, 2020, retracted=True),
        _record(QUERY_RUN, 2020, ca=False),  # not California: excluded, still in route totals
        _record("orcid-doi-ingest-2026-11-10", 2020),  # local text rule, not a query route
        _record(QUERY_RUN, 2021),
        _record("europepmc-audit-2026-11-10", 2021),  # search AND DOI: a query route
        _record("escholarship-ingest", 2021),  # location AND query: a query route
    ]
    rows, routes, undated = corpus_rows(records, as_of=AS_OF)
    by_year = {row["year"]: row for row in rows}

    assert by_year[2020]["count"] == 2
    assert by_year[2020]["retracted"] == 1
    assert by_year[2020]["other_route"] == 1
    assert by_year[2021]["count"] == 3
    assert by_year[2021]["other_route"] == 0
    assert routes == {
        "escholarship-ingest": 1,
        "europepmc-audit": 1,
        "openalex-works": 4,
        "orcid-doi-ingest": 1,
    }
    assert undated == 0


def test_route_family_marks_only_the_query_routes():
    query_runs = (QUERY_RUN, "europepmc-audit-2026-11-10", "escholarship-ingest")
    assert {route_family(run) for run in query_runs} == QUERY_ROUTES
    assert route_family("orcid-doi-ingest-2026-11-10") not in QUERY_ROUTES
    assert route_family("ror-researcher-doi-ingest-2026-11-10") not in QUERY_ROUTES


def test_published_counts_plastic_related_only_with_retractions_separate(tmp_path):
    specs = load_series_config(
        _config(
            tmp_path,
            [
                _entry(
                    "D",
                    counting_unit=CURATED,
                    scope="california",
                    compute="published_plastic_related",
                    beside_only=True,
                )
            ],
        )
    )
    works = [
        _work(2023, True, retracted=True),
        _work(2023, True),
        _work(2023, False),
        _work(2023, None),
        _work(2024, True),
    ]
    payload = build_series(specs, trend_global=None, published_works=works, as_of=AS_OF)
    rows = _rows(payload, "D")

    assert rows[2023]["count"] == 2
    assert rows[2023]["retracted"] == 1
    assert rows[2024]["count"] == 1
    assert rows[2024]["retracted"] == 0
    assert payload["series"]["D"]["beside_only"] is True


def test_zero_fill_aligns_series_over_the_shared_year_range(tmp_path):
    specs = load_series_config(
        _config(
            tmp_path,
            [
                _entry("A", comparable_with=["C"]),
                _entry(
                    "C",
                    scope="california",
                    compute="corpus_query_route",
                    comparable_with=["A"],
                ),
            ],
        )
    )
    payload = build_series(
        specs,
        trend_global=_trend({2000: 4, 2002: 6}),
        corpus_records=[_record(QUERY_RUN, 2001)],
        as_of=AS_OF,
        expected_query_version="plastic-v3.1",
    )

    assert [row["year"] for row in payload["series"]["A"]["years"]] == [2000, 2001, 2002]
    assert _rows(payload, "C")[2000]["count"] == 0
    assert _rows(payload, "C")[2000]["retracted"] == 0
    assert _rows(payload, "A")[2001]["count"] == 0
    assert payload["ratio_pairs"] == [["A", "C"]]


def test_identical_inputs_render_identical_text(tmp_path):
    specs = load_series_config(_config(tmp_path, [_entry("A")]))
    kwargs = {
        "trend_global": _trend({2025: 3}),
        "as_of": AS_OF,
        "expected_query_version": "plastic-v3.1",
    }
    assert render_payload(build_series(specs, **kwargs)) == render_payload(
        build_series(specs, **kwargs)
    )


def test_route_family_strips_the_run_timestamp():
    assert route_family(QUERY_RUN) == "openalex-works"
    assert route_family("europepmc-audit-2026-11-10") == "europepmc-audit"
    assert route_family("escholarship-ingest") == "escholarship-ingest"
    assert route_family("") == "unknown"


# --- file loaders on tiny parquet and JSON fixtures -------------------------------------------

WORKS_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("ca_any_author", pa.bool_()),
        ("is_retracted", pa.bool_()),
        ("duplicate_work_ids", pa.list_(pa.string())),
    ]
)
RAW_SCHEMA = pa.schema(
    [
        ("openalex_id", pa.string()),
        ("publication_year", pa.int64()),
        ("source_run_id", pa.string()),
        ("raw_json", pa.string()),
    ]
)


def _raw(openalex_id: str, run: str, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "openalex_id": openalex_id,
        "publication_year": 2022,
        "source_run_id": run,
        "raw_json": json.dumps({"id": openalex_id, **extra}),
    }


def test_load_corpus_records_counts_duplicates_as_records(tmp_path):
    works = tmp_path / "works.parquet"
    raw = tmp_path / "works_raw.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "work_id": "W1",
                    "ca_any_author": True,
                    "is_retracted": False,
                    "duplicate_work_ids": ["W2"],
                },
                {
                    "work_id": "W3",
                    "ca_any_author": False,
                    "is_retracted": False,
                    "duplicate_work_ids": [],
                },
            ],
            schema=WORKS_SCHEMA,
        ),
        works,
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                _raw("W1", QUERY_RUN, {}),
                _raw("W2", "orcid-doi-ingest-2026-11-10", {"is_retracted": True}),
                _raw("W3", QUERY_RUN, {}),
                _raw("W9", QUERY_RUN, {}),  # no corpus work (for example suppressed): skipped
            ],
            schema=RAW_SCHEMA,
        ),
        raw,
    )
    records = load_corpus_records(works, raw)

    assert len(records) == 3
    duplicate = next(r for r in records if r["route"].startswith("orcid"))
    assert duplicate["ca_any_author"] is True  # takes the kept work's CA flag
    assert duplicate["is_retracted"] is True  # a duplicate keeps its own raw flag
    rows, _, _ = corpus_rows(records, as_of=AS_OF)
    assert rows == [
        {"year": 2022, "count": 1, "retracted": 0, "partial_year": False, "other_route": 1}
    ]


def test_load_published_works_joins_retraction_and_rejects_unknown_ids(tmp_path):
    index = tmp_path / "index.json"
    works = tmp_path / "works.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [{"work_id": "W1", "is_retracted": True}],
            schema=pa.schema([("work_id", pa.string()), ("is_retracted", pa.bool_())]),
        ),
        works,
    )
    index.write_text(
        json.dumps({"works": [{"work_id": "W1", "year": 2024, "plastic_related": True}]}),
        encoding="utf-8",
    )
    assert load_published_works(index, works) == [
        {"year": 2024, "plastic_related": True, "is_retracted": True}
    ]

    index.write_text(
        json.dumps({"works": [{"work_id": "W404", "year": 2024, "plastic_related": True}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not in the normalized works table"):
        load_published_works(index, works)


# --- CLI wiring (temp inputs; the committed outputs are never touched) ------------------------


def _load_script():
    spec = importlib.util.spec_from_file_location("build_denominator_series", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cache_entry(series_id: str, by_year: dict[int, int], **overrides: Any) -> dict[str, Any]:
    """A cache entry keyed the way scripts/fetch_denominator_series.py keys it (committed query)."""

    config = load_query_config(QUERIES)
    filters = fetch_series_filters(config, series_id)
    entry: dict[str, Any] = {
        "series_id": series_id,
        "query_version": config["version"],
        "filter_digest": filter_digest(filters),
        "filter": ",".join(filters),
        "fetched_at": "2026-11-22T10:00:00+00:00",
        "source": "OpenAlex group_by publication_year",
        "by_year": {str(year): count for year, count in by_year.items()},
        "stale": False,
        "stale_reason": None,
    }
    entry.update(overrides)
    return entry


def _cache_file(path: Path, entries: list[dict[str, Any]]) -> Path:
    payload = {
        "schema_version": "denominator_series_cache.v1",
        "source": "OpenAlex group_by publication_year",
        "entries": {
            cache_key(e["series_id"], e["query_version"], e["filter_digest"]): e for e in entries
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cli_writes_then_checks_then_detects_staleness(tmp_path, monkeypatch):
    script = _load_script()
    cache = _cache_file(
        tmp_path / "denominator_series_cache.json",
        [
            _cache_entry("A-all", {2024: 5, 2025: 7}),
            _cache_entry("A-article_review", {2024: 3, 2025: 4}),
            _cache_entry("B-all", {2024: 2, 2025: 3}),
            _cache_entry("B-article_review", {2024: 1, 2025: 2}),
        ],
    )
    index = tmp_path / "index.json"
    works = tmp_path / "works.parquet"
    raw = tmp_path / "works_raw.parquet"
    out = tmp_path / "out" / "denominator_series.json"
    index.write_text(json.dumps({"works": []}), encoding="utf-8")
    pq.write_table(pa.Table.from_pylist([], schema=WORKS_SCHEMA), works)
    pq.write_table(pa.Table.from_pylist([], schema=RAW_SCHEMA), raw)
    monkeypatch.setattr(script, "CACHE", cache)
    monkeypatch.setattr(script, "INDEX", index)
    monkeypatch.setattr(script, "WORKS", works)
    monkeypatch.setattr(script, "RAW", raw)
    args = ["--as-of", "2026-11-22", "--output", str(out)]

    assert script.main(args) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["series"]["A"]["years"][-1]["year"] == 2025
    assert payload["series"]["B"]["years"][-1]["count"] == 3
    assert payload["series"]["B-article_review"]["sensitivity"] == "article_review"
    assert payload["series"]["B"]["cache"]["stale"] is False
    assert set(payload["not_computed"]) == {"B2"}
    assert ["A", "B"] in payload["ratio_pairs"]
    assert ["A-article_review", "B-article_review"] in payload["ratio_pairs"]
    assert payload["inputs"]["denominator_cache"]["path"].endswith("denominator_series_cache.json")
    assert script.main(["--check", *args]) == 0

    out.write_text(
        out.read_text(encoding="utf-8").replace('"count": 7', '"count": 8'), encoding="utf-8"
    )
    assert script.main(["--check", *args]) == 1


def test_cli_fails_without_a_cache_entry_for_a_series(tmp_path, monkeypatch, capsys):
    script = _load_script()
    cache = _cache_file(
        tmp_path / "denominator_series_cache.json", [_cache_entry("A-all", {2025: 7})]
    )
    index = tmp_path / "index.json"
    works = tmp_path / "works.parquet"
    raw = tmp_path / "works_raw.parquet"
    index.write_text(json.dumps({"works": []}), encoding="utf-8")
    pq.write_table(pa.Table.from_pylist([], schema=WORKS_SCHEMA), works)
    pq.write_table(pa.Table.from_pylist([], schema=RAW_SCHEMA), raw)
    monkeypatch.setattr(script, "CACHE", cache)
    monkeypatch.setattr(script, "INDEX", index)
    monkeypatch.setattr(script, "WORKS", works)
    monkeypatch.setattr(script, "RAW", raw)
    args = ["--as-of", "2026-11-22", "--output", str(tmp_path / "out.json")]

    assert script.main(args) == 1
    err = capsys.readouterr().err
    assert "has no A-article_review entry" in err
    assert "run scripts/fetch_denominator_series.py" in err


def test_cli_check_skips_when_inputs_are_absent(tmp_path, monkeypatch):
    script = _load_script()
    monkeypatch.setattr(script, "CACHE", tmp_path / "missing.json")
    output = str(tmp_path / "x.json")
    assert script.main(["--check", "--output", output]) == 0
    assert script.main(["--output", output]) == 1


# --- BQ-2.2: cache-backed series and their guards ---------------------------------------------


def _cache_specs(tmp_path: Path):
    """A and B as cache-backed series with the same counting unit (the like-for-like pair)."""

    return load_series_config(
        _config(
            tmp_path,
            [
                _entry(
                    "A",
                    comparable_with=["B"],
                    compute="denominator_cache",
                    cache_series="A-all",
                ),
                _entry(
                    "B",
                    comparable_with=["A"],
                    compute="denominator_cache",
                    cache_series="B-all",
                ),
            ],
        )
    )


def test_cache_rows_are_counts_with_no_retraction_split():
    rows = cache_rows({"series_id": "B-all", "by_year": {"2025": 3, "2026": 1}}, as_of=AS_OF)
    assert rows == [
        {"year": 2025, "count": 3, "retracted": None, "partial_year": False},
        {"year": 2026, "count": 1, "retracted": None, "partial_year": True},
    ]


@pytest.mark.parametrize("bad", [{"2025": -1}, {"2025": 1.5}, {"2025": True}, {"2025": "3"}])
def test_cache_counts_must_be_non_negative_integers(bad):
    with pytest.raises(ValueError, match="non-negative integer"):
        cache_rows({"series_id": "A-all", "by_year": bad}, as_of=AS_OF)


def test_resolve_cache_entries_needs_the_active_query_version_and_filters(tmp_path):
    specs = _cache_specs(tmp_path)
    config = load_query_config(QUERIES)
    cache = {"entries": {}}
    entry_a = _cache_entry("A-all", {2025: 10})
    cache["entries"][cache_key("A-all", config["version"], entry_a["filter_digest"])] = entry_a

    with pytest.raises(ValueError, match="no B-all entry"):
        resolve_cache_entries(specs, cache, query_config=config)

    entry_b = _cache_entry("B-all", {2025: 4})
    cache["entries"][cache_key("B-all", config["version"], entry_b["filter_digest"])] = entry_b
    resolved = resolve_cache_entries(specs, cache, query_config=config)
    assert resolved["A"]["by_year"] == {"2025": 10}
    assert resolved["B"]["by_year"] == {"2025": 4}

    # Another query version, or a changed term, finds no entry: nothing falls back to it.
    with pytest.raises(ValueError, match="no A-all entry"):
        resolve_cache_entries(specs, cache, query_config={**config, "version": "plastic-v3.2"})
    changed = {**config, "core_terms": [*config["core_terms"], "plastic cups"]}
    with pytest.raises(ValueError, match="no A-all entry"):
        resolve_cache_entries(specs, cache, query_config=changed)


def test_stale_flags_and_age_flow_into_the_output(tmp_path):
    specs = _cache_specs(tmp_path)
    config = load_query_config(QUERIES)
    aged = _cache_entry("A-all", {2025: 10}, fetched_at="2026-10-01T00:00:00+00:00")
    refused = _cache_entry("B-all", {2025: 4}, stale=True, stale_reason="OpenAlex HTTP 429")
    fresh_cache = {
        "entries": {
            cache_key("A-all", config["version"], aged["filter_digest"]): aged,
            cache_key("B-all", config["version"], refused["filter_digest"]): refused,
        }
    }
    entries = resolve_cache_entries(specs, fresh_cache, query_config=config)

    payload = build_series(
        specs,
        denominator_entries=entries,
        as_of=AS_OF,
        expected_query_version=config["version"],
    )

    assert payload["query_version"] == config["version"]
    assert payload["series"]["A"]["cache"]["stale"] is True
    assert payload["series"]["A"]["cache"]["stale_reason"] == (
        "fetched 30 or more days before the as-of date"
    )
    assert payload["series"]["B"]["cache"] == {
        "query_version": config["version"],
        "filter_digest": refused["filter_digest"],
        "fetched_at": "2026-11-22T10:00:00+00:00",
        "stale": True,
        "stale_reason": "OpenAlex HTTP 429",
    }
    assert payload["series"]["B"]["retractions"].startswith("not separated")


def test_a_fresh_unflagged_entry_is_not_stale(tmp_path):
    specs = _cache_specs(tmp_path)
    fresh = _cache_entry("A-all", {2025: 10})
    payload = build_series(
        specs,
        denominator_entries={"A": fresh, "B": _cache_entry("B-all", {2025: 4})},
        as_of=AS_OF,
        expected_query_version="plastic-v3.1",
    )
    assert payload["series"]["A"]["cache"]["stale"] is False
    assert payload["series"]["A"]["cache"]["stale_reason"] is None


def test_cache_series_without_an_entry_raises(tmp_path):
    with pytest.raises(ValueError, match="denominator cache entry is missing"):
        build_series(_cache_specs(tmp_path), as_of=AS_OF)


def test_cache_entry_for_another_query_version_raises(tmp_path):
    entries = {
        "A": _cache_entry("A-all", {2025: 1}, query_version="plastic-v3.0"),
        "B": _cache_entry("B-all", {2025: 1}),
    }
    with pytest.raises(ValueError, match="active query is 'plastic-v3.1'"):
        build_series(
            _cache_specs(tmp_path),
            denominator_entries=entries,
            as_of=AS_OF,
            expected_query_version="plastic-v3.1",
        )


def test_ratio_guard_refuses_a_type_sensitivity_mismatch(tmp_path):
    with pytest.raises(ValueError, match="crosses type sensitivity"):
        load_series_config(
            _config(
                tmp_path,
                [
                    _entry("A", comparable_with=["B"]),
                    _entry(
                        "B",
                        comparable_with=["A"],
                        sensitivity="article_review",
                        counting_unit=UNIT,
                    ),
                ],
            )
        )


def test_article_review_pair_with_its_own_unit_is_allowed(tmp_path):
    specs = load_series_config(
        _config(
            tmp_path,
            [
                _entry(
                    "A-article_review",
                    counting_unit=ARTICLE_UNIT,
                    sensitivity="article_review",
                    comparable_with=["B-article_review"],
                ),
                _entry(
                    "B-article_review",
                    counting_unit=ARTICLE_UNIT,
                    sensitivity="article_review",
                    comparable_with=["A-article_review"],
                ),
            ],
        )
    )
    assert validate_ratio_pairs(specs) == [("A-article_review", "B-article_review")]


def test_sensitivity_must_match_the_fetched_series(tmp_path):
    with pytest.raises(ValueError, match="does not match A-all"):
        load_series_config(
            _config(
                tmp_path,
                [
                    _entry(
                        "A",
                        compute="denominator_cache",
                        cache_series="A-all",
                        sensitivity="article_review",
                    )
                ],
            )
        )


def test_denominator_cache_needs_a_known_cache_series(tmp_path):
    with pytest.raises(ValueError, match="needs cache_series"):
        load_series_config(_config(tmp_path, [_entry("A", compute="denominator_cache")]))
    with pytest.raises(ValueError, match="needs cache_series"):
        load_series_config(
            _config(tmp_path, [_entry("A", compute="denominator_cache", cache_series="Z-all")])
        )


def test_cache_file_must_have_the_cache_schema(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({"schema_version": "other", "entries": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a denominator cache"):
        load_denominator_cache(path)


# --- BQ-2.2: pollution-core v0 (A3 section 5.3) ------------------------------------------------

# A3 section 5.3 as written, with "ingested plastic(s)" as its two forms.
A3_V0_TERMS = (
    "microplastic",
    "nanoplastic",
    "micro-plastic",
    "nano-plastic",
    "micro-sized plastic",
    "microsized plastics",
    "plastic pollution",
    "plastic debris",
    "plastic litter",
    "marine debris",
    "marine litter",
    "plastic particles",
    "plastic fragments",
    "plastic ingestion",
    "resin pellet",
    "plastic pellet",
    "macroplastic",
    "mesoplastic",
    "plastics pollution",
    "plastic pollutants",
    "plastic trash",
    "anthropogenic litter",
    "anthropogenic debris",
    "anthropogenic microparticles",
    "ingested plastic",
    "ingested plastics",
    "eat plastic",
    "consuming plastic",
    "plastic contamination",
)
LIFECYCLE_CORE_TERMS = (
    "plastic recycling",
    "plastics recycling",
    "recycled plastic",
    "recycled plastics",
    "single-use plastics",
    "biodegradable plastic",
    "biodegradable plastics",
    "circular economy of plastics",
)


def test_pollution_core_v0_is_the_a3_starting_set_in_queries_spelling():
    queries = load_query_config(QUERIES)
    core = load_pollution_core(POLLUTION_CORE_PATH)

    assert core["version"] == "pollution-core-v0"
    assert core["source"] == "A3 §5.3"
    assert core["core_terms"] == list(A3_V0_TERMS)
    assert all(term in queries["core_terms"] for term in core["core_terms"])
    assert not set(core["core_terms"]) & set(core["excluded_lifecycle_terms"])
    assert core["qualified_not_included_v0"] == ["microfiber", "tire wear", "litter"]


def test_every_excluded_lifecycle_term_is_a_query_term():
    queries = load_query_config(QUERIES)
    query_terms = set(queries["core_terms"]) | {q["term"] for q in queries["qualified_terms"]}
    core = load_pollution_core(POLLUTION_CORE_PATH)
    assert set(core["excluded_lifecycle_terms"]) <= query_terms
    assert set(LIFECYCLE_CORE_TERMS) <= set(core["excluded_lifecycle_terms"])


def test_v0_leaves_out_only_the_lifecycle_core_terms_and_one_singular_form():
    queries = load_query_config(QUERIES)
    core = load_pollution_core(POLLUTION_CORE_PATH)
    left_out = sorted(set(queries["core_terms"]) - set(core["core_terms"]))
    assert left_out == sorted([*LIFECYCLE_CORE_TERMS, "anthropogenic microparticle"])


def test_pollution_core_loader_rejects_overlap_duplicates_and_empty(tmp_path):
    base = yaml.safe_load(POLLUTION_CORE_PATH.read_text(encoding="utf-8"))

    def _write(payload):
        path = tmp_path / "core.yml"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return path

    overlap = {
        **base,
        "excluded_lifecycle_terms": [*base["excluded_lifecycle_terms"], "marine debris"],
    }
    with pytest.raises(ValueError, match="also excluded lifecycle terms"):
        load_pollution_core(_write(overlap))
    duplicate = {**base, "core_terms": [*base["core_terms"], "resin pellet"]}
    with pytest.raises(ValueError, match="duplicate core terms"):
        load_pollution_core(_write(duplicate))
    empty = {**base, "core_terms": []}
    with pytest.raises(ValueError, match="core_terms is empty"):
        load_pollution_core(_write(empty))


def test_fetch_series_filters_rejects_a_pollution_core_term_missing_from_queries():
    config = load_query_config(QUERIES)
    core = {**load_pollution_core(POLLUTION_CORE_PATH), "core_terms": ["not a query term"]}
    with pytest.raises(ValueError, match="not in queries.yml core_terms"):
        fetch_series_filters(config, "B-all", pollution_core=core)
