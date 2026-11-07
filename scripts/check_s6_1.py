"""Machine acceptance checks for license-aware S6.1 full-text discovery."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from atlas.fulltext import LOCATOR_SCHEMA, coverage_report, locate_records, write_locator

FIXTURE = Path("tests/fixtures/s6_1_fulltext_records.json")


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = locate_records(fixture["candidates"], fixture["raw"])
    by_id = {row["work_id"]: row for row in rows}
    assert len(rows) == 8
    assert sum(row["source_type"] == "xml" for row in rows) == 2
    assert sum(row["source_type"] == "pdf" for row in rows) == 4
    assert sum(row["source_type"] == "none" for row in rows) == 2
    assert by_id["W9000000101"]["license"] == "cc-by-4.0"
    assert "PMC8123456" in by_id["W9000000101"]["license_provenance"]
    assert by_id["W9000000103"]["license_status"] == "unknown"
    assert by_id["W9000000103"]["processing_allowed"] is False
    assert by_id["W9000000104"]["license_status"] == "unknown"
    assert by_id["W9000000104"]["processing_allowed"] is False
    assert by_id["W9000000105"]["license_status"] == "restricted"
    assert by_id["W9000000105"]["processing_allowed"] is False
    report = coverage_report(rows, source="synthetic fixture")
    assert "candidate rows: 8" in report
    assert "| XML | 2 | 25.0% |" in report
    assert "| PDF | 4 | 50.0% |" in report
    assert "| None | 2 | 25.0% |" in report
    assert "| permissive | 2 |" in report
    assert "| restricted | 1 |" in report
    assert "| unknown | 5 |" in report
    with tempfile.TemporaryDirectory(prefix="s6-1-acceptance-") as directory:
        output = Path(directory) / "locators.parquet"
        write_locator(rows, str(output))
        table = pq.read_table(output)
        assert table.schema.equals(LOCATOR_SCHEMA)
        assert table.to_pylist() == rows
        assert report == coverage_report(
            locate_records(fixture["candidates"], fixture["raw"]), source="synthetic fixture"
        )
    print(
        "S6.1 acceptance passed: XML/PDF/none selection, selected-copy license provenance, "
        "safe unknown and restricted cases, deterministic fixture report"
    )


if __name__ == "__main__":
    main()
