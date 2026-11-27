"""PLAT-4 slice 4: authorships and institutions partition (synthetic pages in tmp_path)."""

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
    AUTHORSHIPS_FILE,
    INSTITUTIONS_FILE,
    build_partition,
    check_outputs,
    summarize,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "partition_global.py"


def _header(fetched: str) -> dict[str, Any]:
    return {
        "record_type": "page_header",
        "schema_version": 1,
        "query_version": "plastic-test",
        "query_hash": "abc123",
        "slice_year": 2025,
        "page_index": 1,
        "requested_url": "https://api.openalex.org/works?example",
        "run_id": "test-run",
        "fetched_utc": fetched,
        "meta": {"count": 2},
    }


def _write_page(raw_dir: Path, name: str, header: dict[str, Any], works: list[dict]) -> None:
    pages = raw_dir / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(header, sort_keys=True)]
    lines.extend(json.dumps(work, sort_keys=True) for work in works)
    with gzip.open(pages / name, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _inst(
    openalex: str | None, name: str, country: str | None, ror: str | None = None
) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{openalex}" if openalex else None,
        "display_name": name,
        "ror": ror,
        "country_code": country,
        "type": "education",
        "geo": {},
    }


def _work(work_id: str, year: int, authorships: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{work_id}",
        "doi": f"https://doi.org/10.1000/{work_id.lower()}",
        "title": f"Paper {work_id}",
        "publication_year": year,
        "publication_date": f"{year}-03-01",
        "type": "article",
        "language": "en",
        "ids": {"openalex": f"https://openalex.org/{work_id}"},
        "cited_by_count": 1,
        "is_retracted": False,
        "authorships": authorships,
    }


def _author(
    author_id: str | None,
    name: str,
    institutions: list[dict[str, Any]],
    *,
    countries: list[str] | None = None,
    raw: list[str] | None = None,
    corresponding: bool | None = None,
    orcid: str | None = None,
) -> dict[str, Any]:
    return {
        "author_position": "first",
        "author": {
            "id": f"https://openalex.org/{author_id}" if author_id else None,
            "display_name": name,
            "orcid": orcid,
        },
        "institutions": institutions,
        "countries": countries or [],
        "is_corresponding": corresponding,
        "raw_affiliation_strings": raw or [],
        "affiliations": [],
    }


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    """W1 (2025): Ada at X and Y, Bo without institution. W2 (2024): Ada at X, an anonymous one."""
    raw = tmp_path / "raw"
    work_one = _work(
        "W1",
        2025,
        [
            _author(
                "A1",
                "Ada Smith",
                [
                    _inst("I1", "Univ X", "US", "https://ror.org/01"),
                    _inst("I2", "Lab Y", "FR"),
                ],
                countries=["US", "FR"],
                raw=["Dept of Chemistry, Univ X, ada@example.org, CA"],
                corresponding=True,
                orcid="https://orcid.org/0000-0001",
            ),
            _author(
                None,
                "Bo Lee",
                [],
                raw=["Univ Z, contact bo@uni.edu"],
                corresponding=False,
            ),
        ],
    )
    work_two = _work(
        "W2",
        2024,
        [
            _author("A1", "Ada Smith", [_inst("I1", "Univ X", "US")], countries=["US"]),
            _author("A2", "Cy Ng", [_inst(None, "Anon Co", "DE")], countries=["DE"]),
        ],
    )
    _write_page(raw, "p1.jsonl.gz", _header("2025-06-01T00:00:00Z"), [work_one, work_two])
    return raw


def _read(out: Path, name: str) -> list[dict[str, Any]]:
    return pq.read_table(out / name).to_pylist()


def test_one_row_per_institution_with_countries_and_orcid(raw_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out, regions=[])
    rows = [r for r in _read(out, AUTHORSHIPS_FILE) if r["work_id"] == "W1"]
    ada = sorted((r for r in rows if r["author_position"] == 0), key=lambda r: r["institution_id"])
    assert [r["institution_id"] for r in ada] == ["I1", "I2"]
    assert all(r["author_id"] == "A1" and r["author_name"] == "Ada Smith" for r in ada)
    assert all(r["author_countries"] == ["US", "FR"] for r in ada)
    assert all(r["is_corresponding"] is True for r in ada)
    assert all(r["author_orcid"] == "https://orcid.org/0000-0001" for r in ada)
    assert ada[0]["institution_ror"] == "https://ror.org/01"
    assert ada[0]["institution_country"] == "US"
    assert ada[1]["institution_country"] == "FR"


