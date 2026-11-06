"""Machine acceptance checks for S2.2 normalization and QC."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.normalize import (
    AUTHORS_SCHEMA,
    AUTHORSHIPS_SCHEMA,
    INSTITUTIONS_SCHEMA,
    WORKS_SCHEMA,
    normalize_raw_parquet,
)
from atlas.ingest.openalex import OpenAlexPaths, ingest_fixture

FIXTURE = Path("tests/fixtures/s2_2_openalex_works.json")
INSTITUTIONS = Path("data/processed/institutions.parquet")


def main() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(fixture, list) and 0 < len(fixture) <= 200
    with tempfile.TemporaryDirectory(prefix="s2-2-acceptance-") as directory:
        root = Path(directory)
        raw = OpenAlexPaths(
            raw_dir=root / "raw",
            output_parquet=root / "interim" / "works_raw.parquet",
            high_water_mark=root / "interim" / "high_water.json",
            usage_log=root / "logs" / "api_usage.jsonl",
        )
        ingest_fixture(FIXTURE, paths=raw, run_id="s2-2-acceptance")
        result = normalize_raw_parquet(
            raw.output_parquet,
            institution_path=INSTITUTIONS,
            output_dir=root / "processed",
            qc_path=root / "normalization_qc.md",
            generated_at="acceptance",
        )
        works = pq.read_table(result.output_dir / "works.parquet")
        authorships = pq.read_table(result.output_dir / "authorships.parquet")
        authors = pq.read_table(result.output_dir / "authors.parquet")
        institutions = pq.read_table(result.output_dir / "institutions.parquet")
        assert works.schema.equals(WORKS_SCHEMA)
        assert authorships.schema.equals(AUTHORSHIPS_SCHEMA)
        assert authors.schema.equals(AUTHORS_SCHEMA)
        assert institutions.schema.equals(INSTITUTIONS_SCHEMA)
        flags = {row["work_id"]: (row["ca_led"], row["ca_any_author"]) for row in works.to_pylist()}
        assert flags["W9000000101"] == (True, True)
        assert flags["W9000000102"] == (False, True)
        assert flags["W9000000103"] == (False, False)
        assert flags["W9000000104"] == (False, False)
        assert result.metrics["missing_affiliations"] == 2
        assert result.metrics["null_author_ids"] == 2
        assert result.metrics["unresolved_institution_links"] == 2
        assert result.metrics["ca_affiliation_without_resolved_institution"] == 1
        assert result.metrics["ca_led_works"] == 1
        assert result.metrics["ca_any_author_works"] == 2
        qc = result.qc_path.read_text(encoding="utf-8")
        assert "Works with CA-like affiliation but no resolved CA institution" in qc
        assert "Authorships with null author IDs" in qc
    print("S2.2 acceptance passed: C3 tables, CA flags, and QC metrics verified")


if __name__ == "__main__":
    main()
