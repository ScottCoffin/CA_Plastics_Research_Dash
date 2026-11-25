"""PLAT-4b slice 1: local partition of the global raw store (synthetic pages in tmp_path)."""

from __future__ import annotations

import gzip
import importlib.util
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.ingest.global_partition import (
    SCREENING_UNSCREENED,
    build_partition,
    check_outputs,
    compact_pmid,
    summarize,
    work_region_bases,
    work_row,
)
from atlas.regions import scope
from atlas.regions.registry import Predicate, Region
from atlas.regions.registry import regions as registry_regions

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "partition_global.py"
QUERY_VERSION = "plastic-test"
QUERY_HASH = "abc123"


def _header(fetched: str, page_index: int = 1) -> dict[str, Any]:
    return {
        "record_type": "page_header",
        "schema_version": 1,
        "query_version": QUERY_VERSION,
        "query_hash": QUERY_HASH,
        "slice_year": 2025,
        "page_index": page_index,
        "requested_url": "https://api.openalex.org/works?example",
        "run_id": "test-run",
        "fetched_utc": fetched,
        "meta": {"count": 2},
    }


def _authorship(
    *,
    institutions: list[dict[str, Any]] | None = None,
    countries: list[str] | None = None,
    raw: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "institutions": institutions or [],
        "countries": countries or [],
        "raw_affiliation_strings": raw or [],
        "affiliations": [],
    }


