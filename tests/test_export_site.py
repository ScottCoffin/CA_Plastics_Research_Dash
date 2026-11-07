import json
from pathlib import Path

import pyarrow.parquet as pq

from atlas.build.export_site import export_site
from atlas.ingest.normalize import normalize_fixture

FIXTURE = Path("tests/fixtures/s2_2_openalex_works.json")
INSTITUTIONS = Path("data/processed/institutions.parquet")


def test_export_site_builds_slim_index_without_labels(tmp_path: Path) -> None:
    normalized = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    result = export_site(
        works_path=normalized.output_dir / "works.parquet",
        authors_path=normalized.output_dir / "authors.parquet",
        authorships_path=normalized.output_dir / "authorships.parquet",
        institutions_path=normalized.output_dir / "institutions.parquet",
        output_dir=tmp_path / "site",
        generated_at="test",
    )
    payload = json.loads((result.output_dir / "index.json").read_text(encoding="utf-8"))
    assert payload["counts"]["works"] == 4
    assert all(row["plastic_related"] is None for row in payload["works"])
    assert pq.read_table(normalized.output_dir / "authors.parquet").num_rows == len(
        payload["authors"]
    )
