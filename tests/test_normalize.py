import json
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.normalize import normalize_fixture

FIXTURE = Path(__file__).parent / "fixtures" / "s2_2_openalex_works.json"
INSTITUTIONS = Path("data/processed/institutions.parquet")


def test_normalization_outputs_c3_tables_and_flags(tmp_path: Path) -> None:
    result = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "processed",
        qc_path=tmp_path / "normalization_qc.md",
        generated_at="test",
    )
    assert json.loads(FIXTURE.read_text(encoding="utf-8"))[0]["title"]
    works = pq.read_table(result.output_dir / "works.parquet").to_pylist()
    assert len(works) == 4
    assert {row["work_id"] for row in works} == {
        "W9000000101",
        "W9000000102",
        "W9000000103",
        "W9000000104",
    }
    assert works[0]["abstract"] == "Microplastics occur in California estuaries"
    by_id = {row["work_id"]: row for row in works}
    assert by_id["W9000000101"]["ca_led"] is True
    assert by_id["W9000000102"]["ca_led"] is False
    assert by_id["W9000000102"]["ca_any_author"] is True
    assert result.metrics == {
        "source_work_rows": 4,
        "works": 4,
        "authorships": 6,
        "authors": 4,
        "institutions": 3,
        "missing_affiliations": 2,
        "null_author_ids": 2,
        "unresolved_institution_links": 2,
        "ca_affiliation_without_resolved_institution": 1,
        "ca_led_works": 2,
        "ca_any_author_works": 3,
        "misattached_abstracts_blanked": 0,
        "near_duplicates_collapsed": 0,
        "near_duplicate_groups": 0,
        "skipped_same_title_distinct_doi": 0,
        "authorships_ca_registry": 2,
        "authorships_ca_raw_affiliation": 1,
        "authorships_ca_carry_forward": 0,
        "authorships_carry_forward_orcid_contradicted": 0,
        "authorships_ca_escholarship": 0,
        "works_ca_escholarship": 0,
    }
    # W...103 is CA only through a raw affiliation string ("California, USA").
    assert by_id["W9000000103"]["ca_led"] is True
    authorships = pq.read_table(result.output_dir / "authorships.parquet").to_pylist()
    assert {r["ca_basis"] for r in authorships} == {"registry", "raw_affiliation", ""}
    report = result.qc_path.read_text(encoding="utf-8")
    assert "Authorships with missing raw affiliation | 2" in report


def test_normalization_preserves_unresolved_institution_rows(tmp_path: Path) -> None:
    result = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "processed",
        qc_path=tmp_path / "normalization_qc.md",
    )
    rows = pq.read_table(result.output_dir / "institutions.parquet").to_pylist()
    by_id = {row["inst_id"]: row for row in rows}
    assert by_id["I84218800"]["ca_flag"] is True
    assert by_id["I99999992"]["ca_flag"] is False
    assert by_id["I99999991"]["atlas_type"] == "other"


def test_suppressed_works_and_authors_are_dropped_at_ingest(tmp_path: Path) -> None:
    """GOV-B (owner, 2026-11-10): suppressions apply at ingest, not only at export."""
    works = json.loads(FIXTURE.read_text(encoding="utf-8"))
    author_id = next(
        a["author"]["id"].rsplit("/", 1)[-1]
        for a in works[0]["authorships"]
        if (a.get("author") or {}).get("id")
    )
    suppressions = tmp_path / "suppressions.csv"
    suppressions.write_text(
        "kind,id,reason,requested_at,reviewed_by\n"
        f"work,W9000000104,test,2026-11-10,SC\nauthor,{author_id},test,2026-11-10,SC\n",
        encoding="utf-8",
    )
    result = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "processed",
        qc_path=tmp_path / "qc.md",
        suppressions_path=suppressions,
        generated_at="test",
    )
    works_table = pq.read_table(result.output_dir / "works.parquet").to_pylist()
    kept = {row["work_id"] for row in works_table}
    assert "W9000000104" not in kept and len(kept) == 3
    authorships = pq.read_table(result.output_dir / "authorships.parquet").to_pylist()
    assert author_id not in {row["author_id"] for row in authorships}


def test_is_retracted_is_carried_from_openalex(tmp_path: Path) -> None:
    """AT-3 excludes retracted works; normalize keeps OpenAlex's flag (missing -> False)."""
    works = json.loads(FIXTURE.read_text(encoding="utf-8"))
    works[0]["is_retracted"] = True
    works[1].pop("is_retracted", None)
    fixture = tmp_path / "works.json"
    fixture.write_text(json.dumps(works), encoding="utf-8")
    result = normalize_fixture(
        fixture,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "processed",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    rows = {r["work_id"]: r for r in pq.read_table(result.output_dir / "works.parquet").to_pylist()}
    first = works[0]["id"].rsplit("/", 1)[-1]
    second = works[1]["id"].rsplit("/", 1)[-1]
    assert rows[first]["is_retracted"] is True
    assert rows[second]["is_retracted"] is False
