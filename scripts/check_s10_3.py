"""Offline acceptance checks for S10.3 (reproducibility package and release snapshot).

Runs the fixture rebuild twice and requires byte-identical outputs, builds the release
snapshot into a temporary directory and verifies its manifest checksums and exclusions,
and validates ``.zenodo.json``, the ``reproduce`` Makefile target, the REPRODUCIBILITY
document headings, and the ``dist/`` ignore rule. Makes no network calls and writes
nothing into the repository.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

# A JSON key named abstract*, not a value that merely starts with "Abstract".
ABSTRACT_KEY = re.compile(rb'"abstract[a-z_]*"\s*:')

ROOT = Path(__file__).resolve().parents[1]

ZENODO = Path(".zenodo.json")
MAKEFILE = Path("Makefile")
DOC = Path("docs/REPRODUCIBILITY.md")
GITIGNORE = Path(".gitignore")
ZENODO_KEYS = ("upload_type", "title", "description", "creators", "license", "keywords")
DOC_HEADINGS = (
    "## 1. Fixture rebuild from scratch",
    "## 2. Full live rebuild",
    "## 3. Release snapshot contents",
    "## 4. Release to Zenodo",
    "### Owner steps",
)
FORBIDDEN_PARTS = ("data/raw", "data/interim", ".env")


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.path.insert(0, str(ROOT / "src"))
    spec.loader.exec_module(module)
    return module


def check_zenodo(root: Path) -> list[str]:
    errors: list[str] = []
    payload = json.loads((root / ZENODO).read_text(encoding="utf-8"))
    for key in ZENODO_KEYS:
        if key not in payload:
            errors.append(f".zenodo.json missing {key}")
    if payload.get("upload_type") != "software":
        errors.append(".zenodo.json upload_type must be software")
    if payload.get("title") != "CA Plastics Research Atlas":
        errors.append(".zenodo.json title mismatch")
    if payload.get("creators") != [{"name": "Coffin, Scott"}]:
        errors.append(".zenodo.json creators mismatch")
    if payload.get("license") != "MIT":
        errors.append(".zenodo.json license must be MIT")
    if "CC BY 4.0" not in str(payload.get("description", "")):
        errors.append(".zenodo.json description must note CC BY 4.0 derived data")
    related = payload.get("related_identifiers", [])
    if not any(
        item.get("identifier") == "https://plastiverse.live/"
        and item.get("relation") == "isSupplementTo"
        for item in related
    ):
        errors.append(".zenodo.json lacks isSupplementTo https://plastiverse.live/")
    return errors


def check_make_and_docs(root: Path) -> list[str]:
    errors: list[str] = []
    lines = (root / MAKEFILE).read_text(encoding="utf-8").splitlines()
    if "reproduce:" not in lines:
        errors.append("Makefile lacks a reproduce target")
    elif "scripts/rebuild_from_fixtures.py" not in lines[lines.index("reproduce:") + 1]:
        errors.append("reproduce target does not run scripts/rebuild_from_fixtures.py")
    doc = (root / DOC).read_text(encoding="utf-8")
    for heading in DOC_HEADINGS:
        if heading not in doc:
            errors.append(f"REPRODUCIBILITY.md lacks heading {heading!r}")
    if "make reproduce" not in doc or "/c/rtools45/usr/bin/make.exe" not in doc:
        errors.append("REPRODUCIBILITY.md must document make reproduce")
    ignored = {line.strip() for line in (root / GITIGNORE).read_text().splitlines()}
    if "dist/" not in ignored:
        errors.append(".gitignore must ignore dist/")
    return errors


def check_rebuild(rebuild) -> list[str]:
    """Rebuild twice and require identical outputs; the repo outputs must not change."""
    tracked = sorted((ROOT / "site/data").glob("*.json")) + [ROOT / "site/feed.xml"]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    rows = rebuild.verify_determinism()
    errors: list[str] = []
    paths = {row.path for row in rows}
    for required in ("site/data/index.json", "site/data/grants.json", "site/feed.xml"):
        if required not in paths:
            errors.append(f"fixture rebuild did not produce {required}")
    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    if before != after:
        errors.append("fixture rebuild changed committed site outputs")
    return errors


def check_snapshot(snapshot, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="s10-3-check-") as directory:
        output = Path(directory) / "atlas-snapshot-check.zip"
        manifest = snapshot.build_snapshot(root, output, "2026.11.10", source_commit=None)
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            if "MANIFEST.json" not in names or "README.txt" not in names:
                errors.append("snapshot lacks MANIFEST.json or README.txt")
            embedded = json.loads(archive.read("MANIFEST.json"))
            if embedded != manifest:
                errors.append("embedded MANIFEST.json differs from the returned manifest")
            for item in manifest["files"]:
                data = archive.read(item["path"])
                if hashlib.sha256(data).hexdigest() != item["sha256"]:
                    errors.append(f"checksum mismatch for {item['path']}")
                if len(data) != item["bytes"]:
                    errors.append(f"byte count mismatch for {item['path']}")
                if not item.get("license"):
                    errors.append(f"no licence recorded for {item['path']}")
                if item["path"].endswith(".json") and ABSTRACT_KEY.search(data.lower()):
                    errors.append(f"abstract-bearing JSON packaged: {item['path']}")
            listed = {item["path"] for item in manifest["files"]} | {"MANIFEST.json"}
            if listed != names:
                errors.append("zip members and manifest disagree")
        for name in names:
            if any(part in name for part in FORBIDDEN_PARTS):
                errors.append(f"excluded path packaged: {name}")
    return errors


def main() -> int:
    rebuild = _load("rebuild_from_fixtures", "scripts/rebuild_from_fixtures.py")
    snapshot = _load("build_release_snapshot", "scripts/build_release_snapshot.py")
    errors: list[str] = []
    errors += check_zenodo(ROOT)
    errors += check_make_and_docs(ROOT)
    errors += check_rebuild(rebuild)
    errors += check_snapshot(snapshot)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("S10.3 checks passed: fixture rebuild deterministic, snapshot manifest verified,")
    print(".zenodo.json valid, reproduce target and REPRODUCIBILITY headings present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
