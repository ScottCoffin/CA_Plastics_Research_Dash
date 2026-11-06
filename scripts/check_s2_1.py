"""Machine acceptance checks for S2.1 works ingestion."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.openalex import OpenAlexPaths, ingest_fixture

FIXTURE = Path("tests/fixtures/s2_1_openalex_works.json")


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(fixture, list) and 0 < len(fixture) <= 200
    with tempfile.TemporaryDirectory(prefix="s2-1-acceptance-") as directory:
        root = Path(directory)
        paths = OpenAlexPaths(
            raw_dir=root / "raw",
            output_parquet=root / "interim" / "works_raw.parquet",
            high_water_mark=root / "interim" / "high_water.json",
            usage_log=root / "logs" / "api_usage.jsonl",
        )
        first = ingest_fixture(FIXTURE, paths=paths, run_id="s2-1-acceptance-1")
        second = ingest_fixture(FIXTURE, paths=paths, run_id="s2-1-acceptance-2")
        table = pq.read_table(paths.output_parquet)
        ids = table.column("openalex_id").to_pylist()
        assert len(ids) == len(set(ids)) == len({row["id"] for row in fixture})
        assert first["rows_written"] == second["rows_written"] == len(ids)
        state = json.loads(paths.high_water_mark.read_text(encoding="utf-8"))
        assert state["incremental_field"] == "publication_date"
        assert state["last_successful_run_utc"]
        usage_lines = paths.usage_log.read_text(encoding="utf-8").splitlines()
        assert len(usage_lines) == 4, "two fixture requests plus two run summaries expected"
        assert all(
            json.loads(line)["record_type"] in {"request", "run_summary"} for line in usage_lines
        )
    print(
        f"S2.1 acceptance passed: {len(ids)} unique fixture works; high-water and usage log written"
    )


if __name__ == "__main__":
    main()
