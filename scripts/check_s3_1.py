"""Machine acceptance checks for the S3.1 static-site exporter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from atlas.build.export_site import export_site
from atlas.ingest.normalize import normalize_fixture
from atlas.nlp.labels import label_records

FIXTURE = Path("tests/fixtures/s2_2_openalex_works.json")
INSTITUTIONS = Path("data/processed/institutions.parquet")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="s3-1-acceptance-") as directory:
        root = Path(directory)
        normalized = normalize_fixture(
            FIXTURE,
            institution_path=INSTITUTIONS,
            output_dir=root / "normalized",
            qc_path=root / "normalization_qc.md",
            generated_at="acceptance",
        )
        normalized_works = pq.read_table(normalized.output_dir / "works.parquet").to_pylist()
        labels = label_records(
            normalized_works,
            json.loads(FIXTURE.read_text(encoding="utf-8")),
            output_path=root / "work_labels.parquet",
            qc_path=root / "labels_qc.md",
            source="S3.1 fixture",
            generated_at="acceptance",
        )
        kwargs = {
            "works_path": normalized.output_dir / "works.parquet",
            "authors_path": normalized.output_dir / "authors.parquet",
            "authorships_path": normalized.output_dir / "authorships.parquet",
            "institutions_path": normalized.output_dir / "institutions.parquet",
            "labels_path": labels.output_path,
            "generated_at": "acceptance",
        }
        first = export_site(output_dir=root / "site-1", **kwargs)
        second = export_site(output_dir=root / "site-2", **kwargs)
        metadata_before = (root / "site-1" / "build_metadata.json").read_bytes()
        export_site(output_dir=root / "site-1", **kwargs)
        assert metadata_before == (root / "site-1" / "build_metadata.json").read_bytes()
        files = {
            "index.json",
            "institutions.json",
            "institutions.geojson",
            "aggregates.json",
            "build_metadata.json",
        }
        assert files <= {path.name for path in (root / "site-1").iterdir()}
        assert (root / "site-1" / "authors" / "A9000000101.json").exists()
        assert (root / "site-1" / "index.json").read_bytes() == (
            root / "site-2" / "index.json"
        ).read_bytes()
        index = json.loads((root / "site-1" / "index.json").read_text(encoding="utf-8"))
        assert index["schema_version"] == "s3.1"
        assert index["counts"] == {
            "authors": 4,
            "ca_institutions": 1,
            "institutions": 3,
            "labeled_works": 4,
            "works": 4,
        }
        assert [row["work_id"] for row in index["works"]] == sorted(
            row["work_id"] for row in index["works"]
        )
        detail = json.loads(
            (root / "site-1" / "authors" / "A9000000101.json").read_text(encoding="utf-8")
        )
        assert detail["author"]["work_count"] == 1
        assert detail["works"][0]["work_id"] == "W9000000101"
        aggregates = json.loads((root / "site-1" / "aggregates.json").read_text(encoding="utf-8"))
        assert {row["year"] for row in aggregates["by_year"]} == {2023, 2024, 2025}
        geojson = json.loads((root / "site-1" / "institutions.geojson").read_text(encoding="utf-8"))
        assert len(geojson["features"]) == 1
        metadata = json.loads((root / "site-1" / "build_metadata.json").read_text(encoding="utf-8"))
        assert metadata["payload_gzip_bytes"] < 3_000_000
        assert first.counts == second.counts
        assert first.sizes["index.json"]["bytes"] > 0
    print(
        "S3.1 acceptance passed: deterministic payloads, joins, aggregates, map, and "
        "budget verified"
    )


if __name__ == "__main__":
    main()
