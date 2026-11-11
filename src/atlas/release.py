"""Release bundle, methods card, and site release metadata (AT-10).

``write_release`` writes ``release/<date>/`` with copies of the bundle Parquet files,
the active query text, a methods card (JSON and Markdown), and ``checksums.sha256``.
``site_release_payload`` turns ``config/release.yml`` into the ``site/data/release.json``
payload that the About page reads.

Every number in the methods card is either a value with its source or ``null`` with a
reason. Nothing is estimated or invented. Offline only: git is read locally.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from atlas.query import load_query_config, openalex_filter, render_query

REPO = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "at10"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$")
QUERY_CONFIG = Path("config/queries.yml")
AUDIT_DOC = Path("docs/QUERY_AUDIT.md")
RAW_WORKS = Path("data/interim/works_raw.parquet")
NORMALIZED_WORKS = Path("data/processed/normalized/works.parquet")
INDEX_JSON = Path("site/data/index.json")
ANALYTICS_MANIFEST = Path("data/processed/analytics/manifest.json")
BUNDLE_MANIFEST = Path("site/data/bundle/manifest.json")
BUNDLE_PARQUET = Path("site/data/bundle/parquet")
RELEASE_YML = Path("config/release.yml")
SITE_RELEASE_JSON = Path("site/data/release.json")
CHECKSUMS_NAME = "checksums.sha256"
QUERY_NAME = "query.txt"
METHODS_JSON_NAME = "methods_card.json"
METHODS_MD_NAME = "methods_card.md"
RELEASE_KEYS = ("version", "date", "doi", "concept_doi")
REQUIRED_CARD_KEYS = (
    "release_date",
    "generated_at",
    "source_commit",
    "worktree",
    "query",
    "audit_precision",
    "exclusions",
    "flow",
)
FLOW_KEYS = (
    "raw_records",
    "after_near_duplicate_collapse",
    "california_authorship",
    "published_after_curation",
    "plastic_related_published",
    "analysed_excluding_retracted",
)


class ReleaseError(RuntimeError):
    """Raised when a release cannot be written without breaking a rule."""


def _check_date(date: str) -> None:
    if not isinstance(date, str) or not DATE_PATTERN.match(date):
        raise ReleaseError(f"release date must be YYYY-MM-DD, got {date!r}")


def refuse_abstract_columns(path: Path) -> None:
    """Raise ``ReleaseError`` if a Parquet file has any column whose name contains 'abstract'."""

    names = pq.read_schema(path).names
    hits = sorted(name for name in names if "abstract" in name.lower())
    if hits:
        raise ReleaseError(f"{path.name} has abstract columns {hits}; not released")


def _field(value: Any, source: str, reason: str | None = None) -> dict[str, Any]:
    """Return a card field; a null value must carry a reason."""

    if value is None and not reason:
        raise ValueError(f"null value from {source} needs a reason")
    return {"value": value, "source": source, "reason": None if value is not None else reason}


def _git(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def _source_commit(root: Path) -> str | None:
    out = _git(root, "rev-parse", "HEAD")
    return out.strip() if out and out.strip() else None


def _rows(root: Path, rel: Path) -> tuple[int | None, str | None]:
    path = root / rel
    if not path.is_file():
        return None, f"{rel.as_posix()} not present in this checkout (gitignored build output)"
    return pq.ParquetFile(path).metadata.num_rows, None


def _true_count(root: Path, rel: Path, column: str) -> tuple[int | None, str | None]:
    path = root / rel
    if not path.is_file():
        return None, f"{rel.as_posix()} not present in this checkout (gitignored build output)"
    if column not in pq.read_schema(path).names:
        return None, f"column {column} missing from {rel.as_posix()}"
    values = pq.read_table(path, columns=[column]).column(column).to_pylist()
    return sum(1 for value in values if value is True), None


def _json_file(root: Path, rel: Path) -> dict[str, Any] | None:
    path = root / rel
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _index_works(root: Path) -> tuple[list[dict[str, Any]] | None, str | None]:
    data = _json_file(root, INDEX_JSON)
    if data is None:
        return None, f"{INDEX_JSON.as_posix()} not present in this checkout"
    works = data.get("works")
    if not isinstance(works, list):
        return None, f"{INDEX_JSON.as_posix()} has no works list"
    return works, None


def _exclusions(root: Path) -> tuple[dict[str, Any] | None, str, str | None]:
    """Exclusions from the analytics manifest when present, else the bundle manifest."""

    for rel in (ANALYTICS_MANIFEST, BUNDLE_MANIFEST):
        data = _json_file(root, rel)
        if data is not None and isinstance(data.get("exclusions"), dict):
            return data["exclusions"], rel.as_posix(), None
    return (
        None,
        f"{ANALYTICS_MANIFEST.as_posix()} or {BUNDLE_MANIFEST.as_posix()}",
        f"neither {ANALYTICS_MANIFEST.as_posix()} nor a bundle manifest exclusions block "
        "is present (run scripts/build_analytics.py)",
    )


def _audit_precision(root: Path, version: str) -> tuple[float | None, str, str | None]:
    """Estimated overall precision for the active query, parsed from docs/QUERY_AUDIT.md."""

    source = f"{AUDIT_DOC.as_posix()}: 'Estimated overall precision' row"
    path = root / AUDIT_DOC
    if not path.is_file():
        return None, source, f"{AUDIT_DOC.as_posix()} not present in this checkout"
    label = version.removeprefix("plastic-")
    column: int | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not line.lstrip().startswith("|"):
            continue
        if cells and cells[0] == "Measure":
            column = cells.index(label) if label in cells else None
            continue
        if column is not None and cells and cells[0] == "Estimated overall precision":
            match = re.search(r"(\d+(?:\.\d+)?)\s*%", cells[column] if column < len(cells) else "")
            if match:
                return float(match.group(1)), source, None
    return (
        None,
        source,
        f"no 'Estimated overall precision' value for {label} in {AUDIT_DOC.as_posix()}",
    )


def _flow(root: Path) -> dict[str, dict[str, Any]]:
    raw, raw_reason = _rows(root, RAW_WORKS)
    dedup, dedup_reason = _rows(root, NORMALIZED_WORKS)
    ca, ca_reason = _true_count(root, NORMALIZED_WORKS, "ca_any_author")
    works, works_reason = _index_works(root)
    published = len(works) if works is not None else None
    plastic = (
        sum(1 for work in works if work.get("plastic_related") is True)
        if works is not None
        else None
    )
    analytics = _json_file(root, ANALYTICS_MANIFEST)
    analysed = analytics.get("n_works") if analytics else None
    analysed_reason = (
        None
        if isinstance(analysed, int)
        else f"{ANALYTICS_MANIFEST.as_posix()} not present or has no n_works "
        "(run scripts/build_analytics.py)"
    )
    return {
        "raw_records": _field(raw, RAW_WORKS.as_posix() + " rows", raw_reason),
        "after_near_duplicate_collapse": _field(
            dedup, NORMALIZED_WORKS.as_posix() + " rows", dedup_reason
        ),
        "california_authorship": _field(
            ca, NORMALIZED_WORKS.as_posix() + " ca_any_author true", ca_reason
        ),
        "published_after_curation": _field(
            published, INDEX_JSON.as_posix() + " works", works_reason
        ),
        "plastic_related_published": _field(
            plastic, INDEX_JSON.as_posix() + " works with plastic_related true", works_reason
        ),
        "analysed_excluding_retracted": _field(
            analysed if isinstance(analysed, int) else None,
            ANALYTICS_MANIFEST.as_posix() + " n_works",
            analysed_reason,
        ),
    }


def _query_text(config: dict[str, Any]) -> str:
    rendered = render_query(config)
    return "\n".join(
        [
            f"Query version: {config['version']}",
            f"Status: {config.get('status', 'not recorded')}",
            f"Source: {QUERY_CONFIG.as_posix()}",
            "",
            "Rendered query (title and abstract, exclusions applied):",
            rendered,
            "",
            "OpenAlex filter:",
            openalex_filter(config),
            "",
        ]
    )


def methods_card(
    root: Path = REPO,
    *,
    release_date: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build the methods card for ``release_date`` from the inputs under ``root``."""

    _check_date(release_date)
    config = load_query_config(root / QUERY_CONFIG)
    commit = _source_commit(root)
    status = _git(root, "status", "--porcelain")
    worktree_reason = None if status is not None else "git status unavailable"
    exclusions, exclusions_source, exclusions_reason = _exclusions(root)
    precision, precision_source, precision_reason = _audit_precision(root, config["version"])
    return {
        "schema_version": SCHEMA_VERSION,
        "release_date": release_date,
        "generated_at": generated_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_commit": _field(
            commit,
            "git rev-parse HEAD",
            "not a git checkout or git unavailable",
        ),
        "worktree": _field(
            None if status is None else ("dirty" if status.strip() else "clean"),
            "git status --porcelain",
            worktree_reason,
        ),
        "query": {
            "version": config["version"],
            "status": config.get("status", "not recorded"),
            "source": QUERY_CONFIG.as_posix(),
            "rendered_sha256": hashlib.sha256(render_query(config).encode("utf-8")).hexdigest(),
        },
        "audit_precision": {
            **_field(
                precision,
                precision_source,
                precision_reason,
            ),
            "unit": "percent",
        },
        "exclusions": _field(exclusions, exclusions_source, exclusions_reason),
        "flow": _flow(root),
    }