def test_authorship_without_institution_gets_one_null_row_and_null_author_kept(
    raw_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out, regions=[])
    rows = [r for r in _read(out, AUTHORSHIPS_FILE) if r["work_id"] == "W1"]
    bo = [r for r in rows if r["author_position"] == 1]
    assert len(bo) == 1
    assert bo[0]["institution_id"] is None
    assert bo[0]["institution_name"] is None
    assert bo[0]["author_id"] is None
    assert bo[0]["author_name"] == "Bo Lee"
    assert bo[0]["is_corresponding"] is False


def test_emails_are_redacted_from_raw_affiliation_and_nowhere_else(
    raw_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out, regions=[])
    rows = _read(out, AUTHORSHIPS_FILE)
    by_pos = {r["author_position"]: r for r in rows if r["work_id"] == "W1"}
    assert by_pos[0]["raw_affiliation"] == "Dept of Chemistry, Univ X, [email removed], CA"
    assert by_pos[1]["raw_affiliation"] == "Univ Z, contact [email removed]"
    assert all("@" not in str(value) for row in rows for value in row.values() if value)


def test_institutions_aggregate_counts_and_years(raw_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = build_partition(raw_dir, out, regions=[])
    inst = {r["institution_id"]: r for r in _read(out, INSTITUTIONS_FILE)}
    assert set(inst) == {"I1", "I2"}  # the anonymous institution has no id, so no row
    assert inst["I1"]["works_n"] == 2  # W1 and W2
    assert inst["I1"]["authors_n"] == 1  # Ada only; Bo has no institution
    assert inst["I1"]["first_year"] == 2024
    assert inst["I1"]["last_year"] == 2025
    assert inst["I2"]["works_n"] == 1
    assert inst["I2"]["first_year"] == inst["I2"]["last_year"] == 2025
    assert result.authorships == 5  # W1: Ada x2 + Bo; W2: Ada + Cy
    assert result.institutions == 2


def test_latest_page_wins_for_authorships(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    old = _work("W9", 2025, [_author("OLD", "Old Author", [_inst("I7", "Old U", "US")])])
    new = _work("W9", 2025, [_author("NEW", "New Author", [_inst("I8", "New U", "US")])])
    _write_page(raw, "a.jsonl.gz", _header("2025-01-01T00:00:00Z"), [old])
    _write_page(raw, "b.jsonl.gz", _header("2025-02-01T00:00:00Z"), [new])
    out = tmp_path / "out"
    build_partition(raw, out, regions=[])
    rows = _read(out, AUTHORSHIPS_FILE)
    assert [r["author_id"] for r in rows] == ["NEW"]
    assert [r["institution_id"] for r in rows] == ["I8"]


def test_check_outputs_passes_then_flags_count_and_orphan_problems(
    raw_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out, regions=[])
    assert check_outputs(out) == []

    inst_path = out / INSTITUTIONS_FILE
    inst = pq.read_table(inst_path)
    works_n = inst.column("works_n").to_pylist()
    works_n[0] += 1
    pq.write_table(
        inst.set_column(
            inst.schema.get_field_index("works_n"), "works_n", pa.array(works_n, pa.int64())
        ),
        inst_path,
    )
    problems = check_outputs(out)
    assert any("works_n or authors_n differ" in p for p in problems)

    build_partition(raw_dir, out, regions=[])
    auth_path = out / AUTHORSHIPS_FILE
    auth = pq.read_table(auth_path)
    work_ids = auth.column("work_id").to_pylist()
    work_ids[0] = "W404"
    pq.write_table(
        auth.set_column(
            auth.schema.get_field_index("work_id"), "work_id", pa.array(work_ids, pa.string())
        ),
        auth_path,
    )
    assert any("unknown works" in p for p in check_outputs(out))


def test_summarize_reports_authorship_headlines(raw_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    build_partition(raw_dir, out, regions=[])
    counts = summarize(out)
    assert counts["authorships"] == 5
    assert counts["distinct_authors"] == 2  # A1 and A2; the null author is not counted
    assert counts["null_author_id_share"] == pytest.approx(0.2)
    assert counts["institutions"] == 2


def test_cli_check_skips_without_raw_store(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    spec = importlib.util.spec_from_file_location("partition_global_cli", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code = module.main(["--raw-dir", str(tmp_path / "absent"), "--check"])
    assert code == 0
    assert "SKIP" in capsys.readouterr().out
