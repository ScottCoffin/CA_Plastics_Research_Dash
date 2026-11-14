"""AT-11: CI guards for the daily ingest (rate limit, empty day, schema, payload size)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.guards import (
    check_normalized,
    check_raw_works,
    check_site_payload,
    run_all,
)
from atlas.ingest.daily import run_daily_ingest
from atlas.ingest.normalize import (
    AUTHORS_SCHEMA,
    AUTHORSHIPS_SCHEMA,
    INSTITUTIONS_SCHEMA,
    WORKS_SCHEMA,
)
from atlas.ingest.openalex import (
    RAW_SCHEMA,
    OpenAlexBudgetError,
    OpenAlexPaths,
    OpenAlexRateLimitError,
)

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_ci_guards.py"


def make_work(**overrides: object) -> dict:
    work = {
        "id": "https://openalex.org/W1",
        "title": "Microplastics in California wastewater",
        "publication_year": 2025,
        "publication_date": "2025-03-01",
        "type": "article",
        "authorships": [
            {"author": {"id": "https://openalex.org/A1"}, "institutions": [{"id": "I1"}]}
        ],
        "primary_location": {"source": None},
        "open_access": {"is_oa": False},
        "is_retracted": False,
        "cited_by_count": 3,
    }
    work.update(overrides)
    return work


def write_raw(path: Path, works: list[dict], *, schema: pa.Schema = RAW_SCHEMA) -> Path:
    rows = [
        {
            "openalex_id": work.get("id"),
            "updated_date": "2025-03-01",
            "publication_date": "2025-03-01",
            "publication_year": 2025,
            "raw_json": json.dumps(work, sort_keys=True),
            "source_run_id": "run-1",
            "fetched_at_utc": "2025-03-02T00:00:00Z",
        }
        for work in works
    ]
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    return path


def write_normalized(directory: Path, *, works_schema: pa.Schema = WORKS_SCHEMA) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    tables = {
        "works.parquet": works_schema,
        "authorships.parquet": AUTHORSHIPS_SCHEMA,
        "authors.parquet": AUTHORS_SCHEMA,
        "institutions.parquet": INSTITUTIONS_SCHEMA,
    }
    for name, schema in tables.items():
        pq.write_table(pa.Table.from_pylist([], schema=schema), directory / name)
    return directory


def write_site(
    directory: Path, *, works: list[dict] | None = None, index_extra: dict | None = None
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    rows = works if works is not None else [{"work_id": "W1", "title": "t", "year": 2025}]
    index = {
        "schema_version": 1,
        "generated_at": "2026-11-11T00:00:00+00:00",
        "counts": {"works": len(rows)},
        "authors": {},
        "works": rows,
    }
    index.update(index_extra or {})
    (directory / "index.json").write_text(json.dumps(index), encoding="utf-8")
    for name in ("institutions.json", "aggregates.json", "build_metadata.json"):
        (directory / name).write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    return directory


# Rate limit ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (OpenAlexRateLimitError("429 Too Many Requests", retry_after="60"), "rate_limited"),
        (OpenAlexBudgetError("daily ceiling reached"), "budget_exceeded"),
    ],
)
def test_rate_limited_run_defers_and_keeps_outputs_byte_identical(
    tmp_path: Path, error: Exception, reason: str
) -> None:
    paths = OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "works_raw.parquet",
        high_water_mark=tmp_path / "hw.json",
        usage_log=tmp_path / "usage.jsonl",
    )
    write_raw(paths.output_parquet, [make_work()])
    paths.high_water_mark.write_text('{"schema_version": 1}', encoding="utf-8")
    paths.usage_log.write_text('{"event": "earlier"}\n', encoding="utf-8")
    before = {
        p: p.read_bytes() for p in (paths.output_parquet, paths.high_water_mark, paths.usage_log)
    }

    def raising_ingest(**_: object) -> dict:
        raise error

    result = run_daily_ingest(institution_ids=["I1"], paths=paths, ingest=raising_ingest)

    assert result["status"] == "deferred"
    assert result["reason"] == reason
    after = {p: p.read_bytes() for p in before}
    assert after == before


# Empty day ----------------------------------------------------------------------


def test_empty_day_is_a_successful_run(tmp_path: Path) -> None:
    def empty_ingest(**_: object) -> dict:
        return {"fetched": 0, "rows_written": 0}

    result = run_daily_ingest(
        institution_ids=["I1"],
        paths=OpenAlexPaths(output_parquet=tmp_path / "w.parquet"),
        ingest=empty_ingest,
    )
    assert result["status"] == "success"
    assert result["fetched"] == 0


def test_empty_raw_parquet_has_no_problems(tmp_path: Path) -> None:
    raw = write_raw(tmp_path / "works_raw.parquet", [])
    result = check_raw_works(raw)
    assert result.problems == []
    assert result.metrics["rows"] == 0


# Schema change ------------------------------------------------------------------


def test_valid_raw_records_pass(tmp_path: Path) -> None:
    raw = write_raw(tmp_path / "works_raw.parquet", [make_work(), make_work(id="W2")])
    result = check_raw_works(raw)
    assert result.problems == []
    assert result.metrics == {"rows": 2, "sampled": 2, "bad_records": 0}


def test_raw_json_missing_authorships_is_detected(tmp_path: Path) -> None:
    work = make_work()
    del work["authorships"]
    raw = write_raw(tmp_path / "works_raw.parquet", [make_work(), work])
    result = check_raw_works(raw)
    assert any("'authorships'" in problem for problem in result.problems)
    assert result.metrics["bad_records"] == 1


def test_raw_json_missing_is_retracted_is_detected(tmp_path: Path) -> None:
    work = make_work()
    del work["is_retracted"]
    raw = write_raw(tmp_path / "works_raw.parquet", [work])
    result = check_raw_works(raw)
    assert any("'is_retracted'" in problem for problem in result.problems)
    assert result.metrics["bad_records"] == 1


def test_authorship_item_missing_institutions_is_detected(tmp_path: Path) -> None:
    work = make_work(authorships=[{"author": {"id": "A1"}}])
    raw = write_raw(tmp_path / "works_raw.parquet", [work])
    result = check_raw_works(raw)
    assert any("authorships[].institutions" in problem for problem in result.problems)


def test_raw_parquet_missing_column_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "works_raw.parquet"
    table = pa.Table.from_pylist(
        [{"openalex_id": "W1", "raw_json": "{}"}],
        schema=pa.schema([("openalex_id", pa.string()), ("raw_json", pa.string())]),
    )
    pq.write_table(table, path)
    result = check_raw_works(path)
    assert any("missing columns" in problem for problem in result.problems)


def test_normalized_tables_pass_when_schemas_match(tmp_path: Path) -> None:
    result = check_normalized(write_normalized(tmp_path / "normalized"))
    assert result.problems == []


def test_normalized_missing_column_is_detected(tmp_path: Path) -> None:
    schema = pa.schema([field for field in WORKS_SCHEMA if field.name != "cited_by_count"])
    directory = write_normalized(tmp_path / "normalized", works_schema=schema)
    result = check_normalized(directory)
    assert any("missing column 'cited_by_count'" in problem for problem in result.problems)


def test_normalized_wrong_type_is_detected(tmp_path: Path) -> None:
    schema = pa.schema(
        [pa.field("year", pa.string()) if field.name == "year" else field for field in WORKS_SCHEMA]
    )
    directory = write_normalized(tmp_path / "normalized", works_schema=schema)
    result = check_normalized(directory)
    assert any("'year' has type string" in problem for problem in result.problems)


def test_normalized_missing_directory_and_table_are_problems(tmp_path: Path) -> None:
    assert check_normalized(tmp_path / "absent").problems
    directory = write_normalized(tmp_path / "normalized")
    (directory / "authors.parquet").unlink()
    result = check_normalized(directory)
    assert result.problems == ["normalized table missing: authors.parquet"]


# Oversized payload --------------------------------------------------------------


def test_initial_payload_over_gzip_limit_is_detected(tmp_path: Path) -> None:
    site = write_site(tmp_path / "data")
    result = check_site_payload(site, initial_gzip_limit=10)
    assert any("initial payload gzip" in problem for problem in result.problems)
    assert result.metrics["initial_gzip_bytes"] > 10


def test_file_over_size_limit_is_detected(tmp_path: Path) -> None:
    site = write_site(tmp_path / "data")
    (site / "authors").mkdir()
    (site / "authors" / "big.json").write_text("x" * 5000, encoding="utf-8")
    result = check_site_payload(site, file_limit=1000)
    assert any("authors/big.json" in problem for problem in result.problems)
    assert result.metrics["largest_file"] == "authors/big.json"


def test_index_missing_required_keys_or_row_fields_is_detected(tmp_path: Path) -> None:
    site = write_site(tmp_path / "data", works=[{"work_id": "W1", "title": "t"}])
    result = check_site_payload(site)
    assert any("work rows lack" in problem for problem in result.problems)
    payload = json.loads((site / "index.json").read_text(encoding="utf-8"))
    del payload["authors"]
    (site / "index.json").write_text(json.dumps(payload), encoding="utf-8")
    assert any("missing key 'authors'" in p for p in check_site_payload(site).problems)


def test_missing_initial_file_is_detected(tmp_path: Path) -> None:
    site = write_site(tmp_path / "data")
    (site / "aggregates.json").unlink()
    result = check_site_payload(site)
    assert result.problems == ["initial payload file missing: aggregates.json"]


# Happy path and run_all ---------------------------------------------------------


def test_committed_site_data_passes_default_limits() -> None:
    result = check_site_payload(ROOT / "site" / "data")
    assert result.problems == []
    assert result.metrics["initial_gzip_bytes"] <= 3_000_000
    assert result.metrics["largest_file_bytes"] <= 25_000_000


def test_run_all_skips_absent_optional_inputs(tmp_path: Path) -> None:
    results = run_all(
        raw_path=tmp_path / "missing.parquet",
        normalized_dir=tmp_path / "missing-normalized",
        site_data_dir=write_site(tmp_path / "data"),
    )
    assert set(results) == {"site_payload"}
    assert results["site_payload"].ok


def test_run_all_required_missing_input_is_a_problem(tmp_path: Path) -> None:
    results = run_all(raw_path=tmp_path / "missing.parquet", require_raw=True, require_site=False)
    assert set(results) == {"raw_works"}
    assert not results["raw_works"].ok


def test_cli_exit_code_reflects_problems(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    spec = importlib.util.spec_from_file_location("check_ci_guards", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    raw = write_raw(tmp_path / "works_raw.parquet", [])
    normalized = write_normalized(tmp_path / "normalized")
    site = write_site(tmp_path / "data")
    args = ["--raw", str(raw), "--normalized-dir", str(normalized), "--site-data", str(site)]
    assert module.main(args) == 0
    out = capsys.readouterr().out
    assert "raw_works: OK" in out and "site_payload: OK" in out
    assert module.main([*args, "--require-raw"]) == 0
    assert module.main(["--site-data", str(tmp_path / "absent")]) == 1


def test_daily_ingest_passes_the_publication_date_cap(tmp_path: Path) -> None:
    """Regression (2026-11-12/13 CI failures): the runner's date cap must reach ingest_live."""
    seen: dict = {}

    def fake_ingest(**kwargs):
        seen.update(kwargs)
        return {"works": 0}

    result = run_daily_ingest(
        institution_ids=["I1"],
        paths=OpenAlexPaths(output_parquet=tmp_path / "w.parquet"),
        publication_date_cap="2026-11-12",
        ingest=fake_ingest,
    )
    assert result["status"] == "success"
    assert seen["publication_date_cap"] == "2026-11-12"