def _fmt(field: dict[str, Any]) -> str:
    return "n/a" if field["value"] is None else f"{field['value']:,}"


def render_methods_markdown(card: dict[str, Any]) -> str:
    """Render the methods card as a short Markdown page: one table and a flow list."""

    flow = card["flow"]
    query = card["query"]
    precision = card["audit_precision"]
    exclusions = card["exclusions"]
    commit = card["source_commit"]
    missing: list[str] = []

    def note(label: str, field: dict[str, Any]) -> None:
        if field["value"] is None:
            missing.append(f"- {label}: {field['reason']}")

    precision_text = (
        "not reported"
        if precision["value"] is None
        else f"{precision['value']:.1f}% (estimated overall, {query['version']})"
    )
    if exclusions["value"] is None:
        exclusion_text = "n/a"
    else:
        exclusion_text = "; ".join(
            f"{key.replace('_', ' ')} {value:,}" for key, value in exclusions["value"].items()
        )
    lines = [
        f"# Methods card: CA Plastics Research Atlas, release {card['release_date']}",
        "",
        f"Generated {card['generated_at']}.",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Query version | {query['version']} ({query['status']}; {query['source']}) |",
        f"| Estimated precision (AT-1 audit) | {precision_text} |",
        f"| Exclusions | {exclusion_text} |",
        f"| Source commit | {commit['value'] or 'n/a'} "
        f"(worktree {card['worktree']['value'] or 'n/a'}) |",
        "",
        "PRISMA-style flow (counts):",
        "",
        f"1. Raw records retrieved: {_fmt(flow['raw_records'])}",
        f"2. After near-duplicate collapse: {_fmt(flow['after_near_duplicate_collapse'])}",
        f"3. California authorship (ca_any_author): {_fmt(flow['california_authorship'])}",
        f"4. Published after curation: {_fmt(flow['published_after_curation'])}",
        f"5. Plastic-related and published: {_fmt(flow['plastic_related_published'])}",
        f"6. Analysed (excluding retracted): {_fmt(flow['analysed_excluding_retracted'])}",
        "",
    ]
    note("Source commit", commit)
    note("Precision", precision)
    note("Exclusions", exclusions)
    for key in FLOW_KEYS:
        note(f"Flow step {key}", flow[key])
    if missing:
        lines += ["Values not available in this checkout:", "", *missing, ""]
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_release(
    date: str,
    out_root: str | Path = "release",
    *,
    root: Path = REPO,
) -> dict[str, Any]:
    """Write ``<out_root>/<date>/`` and return a summary.

    A relative ``out_root`` is resolved against ``root``. Every Parquet file is checked for
    abstract columns before anything is written.
    """

    _check_date(date)
    out = Path(out_root)
    out_dir = (out if out.is_absolute() else root / out) / date
    sources = sorted((root / BUNDLE_PARQUET).glob("*.parquet"))
    if not sources:
        raise ReleaseError(f"no Parquet files in {BUNDLE_PARQUET.as_posix()}; run the bundle build")
    for source in sources:
        refuse_abstract_columns(source)
    config = load_query_config(root / QUERY_CONFIG)
    card = methods_card(root, release_date=date)

    parquet_dir = out_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in sources:
        target = parquet_dir / source.name
        shutil.copyfile(source, target)
        written.append(target)
    for name, text in (
        (QUERY_NAME, _query_text(config)),
        (METHODS_JSON_NAME, json.dumps(card, indent=2, sort_keys=True) + "\n"),
        (METHODS_MD_NAME, render_methods_markdown(card)),
    ):
        target = out_dir / name
        target.write_text(text, encoding="utf-8", newline="\n")
        written.append(target)

    lines = [f"{_sha256(path)}  {path.relative_to(out_dir).as_posix()}" for path in written]
    checksums = out_dir / CHECKSUMS_NAME
    checksums.write_text("\n".join(sorted(lines)) + "\n", encoding="utf-8", newline="\n")
    return {
        "directory": str(out_dir),
        "files": sorted(path.relative_to(out_dir).as_posix() for path in [*written, checksums]),
        "card": card,
    }


