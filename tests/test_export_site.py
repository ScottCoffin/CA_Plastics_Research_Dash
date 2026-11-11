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
        ca_authors_only=False,
    )
    payload = json.loads((result.output_dir / "index.json").read_text(encoding="utf-8"))
    assert payload["counts"]["works"] == 4
    assert all(row["plastic_related"] is None for row in payload["works"])
    assert pq.read_table(normalized.output_dir / "authors.parquet").num_rows == len(
        payload["authors"]
    )


def test_export_site_lists_only_california_affiliated_experts(tmp_path) -> None:
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
    authors = pq.read_table(normalized.output_dir / "authors.parquet").to_pylist()
    expected = {row["author_id"] for row in authors if (row["ca_works_count"] or 0) > 0}
    assert expected and {row["author_id"] for row in payload["authors"]} == expected
    # CA-only mode also drops works with no CA authorship on any basis (2026-11-11).
    works = pq.read_table(normalized.output_dir / "works.parquet").to_pylist()
    assert payload["counts"]["works"] == sum(1 for w in works if w["ca_any_author"])
    files = {path.stem for path in (result.output_dir / "authors").glob("*.json")}
    assert files == expected


def test_export_site_removes_stale_author_files(tmp_path: Path) -> None:
    normalized = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    stale = tmp_path / "site" / "authors" / "A_GONE.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    result = export_site(
        works_path=normalized.output_dir / "works.parquet",
        authors_path=normalized.output_dir / "authors.parquet",
        authorships_path=normalized.output_dir / "authorships.parquet",
        institutions_path=normalized.output_dir / "institutions.parquet",
        output_dir=tmp_path / "site",
        generated_at="test",
        ca_authors_only=False,
    )
    payload = json.loads((result.output_dir / "index.json").read_text(encoding="utf-8"))
    assert not stale.exists()
    files = {p.stem for p in (result.output_dir / "authors").glob("*.json")}
    assert files == {row["author_id"] for row in payload["authors"]}
