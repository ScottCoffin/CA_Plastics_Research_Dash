"""Offline acceptance checks for AT-10 (release pipeline).

Builds a release into a temporary directory, both from the working tree and from a
simulated clean checkout (only tracked inputs present, so the gitignored build inputs are
absent and must come out as null with a reason). It then checks:

- ``checksums.sha256`` verifies and every release file is listed;
- the methods card has every required field, and a null value always has a reason;
- no Parquet column contains "abstract";
- the snapshot ZIP packs the release with a licence per file and matching bytes;
- ``site/data/release.json`` matches ``config/release.yml``;
- ``.zenodo.json`` and ``CITATION.cff`` agree on title, creators and licence, and the
  CITATION.cff DOIs match ``config/release.yml``.

Exits 1 on any failure. Makes no network calls, creates no tags or releases, and writes
nothing into the repository except through the explicit ``--write-site-release`` path,
which this check does not call.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas import release  # noqa: E402

ZENODO = ROOT / ".zenodo.json"
CITATION = ROOT / "CITATION.cff"
SNAPSHOT_VERSION = "2026.11.11"
CLEAN_INPUTS = (
    release.QUERY_CONFIG,
    release.AUDIT_DOC,
    release.INDEX_JSON,
    release.BUNDLE_MANIFEST,
    release.RELEASE_YML,
)


def _load_snapshot():
    spec = importlib.util.spec_from_file_location(
        "build_release_snapshot", ROOT / "scripts/build_release_snapshot.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_release_snapshot"] = module
    spec.loader.exec_module(module)
    return module


def check_card(card: dict[str, Any]) -> list[str]:
    """Every required field present; every null value carries a non-empty reason."""

    errors: list[str] = []
    for key in release.REQUIRED_CARD_KEYS:
        if key not in card:
            errors.append(f"methods card lacks {key}")
    for key in release.FLOW_KEYS:
        if key not in card.get("flow", {}):
            errors.append(f"methods card flow lacks {key}")

    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            return
        if {"value", "source", "reason"} <= set(node):
            if node["value"] is None and not node["reason"]:
                errors.append(f"{path} is null without a reason")
            return
        for key, child in node.items():
            walk(child, f"{path}.{key}")

    walk(card, "card")
    return errors


def check_release_dir(out_dir: Path) -> list[str]:
    errors = release.verify_checksums(out_dir)
    parquet_files = sorted((out_dir / "parquet").glob("*.parquet"))
    if not parquet_files:
        errors.append("release has no Parquet files")
    for path in parquet_files:
        hits = [n for n in pq.read_schema(path).names if "abstract" in n.lower()]
        if hits:
            errors.append(f"{path.name} has abstract columns {hits}")
    for name in (release.QUERY_NAME, release.METHODS_MD_NAME):
        if not (out_dir / name).is_file():
            errors.append(f"release lacks {name}")
    card_path = out_dir / release.METHODS_JSON_NAME
    if card_path.is_file():
        errors += check_card(json.loads(card_path.read_text(encoding="utf-8")))
    else:
        errors.append(f"release lacks {release.METHODS_JSON_NAME}")
    return errors


def check_snapshot_release(
    manifest: dict[str, Any], archive_path: Path, out_dir: Path
) -> list[str]:
    errors: list[str] = []
    prefix = f"release/{out_dir.name}/"
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        for item in manifest["files"]:
            if not item["path"].startswith(prefix):
                continue
            if not item.get("license"):
                errors.append(f"no licence recorded for {item['path']}")
            local = out_dir / item["path"][len(prefix) :]
            if archive.read(item["path"]) != local.read_bytes():
                errors.append(f"snapshot bytes differ from release file {item['path']}")
        if prefix + release.CHECKSUMS_NAME not in names:
            errors.append("snapshot lacks the release checksums file")
    return errors


def check_site_release(root: Path = ROOT) -> list[str]:
    try:
        expected = release.site_release_payload(root)
    except (release.ReleaseError, OSError, KeyError) as error:
        return [f"config/release.yml unusable: {error}"]
    target = root / release.SITE_RELEASE_JSON
    if not target.is_file():
        return [f"{release.SITE_RELEASE_JSON.as_posix()} missing; run --write-site-release"]
    actual = json.loads(target.read_text(encoding="utf-8"))
    if actual != expected:
        return ["site/data/release.json does not match config/release.yml"]
    return []


def check_metadata_agreement(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    zenodo = json.loads((root / ZENODO.name).read_text(encoding="utf-8"))
    cff = yaml.safe_load((root / CITATION.name).read_text(encoding="utf-8"))
    if zenodo.get("title") != cff.get("title"):
        errors.append(".zenodo.json and CITATION.cff disagree on title")
    zenodo_creators = [creator["name"] for creator in zenodo.get("creators", [])]
    cff_creators = [f"{a['family-names']}, {a['given-names']}" for a in cff.get("authors", [])]
    if zenodo_creators != cff_creators:
        errors.append(".zenodo.json and CITATION.cff disagree on creators")
    if zenodo.get("license") != cff.get("license"):
        errors.append(".zenodo.json and CITATION.cff disagree on licence")
    meta = release.load_release_yml(root)
    if cff.get("doi") != meta["concept_doi"]:
        errors.append("CITATION.cff doi is not the concept DOI in config/release.yml")
    identifiers = {item.get("value") for item in cff.get("identifiers", [])}
    if not {meta["doi"], meta["concept_doi"]} <= identifiers:
        errors.append("CITATION.cff identifiers lack the release or concept DOI")
    return errors


def _clean_checkout(tmp: Path) -> Path:
    """Copy only the tracked inputs that a fresh clone has; gitignored data stays absent."""

    clean = tmp / "clean"
    for rel in CLEAN_INPUTS:
        (clean / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, clean / rel)
    parquet_dir = clean / release.BUNDLE_PARQUET
    parquet_dir.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / release.BUNDLE_PARQUET).glob("*.parquet"):
        shutil.copy2(source, parquet_dir / source.name)
    return clean


def main() -> int:
    errors: list[str] = []
    errors += check_site_release(ROOT)
    errors += check_metadata_agreement(ROOT)
    snapshot = _load_snapshot()
    date = release.load_release_yml(ROOT)["date"]
    with tempfile.TemporaryDirectory(prefix="at10-check-") as directory:
        tmp = Path(directory)
        for label, source_root in (("checkout", ROOT), ("clean", _clean_checkout(tmp))):
            out = tmp / label / "out"
            written = release.write_release(date, out_root=out, root=source_root)
            out_dir = Path(written["directory"])
            errors += [f"{label}: {error}" for error in check_release_dir(out_dir)]
            if label == "clean":
                flow = written["card"]["flow"]
                if flow["raw_records"]["value"] is not None:
                    errors.append("clean checkout unexpectedly has raw records")
                if written["card"]["source_commit"]["value"] is not None:
                    errors.append("clean directory unexpectedly reports a git commit")
            if label == "checkout":
                archive = tmp / "snapshot.zip"
                manifest = snapshot.build_snapshot(
                    ROOT,
                    archive,
                    SNAPSHOT_VERSION,
                    source_commit=None,
                    release_dir=out_dir,
                )
                errors += check_snapshot_release(manifest, archive, out_dir)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        "AT-10 checks passed: release checksums and methods card verified in a checkout and a "
        "clean checkout; no abstract Parquet columns; snapshot packs the release with licences; "
        "site/data/release.json matches config/release.yml; .zenodo.json and CITATION.cff agree."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
