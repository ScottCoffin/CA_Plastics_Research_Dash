"""GP-5: California-schema institution payloads for a registry region (synthetic inputs only)."""

from __future__ import annotations

import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build import region_export as rx
from atlas.build.export_site import SCHEMA_VERSION as CA_SCHEMA_VERSION
from atlas.build.region_pages import SCREENING_STATUS

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_region_export.py"
CA_KEYS = json.loads(
    (REPO_ROOT / "tests" / "fixtures" / "region_export" / "california_keys.json").read_text(
        encoding="utf-8"
    )
)


def _script():
    spec = importlib.util.spec_from_file_location("build_region_export", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _work(work_id, year, title, topic="Plastic waste", cited=3):
    return {
        "work_id": work_id,
        "title": title,
        "publication_year": year,
        "publication_date": f"{year}-06-01",
        "type": "article",
        "primary_topic_name": topic,
        "cited_by_count": cited,
        "doi": f"https://doi.org/10.1/{work_id}",
    }


def _auth(work_id, pos, author_id, name, inst):
    return {
        "work_id": work_id,
        "author_position": pos,
        "author_id": author_id,
        "author_name": name,
        "author_orcid": None,
        "institution_id": inst,
    }


def _inst(inst_id, name, country, typ):
    return {
        "institution_id": inst_id,
        "display_name": name,
        "ror": f"https://ror.org/{inst_id.lower()}",
        "country_code": country,
        "type": typ,
    }


def _region_inputs() -> rx.RegionInputs:
    works = [
        _work("W1", 2020, "B paper", topic="Microplastics"),
        _work("W2", 2021, "A paper", topic="Recycling"),
        _work("W3", 2021, "Belgian only"),  # country BE only
        _work("W4", 2022, "Registry only"),  # registry_region row, no country row
        _work("W5", 2022, "Foreign institution only"),  # NO country, no NO institution
    ]
    work_regions = [
        {
            "work_id": "W1",
            "region_kind": "country",
            "region_code": "NO",
            "basis": "institution_country",
        },
        {
            "work_id": "W2",
            "region_kind": "country",
            "region_code": "NO",
            "basis": "institution_country",
        },
        {
            "work_id": "W3",
            "region_kind": "country",
            "region_code": "BE",
            "basis": "institution_country",
        },
        {
            "work_id": "W4",
            "region_kind": "registry_region",
            "region_code": "norway",
            "basis": "registry_institution",
        },
        {
            "work_id": "W5",
            "region_kind": "country",
            "region_code": "NO",
            "basis": "institution_country",
        },
    ]
    authorships = [
        _auth("W1", 1, "A1", "Ada One", "I1"),
        _auth("W1", 2, "A2", "Bo Two", "I1"),
        _auth("W1", 3, "A3", "Cy Three", "I4"),
        _auth("W2", 1, "A1", "Ada One", "I1"),
        _auth("W2", 2, "A4", "Di Four", "I2"),
        _auth("W3", 1, "A6", "Ed Six", "I4"),
        _auth("W5", 1, "A5", "Fy Five", "I4"),
    ]
    institutions = [
        _inst("I1", "Norwegian Uni", "NO", "education"),
        _inst("I2", "Norwegian Co", "NO", "company"),
        _inst("I3", "Unused Norwegian Body", "NO", "nonprofit"),  # on no region work
        _inst("I4", "Belgian Uni", "BE", "education"),  # other country
    ]
    return rx.RegionInputs(works, work_regions, authorships, institutions)


def _export(inputs: rx.RegionInputs | None = None) -> rx.RegionExport:
    return rx.build_region_export(
        "norway", "NO", inputs or _region_inputs(), "2026-11-26T00:00:00+00:00"
    )


def test_schema_version_matches_california_builder():
    assert rx.SCHEMA_VERSION == CA_SCHEMA_VERSION


def test_key_sets_match_california_fixture():
    assert set(CA_KEYS["institution"]) == rx.INSTITUTION_KEYS
    assert set(CA_KEYS["top_expert"]) == rx.TOP_EXPERT_KEYS
    assert set(CA_KEYS["institutions_file"]) == rx.INSTITUTIONS_FILE_KEYS
    assert set(CA_KEYS["index_file"]) == rx.INDEX_FILE_KEYS
    assert set(CA_KEYS["index_counts"]) == {
        "authors",
        "ca_institutions",
        "institutions",
        "labeled_works",
        "works",
    }
    assert set(CA_KEYS["index_author"]) == rx.INDEX_AUTHOR_KEYS
    assert set(CA_KEYS["institution_works_file"]) == rx.INSTITUTION_WORKS_FILE_KEYS
    assert set(CA_KEYS["institution_works_institution"]) - {"scope"} == (
        rx.INSTITUTION_WORKS_INSTITUTION_KEYS - {"scope"}
    )
    assert set(CA_KEYS["expert"]) == rx.EXPERT_KEYS
    # Only the screening key is new; every other California key is present.
    assert set(CA_KEYS["index_work"]) | {"screening_status"} == rx.INDEX_WORK_KEYS
    assert set(CA_KEYS["full_work"]) | {"screening_status"} == rx.FULL_WORK_KEYS


def test_region_selection_by_country_code_only():
    export = _export()
    assert [w["work_id"] for w in export.index["works"]] == ["W1", "W2"]


def test_institution_filter_country_and_presence_on_region_work():
    export = _export()
    ids = [row["inst_id"] for row in export.institutions["institutions"]]
    assert ids == ["I1", "I2"]  # I3 has no region work, I4 is Belgian


def test_institution_metrics_and_atlas_type():
    rows = {r["inst_id"]: r for r in _export().institutions["institutions"]}
    i1 = rows["I1"]
    assert i1["work_count"] == 2
    assert i1["author_count"] == 2
    assert i1["years"] == [2020, 2021]
    assert i1["atlas_type"] == "other"  # education maps to other
    assert rows["I2"]["atlas_type"] == "company"
    assert rows["I2"]["work_count"] == 1 and rows["I2"]["author_count"] == 1


def test_top_experts_follow_california_rule_and_shape():
    i1 = {r["inst_id"]: r for r in _export().institutions["institutions"]}["I1"]
    assert [e["author_id"] for e in i1["top_experts"]] == ["A1", "A2"]
    assert i1["top_experts"][0] == {
        "author_id": "A1",
        "in_atlas_index": True,
        "name": "Ada One",
        "topic": "Microplastics",
        "works": 2,
    }


def test_experts_link_only_to_authors_with_an_author_file():
    export = _export()
    assert export.author_files, "fixture should have an author with two or more region works"
    assert set(export.author_files) == {a["author_id"] for a in export.index["authors"]}
    for payload in export.institution_works.values():
        assert payload["experts"], "fixture institutions should have experts"
        for expert in payload["experts"]:
            assert expert["in_atlas_index"] is (expert["author_id"] in export.author_files)


def test_author_files_follow_the_california_layout():
    export = _export()
    for author_id, payload in export.author_files.items():
        assert set(payload) == {"author", "schema_version", "works"}
        assert set(payload["author"]) == rx.AUTHOR_FILE_KEYS
        assert payload["author"]["author_id"] == author_id
        assert payload["author"]["h_index"] is None and payload["author"]["m_quotient"] is None
        assert len(payload["works"]) >= rx.MIN_AUTHOR_WORKS
        for work in payload["works"]:
            assert set(work) == rx.AUTHOR_FILE_WORK_KEYS
            assert author_id in [a["id"] for a in work["authors"]]


def test_author_file_key_sets_match_california_fixture():
    assert set(CA_KEYS["author_file_top"]) == rx.AUTHOR_FILE_TOP_KEYS
    assert set(CA_KEYS["author_file_author"]) == rx.AUTHOR_FILE_KEYS
    # Region works add only the screening key and the author names; the rest is California's.
    assert set(CA_KEYS["author_file_work"]) | {"author_names", "screening_status"} == (
        rx.AUTHOR_FILE_WORK_KEYS
    )


def test_null_california_only_fields_and_region_values():
    export = _export()
    for row in export.institutions["institutions"]:
        assert row["ca_flag"] is False
        assert row["region"] == "norway"
        assert row["domain_tags"] == []
        assert row["lat"] is None and row["lon"] is None and row["city"] is None
    for work in export.index["works"]:
        assert work["screening_status"] == SCREENING_STATUS
        assert work["plastic_related"] is None
        assert work["ca_led"] is None
    for author in export.index["authors"]:
        assert author["h_index"] is None and author["ca_works_count"] is None
    works_file = export.institution_works["I1"]
    assert works_file["institution"]["scope"] == "region"
    assert "ca_connection" not in works_file["works"][0]


def test_institution_works_and_index_references_are_consistent():
    export = _export()
    index_ids = {w["work_id"] for w in export.index["works"]}
    assert set(export.institution_works) == {"I1", "I2"}
    for inst_id, payload in export.institution_works.items():
        assert payload["schema_version"] == rx.SCHEMA_VERSION
        assert payload["institution"]["inst_id"] == inst_id
        assert {w["work_id"] for w in payload["works"]} <= index_ids
    # Index authors are the authors with an author file (two or more region works).
    assert [a["author_id"] for a in export.index["authors"]] == ["A1"]
    assert export.index["counts"]["works"] == 2
    assert export.index["counts"]["institutions"] == 2


def test_output_is_deterministic_under_input_order():
    inputs = _region_inputs()
    first = rx.encode(_export(inputs).institutions)
    rng = random.Random(7)
    shuffled = rx.RegionInputs(
        works=rng.sample(inputs.works, len(inputs.works)),
        work_regions=rng.sample(inputs.work_regions, len(inputs.work_regions)),
        authorships=rng.sample(inputs.authorships, len(inputs.authorships)),
        institutions=rng.sample(inputs.institutions, len(inputs.institutions)),
    )
    assert rx.encode(_export(shuffled).institutions) == first
    assert rx.encode(_export().index) == rx.encode(_export(shuffled).index)


def test_encode_matches_california_json_format():
    data = rx.encode({"b": 1, "a": "é"})
    assert data == b'{"a":"\\u00e9","b":1}\n'


def test_write_then_compare_then_detect_drift(tmp_path):
    export = _export()
    out = tmp_path / "norway"
    sizes = rx.write_export(out, export)
    assert sum(sizes.values()) > 0
    assert rx.compare_export(out, export) == []
    assert rx.validate_structure(out) == []
    assert rx.existing_generated_at(out) == "2026-11-26T00:00:00+00:00"

    (out / "institution_works" / "I2.json").write_bytes(b"{}\n")
    assert rx.compare_export(out, export) == ["stale institution_works/I2.json"]
    (out / "institution_works" / "I9.json").write_bytes(b"{}\n")
    assert "unexpected institution_works/I9.json" in rx.compare_export(out, export)


def test_write_removes_stale_institution_work_files(tmp_path):
    out = tmp_path / "norway"
    rx.write_export(out, _export())
    (out / "institution_works" / "I99.json").write_bytes(b"{}\n")
    rx.write_export(out, _export())
    assert not (out / "institution_works" / "I99.json").exists()


def test_validate_structure_flags_a_changed_key(tmp_path):
    out = tmp_path / "norway"
    rx.write_export(out, _export())
    path = out / "institution_works" / "I1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["works"][0].pop("screening_status")
    path.write_bytes(rx.encode(payload))
    assert any("work W" in p and "keys" in p for p in rx.validate_structure(out))


def test_read_inputs_filters_partition_files(tmp_path):
    part = tmp_path / "global"
    part.mkdir()
    inputs = _region_inputs()
    pq.write_table(
        pa.Table.from_pylist(
            [
                {**w, "screening_status": "unscreened_query_hit", "is_retracted": False}
                for w in inputs.works
            ]
        ),
        part / "works.parquet",
    )
    pq.write_table(pa.Table.from_pylist(inputs.work_regions), part / "work_regions.parquet")
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    **a,
                    "author_orcid": None,
                    "institution_name": "x",
                    "is_corresponding": False,
                    "raw_affiliation": None,
                    "institution_ror": None,
                    "institution_country": None,
                    "institution_type": None,
                    "author_countries": [],
                }
                for a in inputs.authorships
            ]
        ),
        part / "authorships.parquet",
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "institution_id": r["institution_id"],
                    "display_name": r["display_name"],
                    "ror": r["ror"],
                    "country_code": r["country_code"],
                    "type": r["type"],
                    "works_n": 1,
                    "authors_n": 1,
                    "first_year": 2020,
                    "last_year": 2022,
                }
                for r in inputs.institutions
            ]
        ),
        part / "institutions.parquet",
    )
    loaded = rx.read_inputs(part, "NO")
    assert sorted(w["work_id"] for w in loaded.works) == ["W1", "W2", "W5"]
    assert {a["work_id"] for a in loaded.authorships} == {"W1", "W2", "W5"}
    assert sorted(i["institution_id"] for i in loaded.institutions) == ["I1", "I2", "I3"]
    built = rx.build_region_export("norway", "NO", loaded, "2026-11-26T00:00:00+00:00")
    assert [w["work_id"] for w in built.index["works"]] == ["W1", "W2"]