def verify_checksums(release_dir: Path) -> list[str]:
    """Return a list of problems with ``checksums.sha256`` under ``release_dir``."""

    checksums = release_dir / CHECKSUMS_NAME
    if not checksums.is_file():
        return [f"{CHECKSUMS_NAME} missing"]
    errors: list[str] = []
    listed: set[str] = set()
    for line in checksums.read_text(encoding="utf-8").split("\n"):
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (\S.*)", line)
        if not match:
            errors.append(f"malformed checksum line {line!r}")
            continue
        digest, rel = match.groups()
        listed.add(rel)
        target = release_dir / rel
        if not target.is_file():
            errors.append(f"listed file missing: {rel}")
        elif _sha256(target) != digest:
            errors.append(f"checksum mismatch: {rel}")
    on_disk = {
        path.relative_to(release_dir).as_posix()
        for path in release_dir.rglob("*")
        if path.is_file() and path.name != CHECKSUMS_NAME
    }
    errors += [f"file not in checksums: {rel}" for rel in sorted(on_disk - listed)]
    return errors


def load_release_yml(root: Path = REPO) -> dict[str, Any]:
    data = yaml.safe_load((root / RELEASE_YML).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ReleaseError(f"{RELEASE_YML.as_posix()} must be a mapping")
    missing = [key for key in RELEASE_KEYS if key not in data]
    if missing:
        raise ReleaseError(f"{RELEASE_YML.as_posix()} is missing {missing}")
    date = str(data["date"])
    _check_date(date)
    doi, concept = str(data["doi"]), str(data["concept_doi"])
    for label, value in (("doi", doi), ("concept_doi", concept)):
        if not DOI_PATTERN.match(value):
            raise ReleaseError(f"{label} {value!r} is not a DOI")
    return {"version": str(data["version"]), "date": date, "doi": doi, "concept_doi": concept}


def site_release_payload(root: Path = REPO) -> dict[str, Any]:
    meta = load_release_yml(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "version": meta["version"],
        "date": meta["date"],
        "doi": meta["doi"],
        "doi_url": f"https://doi.org/{meta['doi']}",
        "concept_doi": meta["concept_doi"],
        "concept_url": f"https://doi.org/{meta['concept_doi']}",
    }


def write_site_release(root: Path = REPO) -> dict[str, Any]:
    """Write ``site/data/release.json`` from ``config/release.yml`` and return the payload."""

    payload = site_release_payload(root)
    target = root / SITE_RELEASE_JSON
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return payload
