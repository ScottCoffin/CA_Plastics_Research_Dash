"""Tests for the AT-10 release pipeline: methods card, release folder, checksums, site JSON."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas import release

REPO = Path(__file__).resolve().parents[1]
DATE = "2026-11-11"


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


snapshot = _load("build_release_snapshot", "scripts/build_release_snapshot.py")
checker = _load("check_at10", "scripts/check_at10.py")

AUDIT_FIXTURE = """# Audit fixture

| Measure | v2 | v3 |
|---|---:|---:|
| Estimated overall precision | 82.8% | ~77.5% |

| Measure | v2 | v3 | v3.1 |
|---|---:|---:|---:|
| Estimated overall precision | 82.8% | ~77.5% | **~83.8%** |
"""


def _parquet(path: Path, table: dict[str, list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(table), path)


def _fixture_root(tmp_path: Path, *, interim: bool = True, analytics: bool = True) -> Path:
    """A small repository with the inputs the card reads; optional inputs can be dropped."""

    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    shutil.copy2(REPO / "config/queries.yml", root / "config/queries.yml")
    (root / "config/release.yml").write_text(
        "version: v2026.11.11\ndate: 2026-11-11\n"
        "doi: 10.5281/zenodo.24124017\nconcept_doi: 10.5281/zenodo.24124016\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs/QUERY_AUDIT.md").write_text(AUDIT_FIXTURE, encoding="utf-8")
    (root / "site/data/bundle").mkdir(parents=True)
    (root / "site/data/bundle/manifest.json").write_text('{"n_works": 3}', encoding="utf-8")
    works = [
        {"work_id": "W1", "plastic_related": True, "ca_any_author": True},
        {"work_id": "W2", "plastic_related": False, "ca_any_author": True},
        {"work_id": "W3", "plastic_related": None, "ca_any_author": False},
    ]
    (root / "site/data/index.json").write_text(
        json.dumps({"works": works, "authors": [], "counts": {}}), encoding="utf-8"
    )
    _parquet(
        root / "site/data/bundle/parquet/works.parquet",
        {"work_id": ["W1", "W2", "W3"], "year": [2020, 2021, 2022]},
    )
    _parquet(
        root / "site/data/bundle/parquet/year_tag.parquet",
        {"year": [2020], "tag": ["x"], "n": [1]},
    )
    if interim:
        _parquet(
            root / "data/interim/works_raw.parquet",
            {"openalex_id": ["a", "b", "c", "d"], "raw_json": ["{}"] * 4},
        )
    _parquet(
        root / "data/processed/normalized/works.parquet",
        {
            "work_id": ["W1", "W2", "W3"],
            "abstract": ["text", "text", "text"],
            "ca_any_author": [True, None, False],
        },
    )
    if analytics:
        (root / "data/processed/analytics").mkdir(parents=True)
        (root / "data/processed/analytics/manifest.json").write_text(
            json.dumps(
                {
                    "n_works": 2,
                    "exclusions": {
                        "not_in_scope": 1,
                        "not_plastic_related": 0,
                        "retracted": 0,
                        "total_works_in_table": 3,
                    },
                }
            ),
            encoding="utf-8",
        )
    return root


def _full_root(tmp_path: Path) -> Path:
    return _fixture_root(tmp_path)


def test_card_flow_numbers_and_precision_from_fixture_inputs(tmp_path: Path) -> None:
    card = release.methods_card(_full_root(tmp_path), release_date=DATE)
    assert checker.check_card(card) == []
    flow = {key: card["flow"][key]["value"] for key in release.FLOW_KEYS}
    assert flow == {
        "raw_records": 4,
        "after_near_duplicate_collapse": 3,
        "california_authorship": 1,
        "published_after_curation": 3,
        "plastic_related_published": 1,
        "analysed_excluding_retracted": 2,
    }
    assert card["audit_precision"]["value"] == 83.8
    assert card["audit_precision"]["unit"] == "percent"
    assert card["exclusions"]["value"]["not_in_scope"] == 1
    assert card["exclusions"]["source"] == "data/processed/analytics/manifest.json"
    assert card["query"]["version"] == "plastic-v3.1"
    assert card["release_date"] == DATE


def test_missing_inputs_become_null_with_reason(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, interim=False, analytics=False)
    card = release.methods_card(root, release_date=DATE)
    assert checker.check_card(card) == []
    flow = card["flow"]
    assert flow["raw_records"]["value"] is None
    assert "data/interim/works_raw.parquet" in flow["raw_records"]["reason"]
    assert flow["analysed_excluding_retracted"]["value"] is None
    assert (
        "data/processed/analytics/manifest.json" in flow["analysed_excluding_retracted"]["reason"]
    )
    assert flow["published_after_curation"]["value"] == 3
    assert card["exclusions"]["value"] is None
    assert card["exclusions"]["reason"]


def test_bundle_manifest_exclusions_are_used_when_analytics_absent(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path, analytics=False)
    (root / "site/data/bundle/manifest.json").write_text(
        json.dumps({"exclusions": {"retracted": 0}}), encoding="utf-8"
    )
    card = release.methods_card(root, release_date=DATE)
    assert card["exclusions"]["value"] == {"retracted": 0}
    assert card["exclusions"]["source"] == "site/data/bundle/manifest.json"


def test_audit_precision_is_not_invented_when_absent(tmp_path: Path) -> None:
    root = _full_root(tmp_path)
    (root / "docs/QUERY_AUDIT.md").write_text("| Measure | v2 |\n|---|---|\n", encoding="utf-8")
    card = release.methods_card(root, release_date=DATE)
    assert card["audit_precision"]["value"] is None
    assert "v3.1" in card["audit_precision"]["reason"]
    assert checker.check_card(card) == []


def test_source_commit_null_outside_git_has_reason(tmp_path: Path) -> None:
    card = release.methods_card(_full_root(tmp_path), release_date=DATE)
    assert card["source_commit"]["value"] is None
    assert card["source_commit"]["reason"]


def test_markdown_card_has_one_table_and_flow_list(tmp_path: Path) -> None:
    card = release.methods_card(_fixture_root(tmp_path, interim=False), release_date=DATE)
    text = release.render_methods_markdown(card)
    assert text.count("| Item | Value |") == 1
    assert "1. Raw records retrieved: n/a" in text
    assert "3. California authorship (ca_any_author): 1" in text
    assert "Values not available in this checkout:" in text


def test_checksums_are_sha256sum_format_and_verify(tmp_path: Path) -> None:
    written = release.write_release(DATE, out_root=tmp_path / "out", root=_full_root(tmp_path))
    out_dir = Path(written["directory"])
    raw = (out_dir / release.CHECKSUMS_NAME).read_bytes()
    assert b"\r" not in raw
    lines = raw.decode("utf-8").splitlines()
    assert lines and all(re.fullmatch(r"[0-9a-f]{64}  \S.*", line) for line in lines)
    listed = {line.split("  ", 1)[1] for line in lines}
    assert "parquet/works.parquet" in listed and "query.txt" in listed
    assert release.verify_checksums(out_dir) == []
    (out_dir / "query.txt").write_text("changed", encoding="utf-8")
    assert any("checksum mismatch: query.txt" in e for e in release.verify_checksums(out_dir))


def test_query_text_has_version_and_rendered_query(tmp_path: Path) -> None:
    written = release.write_release(DATE, out_root=tmp_path / "out", root=_full_root(tmp_path))
    text = (Path(written["directory"]) / "query.txt").read_text(encoding="utf-8")
    assert "Query version: plastic-v3.1" in text
    assert "microplastic" in text


def test_abstract_parquet_column_is_refused(tmp_path: Path) -> None:
    sample = tmp_path / "bad.parquet"
    _parquet(sample, {"work_id": ["W1"], "Abstract": ["text"]})
    with pytest.raises(release.ReleaseError, match="abstract"):
        release.refuse_abstract_columns(sample)


def test_write_release_refuses_before_writing_when_abstract_present(tmp_path: Path) -> None:
    root = _full_root(tmp_path)
    _parquet(
        root / "site/data/bundle/parquet/works.parquet", {"work_id": ["W1"], "abstract": ["t"]}
    )
    with pytest.raises(release.ReleaseError, match="abstract"):
        release.write_release(DATE, out_root=tmp_path / "out", root=root)
    assert not (tmp_path / "out" / DATE).exists()


def test_release_date_must_be_iso(tmp_path: Path) -> None:
    with pytest.raises(release.ReleaseError, match="YYYY-MM-DD"):
        release.write_release("2026/11/11", out_root=tmp_path, root=_full_root(tmp_path))


def test_snapshot_packs_release_directory_with_licences(tmp_path: Path) -> None:
    written = release.write_release(DATE, out_root=tmp_path / "out", root=_full_root(tmp_path))
    out_dir = Path(written["directory"])
    archive = tmp_path / "snap.zip"
    manifest = snapshot.build_snapshot(
        REPO, archive, "2026.11.10", source_commit=None, release_dir=out_dir
    )
    prefix = f"release/{DATE}/"
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert prefix + "checksums.sha256" in names
        assert prefix + "parquet/works.parquet" in names
        assert zf.read(prefix + "query.txt") == (out_dir / "query.txt").read_bytes()
        readme = zf.read("README.txt").decode("utf-8")
    assert f"release/{DATE}/" in readme
    licences = {item["path"]: item["license"] for item in manifest["files"]}
    assert licences[prefix + "query.txt"].startswith("MIT")
    assert licences[prefix + "parquet/works.parquet"] == snapshot.DATA_LICENSE


def test_snapshot_refuses_abstract_parquet_in_release(tmp_path: Path) -> None:
    release_dir = tmp_path / DATE
    (release_dir / "parquet").mkdir(parents=True)
    _parquet(release_dir / "parquet/works.parquet", {"work_id": ["W1"], "abstract": ["text"]})
    (release_dir / "checksums.sha256").write_text("", encoding="utf-8")
    with pytest.raises(snapshot.SnapshotError, match="abstract"):
        snapshot.build_snapshot(
            REPO, tmp_path / "x.zip", "2026.11.10", source_commit=None, release_dir=release_dir
        )
    assert not (tmp_path / "x.zip").exists()


def test_snapshot_requires_checksums_in_release_directory(tmp_path: Path) -> None:
    release_dir = tmp_path / DATE
    release_dir.mkdir()
    with pytest.raises(snapshot.SnapshotError, match="checksums"):
        snapshot.build_snapshot(
            REPO, tmp_path / "x.zip", "2026.11.10", source_commit=None, release_dir=release_dir
        )


def test_site_release_json_matches_release_yml(tmp_path: Path) -> None:
    root = _full_root(tmp_path)
    payload = release.write_site_release(root)
    written = json.loads((root / release.SITE_RELEASE_JSON).read_text(encoding="utf-8"))
    assert written == payload
    assert payload["doi_url"] == "https://doi.org/10.5281/zenodo.24124017"
    assert payload["concept_url"] == "https://doi.org/10.5281/zenodo.24124016"
    assert payload["version"] == "v2026.11.11"
    assert payload["date"] == DATE


def test_site_release_rejects_bad_doi(tmp_path: Path) -> None:
    root = _full_root(tmp_path)
    (root / "config/release.yml").write_text(
        "version: v1\ndate: 2026-11-11\ndoi: not-a-doi\nconcept_doi: 10.5281/zenodo.1\n",
        encoding="utf-8",
    )
    with pytest.raises(release.ReleaseError, match="not a DOI"):
        release.site_release_payload(root)


def test_committed_release_json_matches_release_yml() -> None:
    assert checker.check_site_release(REPO) == []


def test_zenodo_and_citation_cff_agree() -> None:
    assert checker.check_metadata_agreement(REPO) == []


def test_zenodo_cff_disagreement_is_reported(tmp_path: Path) -> None:
    root = _full_root(tmp_path)
    shutil.copy2(REPO / ".zenodo.json", root / ".zenodo.json")
    (root / "CITATION.cff").write_text(
        (REPO / "CITATION.cff")
        .read_text(encoding="utf-8")
        .replace("license: MIT", "license: CC-BY-4.0"),
        encoding="utf-8",
    )
    assert any("licence" in e for e in checker.check_metadata_agreement(root))
