"""S10.2 corrections: suppressions, work overrides and author merges at export time."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.build.curation import load_author_merges, load_curation, load_work_overrides
from atlas.build.export_site import export_site
from atlas.ingest.normalize import normalize_fixture

FIXTURE = Path("tests/fixtures/s2_2_openalex_works.json")
INSTITUTIONS = Path("data/processed/institutions.parquet")
REPO_CURATION = Path("curation")

SUPPRESSION_HEADER = "kind,id,reason,requested_at,reviewed_by"
OVERRIDE_HEADER = "work_id,field,value,reason,reviewed_by,reviewed_at"
MERGE_HEADER = "from_author_id,to_author_id,reason,reviewed_by,reviewed_at"


def _csv(path: Path, header: str, rows: list[str]) -> Path:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def _export(tmp_path: Path, **curation: Path) -> Path:
    normalized = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    export_site(
        works_path=normalized.output_dir / "works.parquet",
        authors_path=normalized.output_dir / "authors.parquet",
        authorships_path=normalized.output_dir / "authorships.parquet",
        institutions_path=normalized.output_dir / "institutions.parquet",
        output_dir=tmp_path / "site",
        generated_at="test",
        **curation,
    )
    return tmp_path / "site"


def _json(site: Path, name: str) -> dict:
    return json.loads((site / name).read_text(encoding="utf-8"))


def _all_text(site: Path) -> str:
    """Concatenate every file under the output directory, including metadata."""
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(site.rglob("*")) if path.is_file()
    )


def test_shipped_curation_files_are_header_only_and_load_empty() -> None:
    curation = load_curation(
        suppressions_path=REPO_CURATION / "suppressions.csv",
        work_overrides_path=REPO_CURATION / "overrides_works.csv",
        author_merges_path=REPO_CURATION / "author_merges.csv",
    )
    assert not curation.suppressed_authors
    assert not curation.suppressed_works
    assert not curation.work_overrides
    assert not curation.author_merges


def test_empty_curation_leaves_payloads_unchanged(tmp_path: Path) -> None:
    plain = _export(tmp_path / "plain")
    curated = _export(
        tmp_path / "curated",
        suppressions_path=REPO_CURATION / "suppressions.csv",
        work_overrides_path=REPO_CURATION / "overrides_works.csv",
        author_merges_path=REPO_CURATION / "author_merges.csv",
    )
    assert (plain / "index.json").read_bytes() == (curated / "index.json").read_bytes()
    assert (plain / "aggregates.json").read_bytes() == (curated / "aggregates.json").read_bytes()


def test_suppressed_author_never_appears_in_any_output_file(tmp_path: Path) -> None:
    suppressions = _csv(
        tmp_path / "suppressions.csv",
        SUPPRESSION_HEADER,
        ["author,A9000000102,privacy request,2026-11-10,owner"],
    )
    site = _export(tmp_path, suppressions_path=suppressions)
    assert "A9000000102" not in _all_text(site)
    assert not (site / "authors" / "A9000000102.json").exists()
    assert (site / "authors" / "A9000000103.json").exists()
    index = _json(site, "index.json")
    assert [row["author_id"] for row in index["authors"]] == [
        "A9000000101",
        "A9000000103",
        "A9000000104",
    ]
    work = next(row for row in index["works"] if row["work_id"] == "W9000000102")
    assert work["author_ids"] == ["A9000000103"]
    assert index["counts"]["works"] == 4
    assert index["counts"]["authors"] == 3
    metadata = _json(site, "build_metadata.json")
    assert metadata["curation"]["authors_removed"] == 1


def test_author_suppression_recomputes_institution_counts(tmp_path: Path) -> None:
    baseline = _json(_export(tmp_path / "base"), "institutions.json")
    suppressions = _csv(
        tmp_path / "suppressions.csv",
        SUPPRESSION_HEADER,
        ["author,A9000000102,privacy request,2026-11-10,owner"],
    )
    site = _export(tmp_path / "suppressed", suppressions_path=suppressions)
    assert "A9000000102" not in _all_text(site)
    before = {row["inst_id"]: row for row in baseline["institutions"]}
    after = {row["inst_id"]: row for row in _json(site, "institutions.json")["institutions"]}
    assert set(before) == set(after)
    assert any(after[i]["author_count"] < before[i]["author_count"] for i in before)


def test_sole_author_suppression_drops_their_work(tmp_path: Path) -> None:
    suppressions = _csv(
        tmp_path / "suppressions.csv",
        SUPPRESSION_HEADER,
        ["author,A9000000104,privacy request,2026-11-10,owner"],
    )
    site = _export(tmp_path, suppressions_path=suppressions)
    assert "A9000000104" not in _all_text(site)
    index = _json(site, "index.json")
    assert "W9000000103" not in {row["work_id"] for row in index["works"]}
    assert index["counts"]["works"] == 3
    assert not (site / "authors" / "A9000000104.json").exists()


def test_suppressed_work_is_dropped_and_its_authors_are_pruned(tmp_path: Path) -> None:
    suppressions = _csv(
        tmp_path / "suppressions.csv",
        SUPPRESSION_HEADER,
        ["work,W9000000101,takedown request,2026-11-10,owner"],
    )
    site = _export(tmp_path, suppressions_path=suppressions)
    assert "W9000000101" not in _all_text(site)
    index = _json(site, "index.json")
    assert index["counts"]["works"] == 3
    assert "A9000000101" not in {row["author_id"] for row in index["authors"]}
    assert not (site / "authors" / "A9000000101.json").exists()


def test_suppressions_reject_unknown_kind(tmp_path: Path) -> None:
    path = _csv(
        tmp_path / "suppressions.csv",
        SUPPRESSION_HEADER,
        ["person,A9000000101,reason,2026-11-10,owner"],
    )
    with pytest.raises(ValueError, match="kind must be author or work"):
        load_curation(suppressions_path=path)


def test_suppressions_require_reviewer(tmp_path: Path) -> None:
    path = _csv(
        tmp_path / "suppressions.csv",
        SUPPRESSION_HEADER,
        ["author,A9000000101,reason,2026-11-10,"],
    )
    with pytest.raises(ValueError, match="reviewed_by is required"):
        load_curation(suppressions_path=path)


def test_work_overrides_apply_to_index_detail_and_aggregates(tmp_path: Path) -> None:
    overrides = _csv(
        tmp_path / "overrides.csv",
        OVERRIDE_HEADER,
        [
            "W9000000101,title,Corrected title,typo,owner,2026-11-10",
            "W9000000101,publication_year,2022,wrong year,owner,2026-11-10",
            "W9000000101,plastic_related,true,label review,owner,2026-11-10",
            "W9000000101,domain_tags,zeta|alpha|zeta,tag review,owner,2026-11-10",
        ],
    )
    site = _export(tmp_path, work_overrides_path=overrides)
    index = _json(site, "index.json")
    row = next(item for item in index["works"] if item["work_id"] == "W9000000101")
    assert row["title"] == "Corrected title"
    assert row["year"] == 2022
    assert row["plastic_related"] is True
    assert row["domain_tags"] == ["alpha", "zeta"]
    detail = _json(site, "authors/A9000000101.json")
    full = next(item for item in detail["works"] if item["work_id"] == "W9000000101")
    assert full["title"] == "Corrected title"
    aggregates = _json(site, "aggregates.json")
    assert 2022 in {item["year"] for item in aggregates["by_year"]}
    metadata = _json(site, "build_metadata.json")
    assert metadata["curation"]["work_overrides_applied"] == 4
    assert metadata["curation"]["work_overrides_skipped"] == 0


def test_work_override_for_suppressed_work_is_skipped(tmp_path: Path) -> None:
    suppressions = _csv(
        tmp_path / "suppressions.csv",
        SUPPRESSION_HEADER,
        ["work,W9000000101,takedown,2026-11-10,owner"],
    )
    overrides = _csv(
        tmp_path / "overrides.csv",
        OVERRIDE_HEADER,
        ["W9000000101,title,Ignored,typo,owner,2026-11-10"],
    )
    site = _export(tmp_path, suppressions_path=suppressions, work_overrides_path=overrides)
    assert "Ignored" not in _all_text(site)
    assert _json(site, "build_metadata.json")["curation"]["work_overrides_skipped"] == 1


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("W9000000101,doi,10.1/x,reason,owner,2026-11-10", "cannot be overridden"),
        ("W9000000101,ca_sampling_flag,true,reason,owner,2026-11-10", "cannot be overridden"),
        ("W9000000101,publication_year,soon,reason,owner,2026-11-10", "must be an integer"),
        ("W9000000101,plastic_related,yes,reason,owner,2026-11-10", "must be true or false"),
        ("W9000000101,title,,reason,owner,2026-11-10", "value is required"),
        ("W9000000101,title,New,reason,,2026-11-10", "reviewed_by is required"),
    ],
)
def test_work_overrides_reject_invalid_rows(tmp_path: Path, row: str, message: str) -> None:
    path = _csv(tmp_path / "overrides.csv", OVERRIDE_HEADER, [row])
    with pytest.raises(ValueError, match=message):
        load_work_overrides(path)


def test_work_overrides_reject_duplicate_field(tmp_path: Path) -> None:
    path = _csv(
        tmp_path / "overrides.csv",
        OVERRIDE_HEADER,
        [
            "W9000000101,title,One,reason,owner,2026-11-10",
            "W9000000101,title,Two,reason,owner,2026-11-10",
        ],
    )
    with pytest.raises(ValueError, match="overridden twice"):
        load_work_overrides(path)


def test_author_merge_repoints_authorships_and_removes_source(tmp_path: Path) -> None:
    merges = _csv(
        tmp_path / "merges.csv",
        MERGE_HEADER,
        ["A9000000103,A9000000102,duplicate profile,owner,2026-11-10"],
    )
    site = _export(tmp_path, author_merges_path=merges)
    assert "A9000000103" not in _all_text(site)
    assert not (site / "authors" / "A9000000103.json").exists()
    index = _json(site, "index.json")
    assert "A9000000103" not in {row["author_id"] for row in index["authors"]}
    work = next(row for row in index["works"] if row["work_id"] == "W9000000102")
    assert work["author_ids"] == ["A9000000102"]
    target = next(row for row in index["authors"] if row["author_id"] == "A9000000102")
    assert target["work_ids"] == ["W9000000102"]
    detail = _json(site, "authors/A9000000102.json")
    assert [item["work_id"] for item in detail["works"]] == ["W9000000102"]
    metadata = _json(site, "build_metadata.json")
    assert metadata["curation"]["authorships_repointed"] == 1


def test_author_merge_rejects_self_and_cycles(tmp_path: Path) -> None:
    self_merge = _csv(
        tmp_path / "self.csv",
        MERGE_HEADER,
        ["A9000000102,A9000000102,reason,owner,2026-11-10"],
    )
    with pytest.raises(ValueError, match="same author"):
        load_author_merges(self_merge)
    cycle = _csv(
        tmp_path / "cycle.csv",
        MERGE_HEADER,
        [
            "A9000000102,A9000000103,reason,owner,2026-11-10",
            "A9000000103,A9000000102,reason,owner,2026-11-10",
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        load_author_merges(cycle)


def test_merge_resolves_chains_and_accepts_openalex_urls(tmp_path: Path) -> None:
    path = _csv(
        tmp_path / "chain.csv",
        MERGE_HEADER,
        [
            "https://openalex.org/A1,A2,reason,owner,2026-11-10",
            "A2,A3,reason,owner,2026-11-10",
        ],
    )
    assert load_author_merges(path) == {"A1": "A3", "A2": "A3"}


def test_bad_header_is_rejected(tmp_path: Path) -> None:
    path = _csv(tmp_path / "bad.csv", "kind,id", ["author,A1"])
    with pytest.raises(ValueError, match="header must be"):
        load_curation(suppressions_path=path)
