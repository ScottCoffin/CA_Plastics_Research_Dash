"""Tests for scripts/check_gold_releases.py (BQ-G6 release rules)."""

import hashlib
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_gold_releases.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_gold_releases", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _release(version: str, files: dict[str, str]) -> dict:
    return {
        "version": version,
        "files": files,
        "release_date": "2026-12-01",
        "licence": "CC BY 4.0",
    }


def _manifest(*releases: dict) -> dict:
    return {"schema": "gold-releases-v1", "releases": list(releases)}


def _write(root: Path, rel: str, data: bytes) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha(data)


def test_empty_manifest_passes(tmp_path):
    assert check.check_releases(_manifest(), tmp_path) == []


def test_empty_manifest_main_message(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "gold_releases.json"
    manifest_path.write_text('{"schema": "gold-releases-v1", "releases": []}', encoding="utf-8")
    monkeypatch.setattr(check, "MANIFEST_PATH", manifest_path)
    assert check.main() == 0
    assert "no gold release yet; nothing to protect" in capsys.readouterr().out


def test_matching_hashes_pass(tmp_path):
    sha = _write(tmp_path, "curation/gold_v1/works.csv", b"work_id\nW1\n")
    manifest = _manifest(_release("gold_v1", {"curation/gold_v1/works.csv": sha}))
    assert check.check_releases(manifest, tmp_path) == []


def test_edited_released_file_fails_with_name(tmp_path):
    sha = _write(tmp_path, "curation/gold_v1/works.csv", b"work_id\nW1\n")
    manifest = _manifest(_release("gold_v1", {"curation/gold_v1/works.csv": sha}))
    _write(tmp_path, "curation/gold_v1/works.csv", b"work_id\nW1 edited\n")
    errors = check.check_releases(manifest, tmp_path)
    assert len(errors) == 1
    assert "curation/gold_v1/works.csv" in errors[0]
    assert "changed" in errors[0]


def test_missing_released_file_fails_with_name(tmp_path):
    manifest = _manifest(_release("gold_v1", {"curation/gold_v1/labels.csv": _sha(b"x")}))
    errors = check.check_releases(manifest, tmp_path)
    assert len(errors) == 1
    assert "curation/gold_v1/labels.csv" in errors[0]
    assert "missing" in errors[0]


def test_duplicate_versions_fail(tmp_path):
    sha_a = _write(tmp_path, "curation/a.csv", b"a")
    sha_b = _write(tmp_path, "curation/b.csv", b"b")
    manifest = _manifest(
        _release("gold_v1", {"curation/a.csv": sha_a}),
        _release("gold_v1", {"curation/b.csv": sha_b}),
    )
    errors = check.check_releases(manifest, tmp_path)
    assert any("duplicate release version 'gold_v1'" in error for error in errors)


def test_new_version_reusing_old_path_fails(tmp_path):
    sha = _write(tmp_path, "curation/gold_works.csv", b"work_id\n")
    manifest = _manifest(
        _release("gold_v1", {"curation/gold_works.csv": sha}),
        _release("gold_v1.1", {"curation/gold_works.csv": sha}),
    )
    errors = check.check_releases(manifest, tmp_path)
    assert any("curation/gold_works.csv" in error and "reused" in error for error in errors)


def test_new_version_with_new_path_passes(tmp_path):
    sha_1 = _write(tmp_path, "curation/gold_v1.csv", b"v1")
    sha_2 = _write(tmp_path, "curation/gold_v1.1.csv", b"v1.1")
    manifest = _manifest(
        _release("gold_v1", {"curation/gold_v1.csv": sha_1}),
        _release("gold_v1.1", {"curation/gold_v1.1.csv": sha_2}),
    )
    assert check.check_releases(manifest, tmp_path) == []


def test_wrong_schema_fails(tmp_path):
    errors = check.check_releases({"schema": "other", "releases": []}, tmp_path)
    assert errors and "schema" in errors[0]
