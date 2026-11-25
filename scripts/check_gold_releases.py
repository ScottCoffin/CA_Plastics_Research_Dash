"""Refuse edits to released gold files (BQ-G6, docs/GOLD_POLICY.md).

Reads curation/gold_releases.json. Every file listed in a release must exist and match its
recorded sha256. Versions must be unique, and a later version must not reuse a file path of an
earlier one. An empty release list passes.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "curation" / "gold_releases.json"
SCHEMA = "gold-releases-v1"
REQUIRED_KEYS = ("version", "files", "release_date", "licence")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_releases(manifest: dict, root: Path = ROOT) -> list[str]:
    """Return a list of error messages; an empty list means the manifest passes."""
    errors: list[str] = []
    if manifest.get("schema") != SCHEMA:
        return [f"schema must be {SCHEMA!r}, found {manifest.get('schema')!r}"]
    releases = manifest.get("releases")
    if not isinstance(releases, list):
        return ["'releases' must be a list"]

    seen_versions: set[str] = set()
    seen_paths: dict[str, str] = {}  # file path -> version that first released it
    for release in releases:
        missing_keys = [key for key in REQUIRED_KEYS if key not in release]
        if missing_keys:
            errors.append(f"release {release.get('version', '?')!r} lacks keys: {missing_keys}")
            continue
        version = release["version"]
        if version in seen_versions:
            errors.append(f"duplicate release version {version!r}")
        seen_versions.add(version)

        files = release["files"]
        if not isinstance(files, dict) or not files:
            errors.append(f"release {version!r} must list at least one file")
            continue
        for rel_path, expected in files.items():
            if rel_path in seen_paths and seen_paths[rel_path] != version:
                errors.append(
                    f"{rel_path}: released in {seen_paths[rel_path]!r} and reused in {version!r}"
                )
            seen_paths.setdefault(rel_path, version)
            path = root / rel_path
            if not path.is_file():
                errors.append(f"{rel_path}: released in {version!r} but missing")
                continue
            actual = sha256_file(path)
            if actual != expected:
                errors.append(
                    f"{rel_path}: released in {version!r} but changed "
                    f"(sha256 {actual} != recorded {expected}); use a new version"
                )
    return errors


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not manifest.get("releases"):
        print("no gold release yet; nothing to protect")
        return 0
    errors = check_releases(manifest)
    for error in errors:
        print(f"FAIL: {error}")
    if errors:
        return 1
    print(f"ok: {len(manifest['releases'])} gold release(s) verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
