"""Tests for the S10.3 reproducibility package: fixture rebuild, release snapshot, metadata."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rebuild = _load("rebuild_from_fixtures", "scripts/rebuild_from_fixtures.py")
snapshot = _load("build_release_snapshot", "scripts/build_release_snapshot.py")
checker = _load("check_s10_3", "scripts/check_s10_3.py")


def test_fixture_rebuild_is_byte_identical_and_covers_public_outputs() -> None:
    rows = rebuild.verify_determinism()
    paths = {row.path for row in rows}
    assert {"site/data/index.json", "site/data/grants.json", "site/feed.xml"} <= paths
    assert all(row.sha256 and row.bytes > 0 for row in rows)


def test_fixture_rebuild_leaves_committed_site_untouched() -> None:
    tracked = sorted((REPO / "site/data").glob("*.json")) + [REPO / "site/feed.xml"]
    before = {p: p.read_bytes() for p in tracked}
    rebuild.verify_determinism()
    assert {p: p.read_bytes() for p in tracked} == before


def test_fixture_grants_drop_abstracts_from_public_export() -> None:
    rows = {row.path for row in rebuild.verify_determinism()}
    assert "site/data/grants.json" in rows
    grants = (REPO / "site/data/grants.json").read_text(encoding="utf-8")
    assert '"abstract' not in grants.lower()


def test_excluded_path_rules() -> None:
    assert snapshot._is_excluded("data/raw/openalex_works/x.json")
    assert snapshot._is_excluded("data/interim/works_raw.parquet")
    assert snapshot._is_excluded("data/logs/api_usage.jsonl")
    assert snapshot._is_excluded(".env")
    assert snapshot._is_excluded("config/.env.local")
    assert not snapshot._is_excluded("site/data/index.json")
    assert not snapshot._is_excluded("curation/gold_works.csv")


def test_snapshot_contents_manifest_and_checksums(tmp_path: Path) -> None:
    output = tmp_path / "atlas-snapshot-test.zip"
    manifest = snapshot.build_snapshot(REPO, output, "2026.11.10", source_commit=None)
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert {"MANIFEST.json", "README.txt", "site/feed.xml"} <= names
        assert "site/data/index.json" in names
        assert "curation/gold_works.csv" in names
        assert "config/queries.yml" in names
        assert not any(name.startswith("site/data/authors/") for name in names)
        embedded = json.loads(archive.read("MANIFEST.json"))
        assert embedded == manifest
        for item in manifest["files"]:
            data = archive.read(item["path"])
            assert len(data) == item["bytes"]
            assert snapshot.hashlib.sha256(data).hexdigest() == item["sha256"]
            assert item["license"]
        assert names == {item["path"] for item in manifest["files"]} | {"MANIFEST.json"}
        assert all(not snapshot._is_excluded(name) for name in names)
        readme = archive.read("README.txt").decode("utf-8")
    assert "Coffin, S. (2026)" in readme
    assert "CC BY 4.0" in readme


def test_snapshot_is_deterministic_for_fixed_inputs(tmp_path: Path) -> None:
    first = tmp_path / "a.zip"
    second = tmp_path / "b.zip"
    snapshot.build_snapshot(REPO, first, "2026.11.10", source_commit="abc")
    snapshot.build_snapshot(REPO, second, "2026.11.10", source_commit="abc")
    assert first.read_bytes() == second.read_bytes()


def _mini_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "site/data").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "curation").mkdir()
    (root / "site/data/index.json").write_text('{"counts": {}, "works": []}', encoding="utf-8")
    (root / "site/feed.xml").write_text("<feed/>", encoding="utf-8")
    shutil.copy2(REPO / "config/queries.yml", root / "config/queries.yml")
    shutil.copy2(REPO / "config/taxonomy.yml", root / "config/taxonomy.yml")
    return root


def test_snapshot_refuses_json_field_named_abstract(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    (root / "site/data/index.json").write_text(
        '{"works": [{"id": "W1", "abstract": "text"}]}', encoding="utf-8"
    )
    with pytest.raises(snapshot.SnapshotError, match="abstract"):
        snapshot.build_snapshot(root, tmp_path / "out.zip", "2026.11.10")
    assert not (tmp_path / "out.zip").exists()


def test_snapshot_refuses_csv_header_named_abstract(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    (root / "curation/gold_works.csv").write_text("work_id,Abstract\nW1,text\n", encoding="utf-8")
    with pytest.raises(snapshot.SnapshotError, match="abstract"):
        snapshot.build_snapshot(root, tmp_path / "out.zip", "2026.11.10")


def test_snapshot_rejects_unsafe_version(tmp_path: Path) -> None:
    root = _mini_root(tmp_path)
    with pytest.raises(snapshot.SnapshotError, match="invalid snapshot version"):
        snapshot.build_snapshot(root, tmp_path / "out.zip", "../escape")


def test_default_output_directory_is_gitignored() -> None:
    ignored = {line.strip() for line in (REPO / ".gitignore").read_text().splitlines()}
    assert "dist/" in ignored


def test_zenodo_metadata_has_required_keys() -> None:
    assert checker.check_zenodo(REPO) == []
    payload = json.loads((REPO / ".zenodo.json").read_text(encoding="utf-8"))
    assert payload["upload_type"] == "software"
    assert payload["license"] == "MIT"
    assert payload["creators"] == [{"name": "Coffin, Scott"}]


def test_zenodo_check_rejects_wrong_upload_type(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    payload = json.loads((REPO / ".zenodo.json").read_text(encoding="utf-8"))
    payload["upload_type"] = "dataset"
    (root / ".zenodo.json").write_text(json.dumps(payload), encoding="utf-8")
    assert any("upload_type" in error for error in checker.check_zenodo(root))


def test_makefile_and_doc_checks_pass() -> None:
    assert checker.check_make_and_docs(REPO) == []