def _work(
    work_id: str,
    *,
    title: str = "A plastics paper",
    pmid: str | None = None,
    authorships: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ids: dict[str, Any] = {"openalex": f"https://openalex.org/{work_id}"}
    if pmid is not None:
        ids["pmid"] = pmid
    return {
        "id": f"https://openalex.org/{work_id}",
        "doi": f"https://doi.org/10.1000/{work_id.lower()}",
        "title": title,
        "publication_year": 2025,
        "publication_date": "2025-03-01",
        "type": "article",
        "language": "en",
        "ids": ids,
        "primary_topic": {"id": "https://openalex.org/T1", "display_name": "x"},
        "is_retracted": False,
        "cited_by_count": 4,
        "authorships": authorships or [],
    }


def _write_page(raw_dir: Path, name: str, header: dict[str, Any], works: list[dict]) -> None:
    pages = raw_dir / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"record_type": "page_header", **header}, sort_keys=True)]
    lines.extend(json.dumps(work, sort_keys=True) for work in works)
    with gzip.open(pages / name, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    california_inst = {
        "country_code": "US",
        "id": "https://openalex.org/I1",
        "geo": {"region": "California", "country_subdivision_code": "CA"},
    }
    _write_page(
        raw,
        "2025_00001.jsonl.gz",
        _header("2026-01-01T00:00:00Z", 1),
        [
            _work(
                "W1",
                title="old title",
                pmid="https://pubmed.ncbi.nlm.nih.gov/123",
                authorships=[_authorship(raw=["Dept X, Example U, Lyon, France"])],
            ),
            _work(
                "W2",
                authorships=[
                    _authorship(
                        institutions=[{"country_code": "US", "id": "https://openalex.org/I9"}],
                        countries=["US", "DE"],
                        raw=["Dept Y, Univ Z, Berlin, Germany"],
                    ),
                    _authorship(
                        institutions=[{"country_code": "DE", "id": "https://openalex.org/I8"}],
                    ),
                ],
            ),
        ],
    )
    _write_page(
        raw,
        "2025_00002.jsonl.gz",
        _header("2026-02-01T00:00:00Z", 2),
        [
            _work(
                "W1",
                title="new title",
                pmid="https://pubmed.ncbi.nlm.nih.gov/123",
                authorships=[_authorship(raw=["Dept X, Example U, Lyon, France"])],
            ),
            _work(
                "W3",
                authorships=[_authorship(institutions=[california_inst])],
            ),
            _work(
                "W4",
                authorships=[
                    _authorship(raw=["Ocean Lab, Univ of Somewhere, Davis, California, USA"])
                ],
            ),
            _work(
                "W5",
                authorships=[_authorship(raw=["Centro de Estudios, Baja California, Mexico"])],
            ),
        ],
    )
    return raw


def test_compact_pmid_strips_pubmed_url() -> None:
    assert compact_pmid("https://pubmed.ncbi.nlm.nih.gov/123") == "123"
    assert compact_pmid("https://pubmed.ncbi.nlm.nih.gov/123/") == "123"
    assert compact_pmid(None) is None
    assert compact_pmid("not-a-pmid") is None


def test_work_row_uses_ids_pmid_and_unscreened_label() -> None:
    row = work_row(_work("W9", pmid="https://pubmed.ncbi.nlm.nih.gov/77"), _header("t"))
    assert row is not None
    assert row["work_id"] == "W9"
    assert row["pmid"] == "77"
    assert row["screening_status"] == SCREENING_UNSCREENED
    assert row["primary_topic_id"] == "T1"
    assert row["query_hash"] == QUERY_HASH


def test_multi_country_work_gets_one_row_per_country() -> None:
    work = _work(
        "W2",
        authorships=[
            _authorship(institutions=[{"country_code": "US"}], countries=["US", "DE"]),
            _authorship(institutions=[{"country_code": "DE"}]),
        ],
    )
    bases = work_region_bases(work, registry_regions(tier="A"))
    assert bases[("country", "US")] == "institution_country"
    assert bases[("country", "DE")] == "institution_country"
    country_rows = [key for key in bases if key[0] == "country"]
    assert sorted(country_rows) == [("country", "DE"), ("country", "US")]


def test_build_dedupes_latest_page_wins(raw_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = build_partition(raw_dir, out)
    works = pq.read_table(result.works_path).to_pylist()
    by_id = {row["work_id"]: row for row in works}
    assert sorted(by_id) == ["W1", "W2", "W3", "W4", "W5"]
    assert by_id["W1"]["title"] == "new title"
    assert by_id["W1"]["pmid"] == "123"


def test_california_predicate_matches_geo_and_raw_but_not_baja(
    raw_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out)
    regions = pq.read_table(out / "work_regions.parquet").to_pylist()
    default = scope.DEFAULT_REGION_SLUG
    matched = {
        row["work_id"]: row["basis"]
        for row in regions
        if row["region_kind"] == "registry_region" and row["region_code"] == default
    }
    assert matched == {"W3": "registry_predicate", "W4": "raw_affiliation"}
    assert ("W5" not in matched) and ("W1" not in matched)
    subdivisions = [row for row in regions if row["region_kind"] == "subdivision"]
    assert [(row["work_id"], row["region_code"]) for row in subdivisions] == [("W3", "US-CA")]


def test_every_row_is_unscreened_and_check_passes(raw_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out)
    statuses = set(pq.read_table(out / "works.parquet").column("screening_status").to_pylist())
    assert statuses == {SCREENING_UNSCREENED}
    assert check_outputs(out) == []


def test_summary_counts(raw_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out)
    counts = summarize(out)
    assert counts["works"] == 5
    assert counts["works_with_pmid"] == 1
    assert counts["default_region_works"] == 2
    assert ("US", 2) in counts["top_countries"]


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("partition_global_cli", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_skips_without_raw_store(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cli = _load_cli()
    code = cli.main(["--raw-dir", str(tmp_path / "absent"), "--check"])
    assert code == 0
    assert "SKIP" in capsys.readouterr().out


def test_cli_check_passes_after_build(raw_dir: Path, tmp_path: Path) -> None:
    cli = _load_cli()
    out = tmp_path / "out"
    assert cli.main(["--raw-dir", str(raw_dir), "--out-dir", str(out)]) == 0
    assert cli.main(["--raw-dir", str(raw_dir), "--out-dir", str(out), "--check"]) == 0


TESTLAND = Region(
    slug="testland",
    name="Testland",
    tier="A",
    parent=None,
    status="planned",
    predicate=Predicate(
        institution_registry="inst.parquet",
        country_codes=("US",),
        institution_region_names=("Testland",),
    ),
)


def _write_registry(root: Path) -> None:
    """Tmp institution registry: I555 belongs to the region; I556 and I557 do not."""
    rows = [
        {"openalex_id": "https://openalex.org/I555", "region": "Testland", "country_code": "US"},
        {"openalex_id": "https://openalex.org/I556", "region": "Elsewhere", "country_code": "US"},
        {"openalex_id": "https://openalex.org/I557", "region": "Testland", "country_code": "MX"},
    ]
    schema = pa.schema([(name, pa.string()) for name in ("openalex_id", "region", "country_code")])
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), root / "inst.parquet")


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the registry-relative path at tmp_path so tests never touch data/."""
    monkeypatch.setattr(scope, "REPO_ROOT", tmp_path)
    _write_registry(tmp_path)
    return tmp_path


def test_registry_institution_ids_follow_region_rule(tmp_repo: Path) -> None:
    assert scope.region_institution_ids(TESTLAND) == frozenset({"I555"})


def test_registry_institution_match_has_basis(tmp_repo: Path) -> None:
    work = _work(
        "W10",
        authorships=[
            _authorship(institutions=[{"id": "https://openalex.org/I555", "country_code": "US"}])
        ],
    )
    ids = {TESTLAND.slug: scope.region_institution_ids(TESTLAND)}
    bases = work_region_bases(work, [TESTLAND], ids)
    assert bases[("registry_region", "testland")] == "registry_institution"


def test_unknown_institution_without_affiliation_text_does_not_match(tmp_repo: Path) -> None:
    work = _work(
        "W11",
        authorships=[
            _authorship(institutions=[{"id": "https://openalex.org/I999", "country_code": "US"}])
        ],
    )
    ids = {TESTLAND.slug: scope.region_institution_ids(TESTLAND)}
    assert ("registry_region", "testland") not in work_region_bases(work, [TESTLAND], ids)


def test_registry_institution_join_in_build(tmp_repo: Path, tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _write_page(
        raw,
        "2025_00001.jsonl.gz",
        _header("2026-01-01T00:00:00Z", 1),
        [
            _work(
                "W20",
                authorships=[
                    _authorship(
                        institutions=[{"id": "https://openalex.org/I555", "country_code": "US"}]
                    )
                ],
            ),
            _work(
                "W21",
                authorships=[
                    _authorship(
                        institutions=[{"id": "https://openalex.org/I556", "country_code": "US"}]
                    )
                ],
            ),
        ],
    )
    out = tmp_path / "out"
    build_partition(raw, out, regions=[TESTLAND])
    rows = pq.read_table(out / "work_regions.parquet").to_pylist()
    matched = [(r["work_id"], r["basis"]) for r in rows if r["region_kind"] == "registry_region"]
    assert matched == [("W20", "registry_institution")]
    assert check_outputs(out) == []


def test_missing_registry_file_warns_and_matches_nothing(tmp_repo: Path) -> None:
    region = Region(
        slug="testland",
        name="Testland",
        tier="A",
        parent=None,
        status="planned",
        predicate=Predicate(institution_registry="absent.parquet", country_codes=("US",)),
    )
    with pytest.warns(UserWarning, match="absent.parquet not found"):
        ids = {region.slug: scope.region_institution_ids(region)}
    assert ids == {region.slug: frozenset()}
    work = _work(
        "W22",
        authorships=[
            _authorship(institutions=[{"id": "https://openalex.org/I555", "country_code": "US"}])
        ],
    )
    assert ("registry_region", "testland") not in work_region_bases(work, [region], ids)


def test_default_region_reads_committed_registry_ids() -> None:
    ids = scope.region_institution_ids()
    assert ids, "the reviewed institution registry should yield California ids"
    assert all(inst_id.startswith("I") for inst_id in ids)
