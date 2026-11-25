"""Offline tests for scripts/build_pubmed_coverage_json.py (BQ-S9 part C).

Tiny in-memory fixtures only. Nothing here reads data/interim/ or the network. The committed-payload
checks read site/data/california/pubmed_coverage.json and skip when it is not built.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from atlas.nlp.active_relevance import wilson_interval

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_pubmed_coverage_json.py"
OUTPUT = ROOT / "site" / "data" / "california" / "pubmed_coverage.json"
TAXONOMY_PATH = ROOT / "config" / "failure_taxonomy.yml"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("build_pubmed_coverage_json", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load()

TAXONOMY = builder.Taxonomy(
    version="failure-taxonomy-v1",
    class_ids=["plasticity_collision", "pubmed_only_record", "non_english_text"],
    false_negative_ids=["pubmed_only_record"],
)


def _ref(pmid: int, doi: str | None = None, year: int | None = 2020) -> dict[str, Any]:
    return {
        "pmid": str(pmid),
        "doi": doi,
        "pub_year": year,
        "chunk_id": "c001",
        "partition": "1950/01/01..2026/11/21",
    }


def _work(work_id: str, pmid: str | None = None, doi: str | None = None) -> dict[str, Any]:
    return {"work_id": work_id, "pmid": pmid, "doi": doi}


def _run(name: str, rows: list[dict[str, Any]]) -> Any:
    manifest = {
        "schema": builder.MANIFEST_SCHEMA,
        "reference_set": name,
        "affiliation": "California",
        "query_translation": f"{name} translation",
        "run_timestamp": "2026-11-23T05:00:00+00:00",
    }
    return builder.ReferenceRun(name, rows, manifest, "a" * 64)


def _fixture() -> tuple[list[Any], Any]:
    """Two reference sets over a five-work normalized table (three published, two not)."""
    r1 = _run(
        "r1",
        [
            _ref(1),
            _ref(2, year=2020),
            _ref(3, year=2021),
            _ref(4, year=None),
            _ref(5, doi="10.9/ABC", year=2021),
        ],
    )
    r2 = _run("r2", [_ref(2, doi="10.1/two"), _ref(6, year=2022), _ref(1)])
    published = [
        _work("W1", pmid="1"),
        _work("W3", pmid="3"),
        _work("W6", doi="https://doi.org/10.9/abc"),
    ]
    unpublished = [_work("W2", pmid="2"), _work("W7", pmid="4", doi="10.1/four")]
    atlas = builder.AtlasWorks(normalized=published + unpublished, published=published)
    return [r1, r2], atlas


def _build(runs: list[Any], atlas: Any, sheet: list[dict[str, str]] | None = None) -> Any:
    return builder.build_payload(
        runs=runs,
        atlas=atlas,
        taxonomy=TAXONOMY,
        existing_sheet=sheet,
        generated_at="2026-11-23T00:00:00+00:00",
    )


def _sheet_row(pmid: str, triage_class: str = "", **extra: str) -> dict[str, str]:
    row = {column: "" for column in builder.TRIAGE_COLUMNS}
    row.update(pmid=pmid, triage_class=triage_class, reference_sets="r1", **extra)
    return row


def _all_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [key for item in value.values() for key in _all_keys(item)] + list(value)
    if isinstance(value, list):
        return [key for item in value for key in _all_keys(item)]
    return []


# --- Coverage and joins -------------------------------------------------------------------------


def test_coverage_math_and_by_year() -> None:
    runs, atlas = _fixture()
    payload, _ = _build(runs, atlas)
    block = payload["reference_sets"]["r1"]

    assert block["reference_pmids"] == 5
    assert block["found_published"] == 3
    assert block["found_published_by_pmid"] == 2
    assert block["found_published_by_doi"] == 1
    assert block["misses"] == 2
    assert block["coverage_published"] == 0.6
    assert block["coverage_by_year"] == {
        "2020": {"reference": 2, "found": 1, "coverage": 0.5},
        "2021": {"reference": 2, "found": 2, "coverage": 1.0},
        "unknown": {"reference": 1, "found": 0, "coverage": 0.0},
    }


def test_doi_fallback_matches_case_and_prefix_insensitively() -> None:
    runs, atlas = _fixture()
    payload, _ = _build(runs, atlas)
    # PMID 5 has DOI 10.9/ABC; the published work stores https://doi.org/10.9/abc with no PMID.
    assert payload["reference_sets"]["r1"]["found_published_by_doi"] == 1
    assert payload["reference_sets"]["r2"]["found_published_by_doi"] == 0


def test_unpublished_corpus_and_join_rates() -> None:
    runs, atlas = _fixture()
    payload, _ = _build(runs, atlas)
    r1 = payload["reference_sets"]["r1"]
    r2 = payload["reference_sets"]["r2"]

    # PMIDs 2 and 4 are misses of the published set but sit in the normalized table.
    assert r1["found_unpublished_corpus"] == 2
    assert r2["found_unpublished_corpus"] == 1
    assert r1["join_rate"] == {"published": 0.6667, "normalized": 0.8}
    assert payload["atlas_corpus"] == {
        "published_works": 3,
        "published_with_pmid": 2,
        "normalized_works": 5,
        "normalized_with_pmid": 4,
    }


def test_misses_are_unioned_and_tagged_with_their_sets() -> None:
    runs, atlas = _fixture()
    _, sheet = _build(runs, atlas)
    by_pmid = {row["pmid"]: row for row in sheet}

    assert sorted(by_pmid) == ["2", "4", "6"]
    assert by_pmid["2"]["reference_sets"] == "r1;r2"
    assert by_pmid["2"]["doi"] == "10.1/two"  # filled from r2 where r1 has no DOI
    assert by_pmid["2"]["in_normalized_corpus"] == "true"
    assert by_pmid["2"]["atlas_work_id"] == "W2"
    assert by_pmid["4"]["reference_sets"] == "r1"
    assert by_pmid["4"]["atlas_work_id"] == "W7"
    assert by_pmid["6"]["in_normalized_corpus"] == "false"
    assert by_pmid["6"]["atlas_work_id"] == ""


# --- Miss sample --------------------------------------------------------------------------------


def test_sample_is_deterministic_and_capped() -> None:
    misses = [
        {"pmid": str(1000 + i), "doi": None, "pub_year": 2020, "reference_sets": ["r1"]}
        for i in range(120)
    ]
    first = builder.select_sample(misses)
    assert first == builder.select_sample(list(reversed(misses)))
    assert len(first) == builder.SAMPLE_CAP == 50
    expected = sorted(misses, key=lambda item: builder.sample_key(item["pmid"]))[:50]
    assert sorted(first, key=lambda item: int(item["pmid"])) == sorted(
        expected, key=lambda item: int(item["pmid"])
    )
    assert builder.sample_key("1000") == hashlib.sha256(b"20261122:1000").hexdigest()


def test_sample_takes_all_misses_below_the_cap() -> None:
    misses = [
        {"pmid": str(i), "doi": None, "pub_year": None, "reference_sets": ["r2"]} for i in (7, 3, 9)
    ]
    sample = builder.select_sample(misses)
    assert [item["pmid"] for item in sample] == ["3", "7", "9"]


# --- Triage sheet -------------------------------------------------------------------------------


def test_labelled_sheet_is_never_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "pubmed_miss_triage_v1.csv"
    labelled = [_sheet_row("2", triage_class="pubmed_only_record", reviewer="tester")]
    path.write_text(builder.triage_csv_text(labelled), encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(builder.TriageOverwriteError):
        builder.write_triage_sheet(path, [_sheet_row("2")])
    assert path.read_bytes() == before


def test_note_only_sheet_is_also_protected(tmp_path: Path) -> None:
    path = tmp_path / "triage.csv"
    path.write_text(builder.triage_csv_text([_sheet_row("2", note="check")]), encoding="utf-8")
    with pytest.raises(builder.TriageOverwriteError):
        builder.write_triage_sheet(path, [_sheet_row("2")])


def test_blank_sheet_is_replaced_with_lf_and_the_fixed_columns(tmp_path: Path) -> None:
    path = tmp_path / "triage.csv"
    path.write_text(builder.triage_csv_text([_sheet_row("9")]), encoding="utf-8")
    fresh = [_sheet_row("2", doi="10.1/two", pub_year="2020")]
    builder.write_triage_sheet(path, fresh)
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert raw.splitlines()[0].decode() == ",".join(builder.TRIAGE_COLUMNS)
    assert raw.splitlines()[1].decode().startswith("2,10.1/two,2020,r1,")


def test_unknown_triage_class_is_rejected() -> None:
    runs, atlas = _fixture()
    _, sheet = _build(runs, atlas)
    sheet[0]["triage_class"] = "not_a_class"
    with pytest.raises(builder.BuildError, match="not_a_class"):
        _build(runs, atlas, sheet)


def test_sheet_with_different_pmids_is_rejected() -> None:
    runs, atlas = _fixture()
    _, sheet = _build(runs, atlas)
    sheet[0]["triage_class"] = "pubmed_only_record"
    with pytest.raises(builder.BuildError, match="different PMIDs"):
        _build(runs, atlas, sheet[:2])


# --- Wilson interval and triage summary ---------------------------------------------------------


def test_wilson_interval_only_when_labelled() -> None:
    runs, atlas = _fixture()
    payload, sheet = _build(runs, atlas)
    triage = payload["miss_triage"]
    assert triage["sample_size"] == 3
    assert triage["seed"] == builder.SAMPLE_SEED == 20261122
    assert triage["labelled"] == 0
    assert triage["status"] == "pending owner triage"
    assert "false_negative_share" not in triage

    labels = {"2": "pubmed_only_record", "4": "non_english_text", "6": "non_english_text"}
    for row in sheet:
        row["triage_class"] = labels[row["pmid"]]
    labelled, _ = _build(runs, atlas, sheet)
    triage = labelled["miss_triage"]
    assert triage["labelled"] == 3
    assert "status" not in triage
    share = triage["false_negative_share"]
    assert (share["count"], share["n"]) == (1, 3)
    lower, upper = wilson_interval(1, 3)
    assert share["wilson_95"] == [round(lower, 4), round(upper, 4)]


def test_load_taxonomy_reads_class_ids_and_false_negative_direction() -> None:
    taxonomy = builder.load_taxonomy(TAXONOMY_PATH)
    assert "pubmed_only_record" in taxonomy.class_ids
    assert "pubmed_only_record" in taxonomy.false_negative_ids
    assert "plasticity_collision" not in taxonomy.false_negative_ids


# --- Inputs and CLI -----------------------------------------------------------------------------


def test_reference_run_loads_and_checks_manifest_counts(tmp_path: Path) -> None:
    header = ",".join(builder.ROW_FIELDS)
    (tmp_path / "r1_california_pmids.csv").write_text(
        f"{header}\n100,10.1/a,2020,c001,p\n101,,2021,c001,p\n", encoding="utf-8"
    )
    manifest = {
        "schema": builder.MANIFEST_SCHEMA,
        "reference_set": "r1",
        "affiliation": "California",
        "query_translation": "t",
        "run_timestamp": "2026-11-23T05:00:00+00:00",
        "total_unique_pmids": 2,
    }
    manifest_bytes = json.dumps(manifest).encode("utf-8")
    (tmp_path / "r1_california_manifest.json").write_bytes(manifest_bytes)

    run = builder.load_reference_run("r1", tmp_path)
    assert [row["pmid"] for row in run.rows] == ["100", "101"]
    assert run.rows[1]["doi"] is None
    assert run.manifest_sha256 == hashlib.sha256(manifest_bytes).hexdigest()

    manifest["total_unique_pmids"] = 3
    (tmp_path / "r1_california_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(builder.BuildError, match="total_unique_pmids"):
        builder.load_reference_run("r1", tmp_path)


def test_atlas_join_uses_normalized_pmid_for_published_ids(tmp_path: Path) -> None:
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    table = pa.table(
        {
            "work_id": ["W1", "W2"],
            "doi": ["10.1/a", None],
            "pmid": ["1", None],
        }
    )
    works = tmp_path / "works.parquet"
    pq.write_table(table, works)
    index = tmp_path / "index.json"
    index.write_text(json.dumps({"works": [{"work_id": "W1"}]}), encoding="utf-8")

    atlas = builder.load_atlas(works, index)
    assert atlas.published == [{"work_id": "W1", "doi": "10.1/a", "pmid": "1"}]
    assert len(atlas.normalized) == 2

    index.write_text(json.dumps({"works": [{"work_id": "W9"}]}), encoding="utf-8")
    with pytest.raises(builder.BuildError, match="not in works.parquet"):
        builder.load_atlas(works, index)


def test_check_skips_when_interim_inputs_are_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(builder, "INTERIM_DIR", tmp_path / "absent")
    assert builder.main(["--check"]) == 0
    assert "SKIP" in capsys.readouterr().out


def test_build_without_interim_inputs_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(builder, "INTERIM_DIR", tmp_path / "absent")
    assert builder.main([]) == 1
    assert "missing interim input" in capsys.readouterr().err


def test_same_payload_ignores_generated_at() -> None:
    runs, atlas = _fixture()
    payload, _ = _build(runs, atlas)
    later = dict(payload, generated_at="2030-01-01T00:00:00+00:00")
    assert builder.same_payload(later, payload)
    changed = json.loads(json.dumps(payload))
    changed["stage"] = 2
    assert not builder.same_payload(changed, payload)


# --- Public wording and committed payload -------------------------------------------------------


def test_fixture_payload_has_no_recall_or_expert_wording() -> None:
    runs, atlas = _fixture()
    payload, _ = _build(runs, atlas)
    text = json.dumps(payload).lower()
    assert "recall" not in text
    assert "expert" not in text
    assert not any("recall" in key.lower() for key in _all_keys(payload))


def test_fixture_payload_names_the_stage_version_and_triage_file() -> None:
    runs, atlas = _fixture()
    payload, _ = _build(runs, atlas)
    assert payload["schema_version"] == "bqs-pm-v1"
    assert payload["stage"] == 1
    assert payload["failure_taxonomy_version"] == "failure-taxonomy-v1"
    assert payload["miss_triage"]["triage_file"] == "curation/pubmed_miss_triage_v1.csv"
    assert payload["triage_classes"] == TAXONOMY.class_ids


@pytest.mark.skipif(
    not OUTPUT.exists(), reason="site/data/california/pubmed_coverage.json is not built"
)
def test_committed_payload_schema() -> None:
    text = OUTPUT.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["schema_version"] == "bqs-pm-v1"
    assert payload["stage"] == 1
    assert {"generated_at", "definition", "atlas_corpus", "reference_sets"} <= set(payload)
    assert set(payload["reference_sets"]) == {"r1", "r2"}
    for block in payload["reference_sets"].values():
        assert {
            "reference_pmids",
            "found_published",
            "found_published_by_pmid",
            "found_published_by_doi",
            "found_unpublished_corpus",
            "coverage_published",
            "coverage_by_year",
            "join_rate",
            "manifest_sha256",
            "run_timestamp",
            "query_translation",
            "affiliation",
            "stage",
        } <= set(block)
        assert len(block["manifest_sha256"]) == 64
        for year_block in block["coverage_by_year"].values():
            assert set(year_block) == {"reference", "found", "coverage"}
    triage = payload["miss_triage"]
    assert triage["seed"] == 20261122
    if triage["labelled"] == 0:
        assert triage["status"] == "pending owner triage"
        assert "false_negative_share" not in triage
    taxonomy = builder.load_taxonomy(TAXONOMY_PATH)
    assert payload["triage_classes"] == taxonomy.class_ids
    assert "recall" not in text.lower()
    assert "expert" not in text.lower()
