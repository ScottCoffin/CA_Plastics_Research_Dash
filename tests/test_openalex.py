import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from atlas.ingest.openalex import (
    OpenAlexPaths,
    build_works_url,
    ingest_fixture,
    load_query_config,
    read_high_water_mark,
)

FIXTURE = Path(__file__).parent / "fixtures" / "s2_1_openalex_works.json"


def test_build_works_url_encodes_date_window_and_limits_batches() -> None:
    url = build_works_url(
        load_query_config(),
        ["I1", "I2"],
        start_date="2024-01-01",
        end_date="2024-12-31",
        per_page=1,
    )
    assert " " not in url and '"' not in url
    assert "from_publication_date%3A2024-01-01" in url
    with pytest.raises(ValueError, match="at most 100"):
        build_works_url(load_query_config(), [f"I{i}" for i in range(101)])


def test_fixture_ingestion_is_idempotent_and_preserves_raw_json(tmp_path: Path) -> None:
    paths = OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "interim" / "works_raw.parquet",
        high_water_mark=tmp_path / "interim" / "high_water.json",
        usage_log=tmp_path / "logs" / "api_usage.jsonl",
    )
    first = ingest_fixture(FIXTURE, paths=paths, run_id="test-first")
    second = ingest_fixture(FIXTURE, paths=paths, run_id="test-second")
    assert first["rows_written"] == second["rows_written"] == 4
    table = pq.read_table(paths.output_parquet)
    assert table.num_rows == 4
    assert len(set(table.column("openalex_id").to_pylist())) == 4
    assert len(list(paths.raw_dir.glob("*.json"))) == 2
    raw = json.loads(table.column("raw_json")[0].as_py())
    assert raw["title"]
    state = read_high_water_mark(paths.high_water_mark)
    assert state and state["last_publication_date"] == "2025-02-03"
    assert len(paths.usage_log.read_text(encoding="utf-8").splitlines()) == 4


def test_fixture_ingestion_rejects_more_than_200_records(tmp_path: Path) -> None:
    fixture = tmp_path / "too-many.json"
    fixture.write_text(json.dumps([{"id": f"W{i}"} for i in range(201)]), encoding="utf-8")
    with pytest.raises(ValueError, match="at most 200"):
        ingest_fixture(fixture, paths=OpenAlexPaths(output_parquet=tmp_path / "out.parquet"))