def test_cli_rejects_california_and_checks_without_partition(tmp_path, capsys):
    script = _script()
    assert script.main(["--region", "california", "--check"]) == 2
    out = tmp_path / "norway"
    absent = str(tmp_path / "absent")
    # No committed files yet: structure check fails.
    assert (
        script.main(
            ["--region", "norway", "--check", "--partition-dir", absent, "--out-dir", str(out)]
        )
        == 1
    )
    rx.write_export(out, _export())
    # Committed files present, no partition: structure passes and the staleness check is skipped.
    assert (
        script.main(
            ["--region", "norway", "--check", "--partition-dir", absent, "--out-dir", str(out)]
        )
        == 0
    )
    assert "SKIP" in capsys.readouterr().out


def test_cli_writes_and_checks_with_sys_executable(tmp_path):
    part = tmp_path / "global"
    part.mkdir()
    inputs = _region_inputs()
    pq.write_table(
        pa.Table.from_pylist(
            [
                {**w, "screening_status": "unscreened_query_hit", "is_retracted": False}
                for w in inputs.works
            ]
        ),
        part / "works.parquet",
    )
    pq.write_table(pa.Table.from_pylist(inputs.work_regions), part / "work_regions.parquet")
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    **a,
                    "author_orcid": None,
                    "institution_name": "x",
                    "is_corresponding": False,
                    "raw_affiliation": None,
                    "institution_ror": None,
                    "institution_country": None,
                    "institution_type": None,
                    "author_countries": [],
                }
                for a in inputs.authorships
            ]
        ),
        part / "authorships.parquet",
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "institution_id": r["institution_id"],
                    "display_name": r["display_name"],
                    "ror": r["ror"],
                    "country_code": r["country_code"],
                    "type": r["type"],
                    "works_n": 1,
                    "authors_n": 1,
                    "first_year": 2020,
                    "last_year": 2022,
                }
                for r in inputs.institutions
            ]
        ),
        part / "institutions.parquet",
    )
    out = tmp_path / "norway"
    base = [
        sys.executable,
        str(SCRIPT_PATH),
        "--region",
        "norway",
        "--partition-dir",
        str(part),
        "--out-dir",
        str(out),
    ]
    write = subprocess.run(base, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    assert write.returncode == 0, write.stderr
    check = subprocess.run(
        [*base, "--check"], capture_output=True, text=True, check=False, cwd=REPO_ROOT
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert "PASS" in check.stdout and "SKIP" not in check.stdout


@pytest.mark.parametrize("slug", ["norway", "belgium"])
def test_committed_region_payloads_are_valid(slug):
    folder = REPO_ROOT / "site" / "data" / slug
    if not (folder / "institutions.json").is_file():
        pytest.skip("committed region export not present")
    assert rx.validate_structure(folder) == []
    assert rx.existing_generated_at(folder)


def test_budget_constant_is_twenty_megabytes():
    assert rx.REGION_BUDGET_BYTES == 20_000_000
