"""Package the versioned release snapshot ZIP for Zenodo archiving (S10.3, AT-10).

The ZIP holds only public and curated files: ``site/data/*.json``, ``site/feed.xml``,
the gold and split files in ``curation/``, and the query and taxonomy definitions in
``config/``. It also holds a ``MANIFEST.json`` (path, bytes, sha256, license per file)
and a ``README.txt`` with the citation. Raw and interim data, ``.env`` files, and any
field named ``abstract`` are refused, and the build fails rather than dropping data.

AT-10 adds two options. ``--release-date YYYY-MM-DD`` writes ``release/<date>/`` (see
``atlas.release``) and packs its contents under ``release/<date>/``. ``--write-site-release``
writes ``site/data/release.json`` from ``config/release.yml`` and exits.

Offline only. The default output is ``dist/atlas-snapshot-<version>.zip``, which the
repository's ``.gitignore`` already excludes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from atlas.release import (  # noqa: E402
    ReleaseError,
    refuse_abstract_columns,
    write_release,
    write_site_release,
)

SCHEMA_VERSION = "s10.3"
CODE_LICENSE = "MIT"
DATA_LICENSE = "CC BY 4.0"
LICENSE_STATUS = "confirmed by owner 2026-11-10; see LICENSE and LICENSE-DATA.md"
REPO_URL = "https://github.com/ScottCoffin/CA_Plastics_Research_Dash"
SITE_URL = "https://plastiverse.live/"
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,63}$")
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
EXCLUDED_PREFIXES = ("data/raw", "data/interim", "data/logs")
EXCLUDED_NAMES = (".env",)
ABSTRACT_PREFIX = "abstract"
MONITORING_NOTE = (
    "Contains SF Bay and Adjacent Sanctuaries microplastic rows (SFEI and 5 Gyres; OPC "
    "on data.cnra.ca.gov), CC BY 4.0 by owner determination 2026-11-10. See docs/REUSE.md."
)
GRANTS_NOTE = (
    "Award rows as reported by each public funder source (see docs/REUSE.md and the "
    "caveat field). Amounts follow each source's own basis."
)


class SnapshotError(RuntimeError):
    """Raised when a file must not enter the snapshot."""


@dataclass(frozen=True)
class Entry:
    path: str  # snapshot member path (repository-relative POSIX path)
    license: str
    notes: str = ""
    source: Path | None = None  # file to read when it is not at ``root / path``


def _is_excluded(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if any(path == prefix or path.startswith(prefix + "/") for prefix in EXCLUDED_PREFIXES):
        return True
    return any(part in EXCLUDED_NAMES or part.startswith(".env.") for part in parts)


def _json_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key))
            keys |= _json_keys(child)
    elif isinstance(value, list):
        for child in value:
            keys |= _json_keys(child)
    return keys


def _check_no_abstract(path: Path, entry: Entry) -> None:
    if path.suffix == ".json":
        keys = _json_keys(json.loads(path.read_text(encoding="utf-8")))
    elif path.suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as stream:
            keys = set(next(csv.reader(stream), []))
    elif path.suffix == ".parquet":
        try:
            refuse_abstract_columns(path)
        except ReleaseError as error:
            raise SnapshotError(f"{entry.path}: {error}") from error
        return
    else:
        return
    hits = sorted(key for key in keys if key.lower().startswith(ABSTRACT_PREFIX))
    if hits:
        raise SnapshotError(f"{entry.path} has abstract-bearing fields {hits}; not packaged")


def discover(root: Path) -> list[Entry]:
    """Return the snapshot inputs under ``root`` in sorted order."""

    entries: list[Entry] = []
    for path in sorted((root / "site/data").glob("*.json")):
        if path.is_file():
            notes = ""
            if path.name == "monitoring.json":
                notes = MONITORING_NOTE
            elif path.name == "grants.json":
                notes = GRANTS_NOTE
            entries.append(Entry(path.relative_to(root).as_posix(), DATA_LICENSE, notes))
    entries.append(Entry("site/feed.xml", DATA_LICENSE))
    curation = root / "curation"
    for pattern in ("gold_*.csv", "splits_v1*.csv", "splits_v1*.json"):
        for path in sorted(curation.glob(pattern)):
            entries.append(Entry(path.relative_to(root).as_posix(), DATA_LICENSE))
    for name in ("queries.yml", "taxonomy.yml"):
        entries.append(Entry(f"config/{name}", CODE_LICENSE, "Query and taxonomy definitions."))
    unique: dict[str, Entry] = {}
    for entry in entries:
        unique.setdefault(entry.path, entry)
    return [unique[path] for path in sorted(unique)]


def _readme(version: str, source_commit: str | None, release_name: str | None = None) -> str:
    commit = source_commit or "not recorded"
    year = version[:4] if version[:4].isdigit() else "n.d."
    contents = [
        "  site/data/*.json   public payloads (CC BY 4.0, derived data)",
        "  site/feed.xml      Atom digest (CC BY 4.0)",
        "  curation/          gold sets and split files (CC BY 4.0)",
        "  config/            query and taxonomy definitions (MIT)",
    ]
    if release_name:
        contents.append(
            f"  release/{release_name}/  Parquet, query text, methods card, checksums (AT-10)"
        )
    return "\n".join(
        [
            "CA Plastics Research Atlas, release snapshot " + version,
            "=" * 60,
            "",
            "Citation:",
            f"  Coffin, S. ({year}). CA Plastics Research Atlas (snapshot {version}).",
            f"  Software and derived data. {SITE_URL} Source: {REPO_URL}",
            "  DOI: assigned by Zenodo on deposit; see the release page.",
            "",
            f"Source commit: {commit}",
            "",
            "Contents:",
            *contents,
            "  MANIFEST.json      path, bytes, sha256, and license for each file",
            "",
            "Licences:",
            f"  Code and configuration: {CODE_LICENSE}, {LICENSE_STATUS}.",
            f"  Derived data: {DATA_LICENSE}. Third-party rows keep their upstream terms;",
            "  see docs/REUSE.md in the repository.",
            "",
            "Not included: raw source downloads, interim tables, local credentials,",
            "per-work abstracts, and author detail files.",
            "",
            "Rebuild: see docs/REPRODUCIBILITY.md in the repository.",
            "",
        ]
    )


def _release_entries(release_dir: Path) -> list[Entry]:
    """Entries for a ``release/<date>/`` directory, packed under ``release/<date>/``."""

    if not (release_dir / "checksums.sha256").is_file():
        raise SnapshotError(f"{release_dir} has no checksums.sha256; write the release first")
    name = release_dir.name
    entries: list[Entry] = []
    for path in sorted(release_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(release_dir).as_posix()
        license_name = CODE_LICENSE if relative == "query.txt" else DATA_LICENSE
        entries.append(
            Entry(
                f"release/{name}/{relative}",
                license_name,
                "AT-10 release bundle file.",
                source=path,
            )
        )
    return entries


def build_snapshot(
    root: Path,
    output: Path,
    version: str,
    *,
    source_commit: str | None = None,
    release_dir: Path | None = None,
) -> dict[str, Any]:
    """Write the snapshot ZIP to ``output`` and return the manifest it contains.

    When ``release_dir`` is given, its files are packed under ``release/<name>/``.
    """

    if not VERSION_PATTERN.match(version):
        raise SnapshotError(f"invalid snapshot version {version!r}")
    entries = discover(root)
    if not any(entry.path.startswith("site/data/") for entry in entries):
        raise SnapshotError("no site/data payloads found; run the site build first")
    release_name = None
    if release_dir is not None:
        release_entries = _release_entries(release_dir)
        entries = sorted([*entries, *release_entries], key=lambda entry: entry.path)
        release_name = release_dir.name

    payloads: dict[str, bytes] = {}
    for entry in entries:
        if _is_excluded(entry.path):
            raise SnapshotError(f"{entry.path} is an excluded path")
        source = entry.source or (root / entry.path)
        _check_no_abstract(source, entry)
        payloads[entry.path] = source.read_bytes()

    readme = _readme(version, source_commit, release_name).encode("utf-8")
    files: list[dict[str, Any]] = []
    for entry in entries:
        data = payloads[entry.path]
        files.append(
            {
                "path": entry.path,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "license": entry.license,
                "notes": entry.notes,
            }
        )
    files.append(
        {
            "path": "README.txt",
            "bytes": len(readme),
            "sha256": hashlib.sha256(readme).hexdigest(),
            "license": f"{CODE_LICENSE} / {DATA_LICENSE} (see README.txt)",
            "notes": "Citation and licence summary.",
        }
    )
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_version": version,
        "source_commit": source_commit,
        "license_status": LICENSE_STATUS,
        "licenses": {"code_and_config": CODE_LICENSE, "derived_data": DATA_LICENSE},
        "excluded": ["data/raw/**", "data/interim/**", "data/logs/**", ".env*", "abstract fields"],
        "file_count": len(files),
        "files": files,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        members = [(entry.path, payloads[entry.path]) for entry in entries]
        members.append(("README.txt", readme))
        members.append(("MANIFEST.json", manifest_bytes))
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    output.write_bytes(buffer.getvalue())
    return manifest


def _source_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        default=datetime.now(UTC).strftime("%Y.%m.%d"),
        help="snapshot version, default today's UTC date as YYYY.MM.DD",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="ZIP path; default dist/atlas-snapshot-<version>.zip",
    )
    parser.add_argument(
        "--release-date",
        default=None,
        help="write release/<date>/ (YYYY-MM-DD) and include it in the ZIP",
    )
    parser.add_argument(
        "--write-site-release",
        action="store_true",
        help="write site/data/release.json from config/release.yml and exit",
    )
    args = parser.parse_args(argv)
    if args.write_site_release:
        try:
            payload = write_site_release(REPO)
        except (ReleaseError, OSError) as error:
            print(f"site release refused: {error}")
            return 1
        print(json.dumps(payload, sort_keys=True))
        return 0
    output = args.output or REPO / "dist" / f"atlas-snapshot-{args.version}.zip"
    release_dir = None
    try:
        if args.release_date:
            written = write_release(args.release_date, REPO / "release", root=REPO)
            release_dir = Path(written["directory"])
        manifest = build_snapshot(
            REPO,
            output,
            args.version,
            source_commit=_source_commit(REPO),
            release_dir=release_dir,
        )
    except (SnapshotError, ReleaseError) as error:
        print(f"snapshot refused: {error}")
        return 1
    total = sum(item["bytes"] for item in manifest["files"])
    print(
        json.dumps(
            {
                "output": str(output),
                "snapshot_version": args.version,
                "files": manifest["file_count"],
                "payload_bytes": total,
                "zip_bytes": output.stat().st_size,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
