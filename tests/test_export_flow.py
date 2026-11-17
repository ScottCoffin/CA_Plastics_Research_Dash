"""FLOW-1: the PRISMA-style ``flow`` block in build_metadata.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build.export_site import _flow, export_site, refresh_metadata_counts
from atlas.ingest.normalize import normalize_fixture

FIXTURE = Path("tests/fixtures/s2_2_openalex_works.json")
INSTITUTIONS = Path("data/processed/institutions.parquet")
SUPPRESSION_HEADER = "kind,id,reason,requested_at,reviewed_by"


def _row(
    work_id: str,
    *,
    ca: bool = True,
    plastic: bool | None = None,
    work_type: str = "article",
    duplicates: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "work_id": work_id,
        "ca_any_author": ca,
        "plastic_related": plastic,
        "type": work_type,
        "duplicate_work_ids": duplicates,
    }


def test_flow_counts_each_step_and_adds_up() -> None:
    normalized = [
        _row("W1", plastic=True, duplicates=["D1", "D2"]),
        _row("W2", plastic=None, work_type="review"),
        _row("W3", ca=False, plastic=True, duplicates=["D3"]),  # no CA authorship
        _row("W4", plastic=False, work_type=""),
        _row("W5", plastic=True),  # CA, removed by curation
        _row("W6", plastic=True),
    ]
    published = [normalized[0], normalized[1], normalized[3], normalized[5]]
    flow = _flow(normalized, published)
    assert flow == {
        "records_retrieved": 9,
        "duplicates_collapsed": 3,
        "unique_works": 6,
        "no_ca_authorship": 1,
        "removed_by_curation": 1,
        "published": 4,
        "plastic_related": 2,
        "not_plastic_related": 2,
        "by_type": {"article": 2, "review": 1, "unknown": 1},
    }
    # Sorted by count descending, then by type name.
    assert list(flow["by_type"]) == ["article", "review", "unknown"]


def test_flow_empty_tables_are_all_zero() -> None:
    assert _flow([], []) == {
        "records_retrieved": 0,
        "duplicates_collapsed": 0,
        "unique_works": 0,
        "no_ca_authorship": 0,
        "removed_by_curation": 0,
        "published": 0,
        "plastic_related": 0,
        "not_plastic_related": 0,
        "by_type": {},
    }


def test_flow_missing_fields_default_safely() -> None:
    flow = _flow([{"work_id": "W1", "ca_any_author": True}], [{"work_id": "W1"}])
    assert flow["records_retrieved"] == 1
    assert flow["duplicates_collapsed"] == 0
    assert flow["removed_by_curation"] == 0
    assert flow["not_plastic_related"] == 1
    assert flow["by_type"] == {"unknown": 1}


def test_flow_rejects_published_work_without_ca_authorship() -> None:
    # A no-CA work that reached the index would make removed_by_curation negative.
    normalized = [_row("W1"), _row("W2", ca=False)]
    with pytest.raises(ValueError, match="negative"):
        _flow(normalized, normalized)


def _normalize(tmp_path: Path) -> Path:
    return normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    ).output_dir


def _export(tmp_path: Path, normalized: Path, **options: Any) -> dict[str, Any]:
    export_site(
        works_path=normalized / "works.parquet",
        authors_path=normalized / "authors.parquet",
        authorships_path=normalized / "authorships.parquet",
        institutions_path=normalized / "institutions.parquet",
        output_dir=tmp_path / "site",
        generated_at="test",
        **options,
    )
    return json.loads((tmp_path / "site" / "build_metadata.json").read_text(encoding="utf-8"))


def test_export_flow_matches_normalized_table_and_index(tmp_path: Path) -> None:
    normalized = _normalize(tmp_path)
    metadata = _export(tmp_path, normalized)
    works = pq.read_table(normalized / "works.parquet").to_pylist()
    flow = metadata["flow"]
    assert flow["unique_works"] == len(works)
    assert flow["no_ca_authorship"] == sum(1 for w in works if w["ca_any_author"] is not True)
    assert flow["published"] == metadata["counts"]["works"]
    assert flow["plastic_related"] == metadata["counts"]["plastic_works"]
    assert flow["removed_by_curation"] == metadata["curation"]["works_removed"] == 0
    assert flow["records_retrieved"] == len(works) + sum(
        len(w["duplicate_work_ids"] or []) for w in works
    )
    assert sum(flow["by_type"].values()) == flow["published"]


def test_export_flow_removed_by_curation_matches_curation_counter(tmp_path: Path) -> None:
    normalized = _normalize(tmp_path)
    works = pq.read_table(normalized / "works.parquet").to_pylist()
    ca_work = next(w["work_id"] for w in works if w["ca_any_author"] is True)
    suppressions = tmp_path / "suppressions.csv"
    suppressions.write_text(
        f"{SUPPRESSION_HEADER}\nwork,{ca_work},privacy request,2026-11-10,owner\n",
        encoding="utf-8",
    )
    metadata = _export(tmp_path, normalized, suppressions_path=suppressions)
    assert metadata["curation"]["works_removed"] == 1
    assert metadata["flow"]["removed_by_curation"] == 1
    assert metadata["flow"]["published"] == metadata["counts"]["works"]


def test_export_flow_plastic_split_follows_labels(tmp_path: Path) -> None:
    normalized = _normalize(tmp_path)
    works = pq.read_table(normalized / "works.parquet").to_pylist()
    ca_ids = [w["work_id"] for w in works if w["ca_any_author"] is True]
    labels = tmp_path / "labels.parquet"
    pq.write_table(pa.table({"work_id": ca_ids[:2], "plastic_related": [True, False]}), labels)
    metadata = _export(tmp_path, normalized, labels_path=labels)
    flow = metadata["flow"]
    assert flow["plastic_related"] == 1 == metadata["counts"]["plastic_works"]
    assert flow["not_plastic_related"] == flow["published"] - 1


def test_export_flow_omitted_when_ca_authors_only_is_off(tmp_path: Path) -> None:
    normalized = _normalize(tmp_path)
    metadata = _export(tmp_path, normalized, ca_authors_only=False)
    assert "flow" not in metadata


def test_export_flow_omitted_when_works_table_has_no_ca_column(tmp_path: Path) -> None:
    normalized = _normalize(tmp_path)
    table = pq.read_table(normalized / "works.parquet")
    kept = [name for name in table.column_names if name != "ca_any_author"]
    pq.write_table(table.select(kept), normalized / "works.parquet")
    metadata = _export(tmp_path, normalized)
    assert "flow" not in metadata
    assert metadata["counts"]["works"] == table.num_rows


def test_flow_survives_network_count_refresh(tmp_path: Path) -> None:
    normalized = _normalize(tmp_path)
    metadata = _export(tmp_path, normalized)
    path = tmp_path / "site" / "build_metadata.json"
    assert refresh_metadata_counts(path, {"network_experts": 0})
    refreshed = json.loads(path.read_text(encoding="utf-8"))
    assert refreshed["flow"] == metadata["flow"]
