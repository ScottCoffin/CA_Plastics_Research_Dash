"""Offline tests for the global-denominator series (BQ-2.1).

Tiny in-memory and tmp_path fixtures only. Nothing here reads the data/ tree, site/data or the
network. The committed-config test reads config/denominator_series.yml and nothing else.
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
    QUERY_ROUTES,
    build_series,
    corpus_rows,
    load_corpus_records,
    load_published_works,
    load_series_config,
    render_payload,
    route_family,
    trend_rows,
    validate_ratio_pairs,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_denominator_series.py"
AS_OF = date(2026, 11, 22)
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


def test_committed_config_declares_the_expected_series_and_one_ratio_pair():
    specs = load_series_config(ROOT / "config" / "denominator_series.yml")

    assert {sid: spec.status for sid, spec in specs.items()} == {
        "A": "available",
        "B": "pending_fetch",
        "B2": "waits_for",
        "C": "available",
        "D": "available",
    }
    assert specs["B"].waits_for == "BQ-2.2"
    assert specs["B2"].waits_for == "BQ-S3"
    assert specs["A"].counting_unit == specs["C"].counting_unit
    assert validate_ratio_pairs(specs) == [("A", "B"), ("A", "C")]
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


def test_cli_writes_then_checks_then_detects_staleness(tmp_path, monkeypatch):
    script = _load_script()
    trend = tmp_path / "trend_global.json"
    index = tmp_path / "index.json"
    works = tmp_path / "works.parquet"
    raw = tmp_path / "works_raw.parquet"
    out = tmp_path / "out" / "denominator_series.json"
    trend.write_text(json.dumps(_trend({2024: 5, 2025: 7})), encoding="utf-8")
    index.write_text(json.dumps({"works": []}), encoding="utf-8")
    pq.write_table(pa.Table.from_pylist([], schema=WORKS_SCHEMA), works)
    pq.write_table(pa.Table.from_pylist([], schema=RAW_SCHEMA), raw)
    monkeypatch.setattr(script, "TREND", trend)
    monkeypatch.setattr(script, "INDEX", index)
    monkeypatch.setattr(script, "WORKS", works)
    monkeypatch.setattr(script, "RAW", raw)
    args = ["--as-of", "2026-11-22", "--output", str(out)]

    assert script.main(args) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["series"]["A"]["years"][-1]["year"] == 2025
    assert payload["not_computed"]["B"]["status"] == "pending_fetch"
    assert script.main(["--check", *args]) == 0

    out.write_text(
        out.read_text(encoding="utf-8").replace('"count": 7', '"count": 8'), encoding="utf-8"
    )
    assert script.main(["--check", *args]) == 1


def test_cli_check_skips_when_inputs_are_absent(tmp_path, monkeypatch):
    script = _load_script()
    monkeypatch.setattr(script, "TREND", tmp_path / "missing.json")
    output = str(tmp_path / "x.json")
    assert script.main(["--check", "--output", output]) == 0
    assert script.main(["--output", output]) == 1
