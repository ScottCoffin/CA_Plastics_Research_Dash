"""Author auto-merges, author metrics, institution work files and the works review helper."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_same_name_same_institution_merges_transitively() -> None:
    merges = _script("build_author_merges")
    authors = [
        {"author_id": "A1", "name": "Andrew B. Gray", "ca_works_count": 30},
        {"author_id": "A2", "name": "andrew b gray", "ca_works_count": 1},
        {"author_id": "A3", "name": "Andrew B Gray", "ca_works_count": 2},
        {"author_id": "A4", "name": "Andrew Gray", "ca_works_count": 3},
        {"author_id": "A5", "name": "Andrew B. Gray", "ca_works_count": 9},
    ]
    authorships = [
        {"work_id": "W1", "author_id": "A1", "institution_ids": ["I1"]},
        {"work_id": "W2", "author_id": "A2", "institution_ids": ["I1", "I2"]},
        {"work_id": "W3", "author_id": "A3", "institution_ids": ["I2"]},
        {"work_id": "W4", "author_id": "A4", "institution_ids": ["I1"]},  # different name
        {"work_id": "W5", "author_id": "A5", "institution_ids": ["I9"]},  # different institution
    ]
    rows = merges.merge_rows(authors, authorships)
    assert [(r["from_author_id"], r["to_author_id"]) for r in rows] == [("A2", "A1"), ("A3", "A1")]
    assert all(r["reason"].startswith(merges.MARKER) for r in rows)
    # Hand-written merges keep their IDs out of the rule.
    assert merges.merge_rows(authors, authorships, keep={"A2"}) == []


def test_committed_author_merges_are_current() -> None:
    merges = _script("build_author_merges")
    path = ROOT / "curation" / "author_merges.csv"
    authors = ROOT / "data/processed/normalized/authors.parquet"
    authorships = ROOT / "data/processed/normalized/authorships.parquet"
    text = merges.render(path, authors, authorships)
    assert path.read_text(encoding="utf-8").replace("\r\n", "\n") == text


def test_author_metrics_url_and_row() -> None:
    metrics = _script("fetch_author_metrics")
    url = metrics.authors_url(["A1", "A2"])
    assert "openalex%3AA1%7CA2" in url and "per-page=2" in url
    row = metrics.row_from_author(
        {
            "id": "https://openalex.org/A1",
            "cited_by_count": 10,
            "works_count": 3,
            "summary_stats": {"h_index": 2, "i10_index": 1},
        },
        "t",
    )
    assert row == {
        "author_id": "A1",
        "cited_by_count": 10,
        "h_index": 2,
        "i10_index": 1,
        "works_count": 3,
        "fetched_at_utc": "t",
    }


def test_work_details_rebuild_abstract(tmp_path: Path) -> None:
    from atlas.work_relevance_review import load_work_details

    work = {
        "id": "https://openalex.org/W1",
        "display_name": "Microplastics in SF Bay",
        "abstract_inverted_index": {"Plastic": [0], "found": [1]},
        "authorships": [
            {"author": {"display_name": "A. Author"}, "institutions": [{"display_name": "UC"}]}
        ],
        "publication_year": 2020,
    }
    path = tmp_path / "raw.parquet"
    pq.write_table(
        pa.Table.from_pylist([{"openalex_id": "W1", "raw_json": json.dumps(work)}]), path
    )
    detail = load_work_details(path)["W1"]
    assert detail["abstract"] == "Plastic found"
    assert detail["authors"] == "A. Author" and detail["institutions"] == "UC"
    assert load_work_details(tmp_path / "missing.parquet") == {}


def test_export_adds_author_metrics_and_institution_files(tmp_path: Path) -> None:
    from atlas.build.export_site import export_site
    from atlas.ingest.normalize import normalize_fixture

    normalized = normalize_fixture(
        Path("tests/fixtures/s2_2_openalex_works.json"),
        institution_path=Path("data/processed/institutions.parquet"),
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    authors = pq.read_table(normalized.output_dir / "authors.parquet").to_pylist()
    first = authors[0]["author_id"]
    metrics = tmp_path / "metrics.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [{"author_id": first, "cited_by_count": 99, "h_index": 7}],
        ),
        metrics,
    )
    site = tmp_path / "site"
    export_site(
        works_path=normalized.output_dir / "works.parquet",
        authors_path=normalized.output_dir / "authors.parquet",
        authorships_path=normalized.output_dir / "authorships.parquet",
        institutions_path=normalized.output_dir / "institutions.parquet",
        author_metrics_path=metrics,
        output_dir=site,
        generated_at="test",
        ca_authors_only=False,
    )
    index = json.loads((site / "index.json").read_text(encoding="utf-8"))
    row = next(a for a in index["authors"] if a["author_id"] == first)
    assert row["cited_by_count"] == 99 and row["h_index"] == 7
    assert {"plastic_works_count", "plastic_citations"} <= set(row)
    files = list((site / "institution_works").glob("*.json"))
    assert files, "CA institutions with works get a publication file"
    detail = json.loads(files[0].read_text(encoding="utf-8"))
    assert detail["works"] and "abstract" in detail["works"][0]
    assert "author_names" in detail["works"][0]
