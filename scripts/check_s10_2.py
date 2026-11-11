"""Offline acceptance check for the S10.2 governance package.

Checks that the governance files exist, that CITATION.cff parses with the
required CFF 1.2.0 keys, that every checklist evidence link resolves, that the
data dictionary names every public payload, that the checklist sign-off cells
are blank or complete (initials and date), and that a privacy scan finds no email-like or phone-like
strings in public site data. The scan reports file and field paths only; it
never prints matched values.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "docs/GOVERNANCE_CHECKLIST.md",
    "docs/PRIVACY_REVIEW.md",
    "docs/CORRECTIONS.md",
    "docs/DATA_DICTIONARY.md",
    "CITATION.cff",
)
REQUIRED_CFF_KEYS = (
    "cff-version",
    "message",
    "title",
    "authors",
    "url",
    "repository-code",
    "license",
)
CHECKLIST = "docs/GOVERNANCE_CHECKLIST.md"
DICTIONARY = "docs/DATA_DICTIONARY.md"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\w.])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w.])")
INTL_PHONE_RE = re.compile(r"\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{2,4}[\s.-]\d{2,4}")
PATTERNS = {"email": EMAIL_RE, "phone": PHONE_RE, "intl_phone": INTL_PHONE_RE}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def public_data_files(repo: Path = REPO) -> list[Path]:
    """Return the public payloads: site/data JSON and GeoJSON, plus site/feed.xml."""
    data = repo / "site" / "data"
    files = sorted(data.glob("*.json")) + sorted(data.glob("*.geojson"))
    files += sorted(data.glob("authors/*.json"))
    feed = repo / "site" / "feed.xml"
    if feed.exists():
        files.append(feed)
    return files


def _walk_json(value, path: str):
    """Yield (path, string) for every key and string value, without printing them."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield f"{path}.{key}" if path else str(key), str(key)
            yield from _walk_json(child, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child, f"{path}[]")
    elif isinstance(value, str):
        yield path, value


def scan_file(path: Path, repo: Path = REPO) -> list[tuple[str, str, str]]:
    """Return (relative file, field path or 'feed text', kind) for each match."""
    rel = path.relative_to(repo).as_posix()
    hits: list[tuple[str, str, str]] = []
    if path.suffix == ".xml":
        text = path.read_text(encoding="utf-8")
        for kind, rx in PATTERNS.items():
            hits.extend((rel, "feed text", kind) for _ in rx.finditer(text))
        return hits
    data = json.loads(path.read_text(encoding="utf-8"))
    for field, text in _walk_json(data, ""):
        for kind, rx in PATTERNS.items():
            # DOIs are public identifiers whose digit groups can look like phone numbers.
            if kind != "email" and field.rsplit(".", 1)[-1] in {"doi", "doi_url"}:
                continue
            if rx.search(text):
                hits.append((rel, field or "(root)", kind))
    return hits


def privacy_scan(repo: Path = REPO) -> tuple[dict[str, int], list[tuple[str, str, str]]]:
    """Return per-kind totals and the list of hits for all public payloads."""
    files = public_data_files(repo)
    hits: list[tuple[str, str, str]] = []
    for path in files:
        hits.extend(scan_file(path, repo))
    totals = {kind: sum(1 for _, _, k in hits if k == kind) for kind in PATTERNS}
    return {"files": len(files), **totals}, hits


def check_required_files(repo: Path = REPO) -> list[str]:
    return [f"missing file: {name}" for name in REQUIRED_FILES if not (repo / name).is_file()]


def check_citation(repo: Path = REPO) -> list[str]:
    path = repo / "CITATION.cff"
    if not path.is_file():
        return ["CITATION.cff missing"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"CITATION.cff does not parse as YAML: {type(exc).__name__}"]
    if not isinstance(data, dict):
        return ["CITATION.cff top level is not a mapping"]
    errors = [f"CITATION.cff missing key: {key}" for key in REQUIRED_CFF_KEYS if key not in data]
    if data.get("cff-version") != "1.2.0":
        errors.append("CITATION.cff cff-version is not 1.2.0")
    return errors


def checklist_rows(repo: Path = REPO) -> list[list[str]]:
    """Return the data rows of the checklist table, split into cells."""
    rows = []
    for line in (repo / CHECKLIST).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5 or set("".join(cells)) <= set("-: "):
            continue
        if cells[0].lower() == "item":
            continue
        rows.append(cells)
    return rows


def check_checklist(repo: Path = REPO) -> list[str]:
    errors = []
    rows = checklist_rows(repo)
    if not rows:
        return [f"{CHECKLIST} has no checklist rows"]
    for cells in rows:
        item, evidence, _status, signoff, date = cells
        links = LINK_RE.findall(evidence)
        if not links:
            errors.append(f"no evidence link in row: {item[:60]}")
        for target in LINK_RE.findall(" ".join(cells)):
            if target.startswith(("http://", "https://")):
                continue
            rel = target.split("#", 1)[0]
            if not (repo / CHECKLIST).parent.joinpath(rel).exists():
                errors.append(f"unresolved link {rel} in row: {item[:60]}")
        # Owner sign-off: initials and an ISO date together, or both blank.
        if bool(signoff) != bool(date):
            errors.append(f"sign-off needs both initials and date: {item[:60]}")
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            errors.append(f"sign-off date is not YYYY-MM-DD: {item[:60]}")
    return errors


def expected_dictionary_names(repo: Path = REPO) -> list[str]:
    names = [p.name for p in sorted((repo / "site" / "data").glob("*.json"))]
    names += [p.name for p in sorted((repo / "site" / "data").glob("*.geojson"))]
    if list((repo / "site" / "data" / "authors").glob("*.json")):
        names.append("authors/<author_id>.json")
    if (repo / "site" / "feed.xml").exists():
        names.append("feed.xml")
    return names


def check_dictionary(repo: Path = REPO) -> list[str]:
    path = repo / DICTIONARY
    if not path.is_file():
        return [f"{DICTIONARY} missing"]
    text = path.read_text(encoding="utf-8")
    return [
        f"data dictionary does not mention {name}"
        for name in expected_dictionary_names(repo)
        if name not in text
    ]


def main(argv: list[str] | None = None) -> int:
    errors: list[str] = []
    errors += check_required_files()
    if not any("missing file" in e for e in errors):
        errors += check_citation()
        errors += check_checklist()
        errors += check_dictionary()
    counts, hits = privacy_scan()
    for rel, field, kind in hits:
        errors.append(f"privacy: {kind}-like string in {rel} at field {field}")
    print(
        "S10.2 privacy scan: files={files} email={email} phone={phone} "
        "intl_phone={intl_phone}".format(**counts)
    )
    print(f"S10.2 checklist rows: {len(checklist_rows())}")
    for error in errors:
        print(f"FAIL {error}")
    if errors:
        print(f"S10.2 check FAILED ({len(errors)} issue(s))")
        return 1
    print("S10.2 check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
