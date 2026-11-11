"""Normalize OpenAlex work records into the processed C3 tables.

The normalizer deliberately keeps the reviewed institution registry as an
input.  Its generated institution table is written below a separate output
directory so a works refresh cannot overwrite owner-reviewed registry state.
"""

from __future__ import annotations

import csv
import json
import re
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.build.curation import load_suppressions
from atlas.ingest.abstract_qc import misattached_abstract_ids
from atlas.ingest.state_agencies import (
    DEFAULT_PATH as STATE_AGENCIES_PATH,
)
from atlas.ingest.state_agencies import (
    apply_state_agencies,
    load_state_agencies,
    match_state_agencies,
    registry_row,
)

WORKS_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("doi", pa.string()),
        ("title", pa.string()),
        ("abstract", pa.string()),
        ("year", pa.int64()),
        ("pub_date", pa.string()),
        ("type", pa.string()),
        ("journal", pa.string()),
        ("is_oa", pa.bool_()),
        ("oa_status", pa.string()),
        ("oa_url", pa.string()),
        ("license", pa.string()),
        ("openalex_topics", pa.list_(pa.string())),
        ("primary_topic", pa.string()),
        ("cited_by_count", pa.int64()),
        ("is_retracted", pa.bool_()),
        ("first_seen", pa.string()),
        ("last_updated", pa.string()),
        ("ca_led", pa.bool_()),
        ("ca_any_author", pa.bool_()),
        ("duplicate_work_ids", pa.list_(pa.string())),
    ]
)

AUTHORSHIPS_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("author_id", pa.string()),
        ("author_name", pa.string()),
        ("position", pa.string()),
        ("is_corresponding", pa.bool_()),
        ("institution_ids", pa.list_(pa.string())),
        ("raw_affiliation", pa.string()),
        ("ca_basis", pa.string()),
    ]
)

AUTHORS_SCHEMA = pa.schema(
    [
        ("author_id", pa.string()),
        ("name", pa.string()),
        ("orcid", pa.string()),
        ("ca_works_count", pa.int64()),
        ("first_year", pa.int64()),
        ("last_year", pa.int64()),
        ("domain_tags", pa.list_(pa.string())),
        ("override_flags", pa.list_(pa.string())),
    ]
)

INSTITUTIONS_SCHEMA = pa.schema(
    [
        ("inst_id", pa.string()),
        ("ror", pa.string()),
        ("name", pa.string()),
        ("city", pa.string()),
        ("region", pa.string()),
        ("lat", pa.float64()),
        ("lon", pa.float64()),
        ("ror_types", pa.list_(pa.string())),
        ("atlas_type", pa.string()),
        ("parent_system", pa.string()),
        ("ca_flag", pa.bool_()),
    ]
)


@dataclass(frozen=True)
class NormalizationResult:
    """Paths and QC metrics produced by one deterministic normalization run."""

    output_dir: Path
    qc_path: Path
    metrics: dict[str, int]


_TYPE_RANK = {
    "article": 0,
    "review": 1,
    "book-chapter": 2,
    "book": 3,
    "conference-paper": 4,
    "proceedings-article": 4,
    "preprint": 6,
    "posted-content": 6,
    "dataset": 7,
}
_OTHER_TYPE_RANK = 5
NEAR_DUPLICATE_MIN_KEY_LENGTH = 20
NEAR_DUPLICATE_YEAR_WINDOW = 1


@dataclass(frozen=True)
class _CollapseResult:
    kept: list[dict[str, Any]]
    duplicate_rows: list[dict[str, Any]]
    skipped_distinct_doi: int


_TITLE_ARTIFACT = re.compile(r"^\s*Title\s*:?\s*(?=[A-Z])")


def title_key(title: object) -> str:
    """Lowercase the title, drop every non [a-z0-9] character, keep 60 characters.

    A leading ``Title``/``Title:`` form-field artifact (seen on SSRN preprints) is
    ignored when a capital letter follows, so the preprint matches its article.
    """
    text = _TITLE_ARTIFACT.sub("", _string(title))
    return re.sub(r"[^a-z0-9]", "", text.lower())[:60]


def _type_rank(value: object) -> int:
    return _TYPE_RANK.get(_string(value).lower(), _OTHER_TYPE_RANK)


def _preference(work: Mapping[str, Any]) -> tuple[Any, ...]:
    """Sort key: lower tuples are preferred as the kept representative."""
    doi = _string(work.get("doi"))
    pub_date = _string(work.get("pub_date"))
    return (
        _type_rank(work.get("type")),
        not doi,
        not pub_date,
        pub_date,
        _string(work.get("work_id")),
    )


def _distinct_article_dois(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    """True when both works are articles carrying different non-empty DOIs."""
    doi_a = _string(first.get("doi")).lower()
    doi_b = _string(second.get("doi")).lower()
    return (
        bool(doi_a and doi_b)
        and doi_a != doi_b
        and _string(first.get("type")).lower() == "article"
        and _string(second.get("type")).lower() == "article"
    )


def _year_clusters(members: list[Mapping[str, Any]]) -> list[list[Mapping[str, Any]]]:
    """Chain works sorted by year; a gap above the window starts a new cluster."""
    clusters: list[list[Mapping[str, Any]]] = []
    for work in members:
        if clusters and work["year"] - clusters[-1][-1]["year"] <= NEAR_DUPLICATE_YEAR_WINDOW:
            clusters[-1].append(work)
        else:
            clusters.append([work])
    return clusters


def _collapse_near_duplicates(works: Sequence[Mapping[str, Any]]) -> _CollapseResult:
    """Collapse same-title, same-window works into one preferred representative."""
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for work in works:
        key = title_key(work.get("title"))
        year = work.get("year")
        if len(key) < NEAR_DUPLICATE_MIN_KEY_LENGTH or not isinstance(year, int):
            continue
        groups[key].append(work)

    duplicate_of: dict[str, str] = {}
    duplicate_rows: list[dict[str, Any]] = []
    skipped = 0
    for key in sorted(groups):
        members = sorted(groups[key], key=lambda work: (work["year"], _string(work["work_id"])))
        for cluster in _year_clusters(members):
            if len(cluster) < 2:
                continue
            keepers: list[Mapping[str, Any]] = []
            for work in sorted(cluster, key=_preference):
                target = None
                blocked = False
                for keeper in keepers:
                    if _distinct_article_dois(keeper, work):
                        blocked = True
                        continue
                    target = keeper
                    break
                if target is None:
                    skipped += int(blocked)
                    keepers.append(work)
                    continue
                duplicate_of[_string(work["work_id"])] = _string(target["work_id"])
                duplicate_rows.append(
                    {
                        "work_id": _string(work["work_id"]),
                        "duplicate_of": _string(target["work_id"]),
                        "title_key": key,
                        "reason": "same_title_key_within_year_window",
                    }
                )

    collapsed_by_keeper: dict[str, list[str]] = defaultdict(list)
    for duplicate_id, keeper_id in duplicate_of.items():
        collapsed_by_keeper[keeper_id].append(duplicate_id)
    kept = [
        {
            **work,
            "duplicate_work_ids": sorted(collapsed_by_keeper.get(_string(work["work_id"]), [])),
        }
        for work in works
        if _string(work["work_id"]) not in duplicate_of
    ]
    duplicate_rows.sort(key=lambda row: row["work_id"])
    return _CollapseResult(kept, duplicate_rows, skipped)


def collapse_near_duplicates(
    works: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (kept works, duplicate map rows) for near-duplicate works.

    Works group by ``title_key`` (titles shorter than 20 characters are skipped)
    and by publication years chained within one year. The preferred work keeps
    its row and lists the collapsed ids in ``duplicate_work_ids``. Two articles
    with different non-empty DOIs are never collapsed.
    """
    result = _collapse_near_duplicates(works)
    return result.kept, result.duplicate_rows


def _repoint_authorships(
    rows: list[dict[str, Any]], keeper_of: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Move authorships of collapsed works to their kept work and dedupe by author."""
    own = [row for row in rows if row["work_id"] not in keeper_of]
    seen = {(row["work_id"], row["author_id"]) for row in own if row["author_id"]}
    moved: list[dict[str, Any]] = []
    for row in rows:
        if row["work_id"] not in keeper_of:
            continue
        repointed = {**row, "work_id": keeper_of[row["work_id"]]}
        if repointed["author_id"]:
            key = (repointed["work_id"], repointed["author_id"])
            if key in seen:
                continue
            seen.add(key)
        moved.append(repointed)
    return own + moved


def compact_id(value: object) -> str:
    """Return an OpenAlex or ROR identifier without its URL prefix."""

    text = str(value or "").rstrip("/")
    return text.rsplit("/", 1)[-1] if text else ""


def _string(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _number(value: object) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _compact_ids(values: object) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return list(dict.fromkeys(compact_id(value) for value in values if compact_id(value)))


def _abstract_from_inverted_index(value: object) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        return ""
    words: dict[int, str] = {}
    for token, positions in value.items():
        if not isinstance(positions, Sequence) or isinstance(positions, (str, bytes)):
            continue
        for position in positions:
            try:
                words[int(position)] = str(token)
            except (TypeError, ValueError):
                continue
    return " ".join(words[index] for index in sorted(words))


def _topic_ids(work: Mapping[str, Any]) -> list[str]:
    topics = work.get("topics")
    if not isinstance(topics, Sequence) or isinstance(topics, (str, bytes)):
        return []
    return list(
        dict.fromkeys(
            compact_id(topic.get("id"))
            for topic in topics
            if isinstance(topic, Mapping) and compact_id(topic.get("id"))
        )
    )


def _source(work: Mapping[str, Any]) -> Mapping[str, Any]:
    location = work.get("primary_location")
    source = location.get("source") if isinstance(location, Mapping) else None
    return source if isinstance(source, Mapping) else {}


def _location(work: Mapping[str, Any]) -> Mapping[str, Any]:
    location = work.get("best_oa_location") or work.get("primary_location")
    return location if isinstance(location, Mapping) else {}


def _author_position(index: int, total: int, value: object) -> str:
    position = _string(value).casefold()
    if position in {"first", "middle", "last"}:
        return position
    if index == 0:
        return "first"
    if index == total - 1:
        return "last"
    return "middle"


def _looks_california(value: str) -> bool:
    text = value.casefold()
    return "california" in text or bool(re.search(r"(?<![a-z])ca(?![a-z])", text))


CA_BASIS_REGISTRY = "registry"
CA_BASIS_RAW = "raw_affiliation"
CA_BASIS_CARRY = "author_carry_forward"
CARRY_FORWARD_YEAR_WINDOW = 2

_CA_AFFILIATION_PATTERNS = (
    re.compile(
        r"(?<!Baja )\bCalifornia\b(?!,?\s*(?:PA\b|Pennsylvania|Missouri|MO\b|Maryland|MD\b))",
        re.IGNORECASE,
    ),
    re.compile(r",\s*CA\.?,?\s+9\d{4}\b"),
    re.compile(r",\s*CA,?\s+(?:USA|U\.S\.A\.|United States)\b", re.IGNORECASE),
    re.compile(
        r"\bUC\s+(?:Berkeley|Davis|Irvine|Los Angeles|Merced|Riverside|San Diego"
        r"|San Francisco|Santa Barbara|Santa Cruz)\b"
    ),
    re.compile(r"\bScripps Institution of Oceanography\b", re.IGNORECASE),
    re.compile(r"\bCaltech\b"),
    re.compile(r"\bMoss Landing Marine Laborator", re.IGNORECASE),
    re.compile(r"\bStanford University\b", re.IGNORECASE),
)
_AFFILIATION_PLACEHOLDER = re.compile(
    r"affiliation\s+not\s+provided|^\s*(?:independent|unaffiliated|none|n/?a|unknown)\b",
    re.IGNORECASE,
)


_NOT_CALIFORNIA_STATE = re.compile(
    r"California\s+(?:University\s+of\s+Pennsylvania|Univ\.?\s+of\s+Pa\.?)", re.IGNORECASE
)


def matches_california_affiliation(value: object) -> bool:
    """True when a raw affiliation string carries a strict California signal.

    Only affiliation strings are tested (never titles), so "California sea lion"
    cannot match. ``Baja California`` and ``California, PA`` style places are excluded.
    """
    text = _NOT_CALIFORNIA_STATE.sub(" ", _string(value))
    return bool(text.strip()) and any(pattern.search(text) for pattern in _CA_AFFILIATION_PATTERNS)


def is_placeholder_affiliation(value: object) -> bool:
    """True for an empty or placeholder affiliation ("Independent - ... not provided")."""
    text = _string(value).strip(" |,.;")
    return not text or bool(_AFFILIATION_PLACEHOLDER.search(text))


def _read_registry(path: str | Path) -> dict[str, dict[str, Any]]:
    table = pq.read_table(path)
    result: dict[str, dict[str, Any]] = {}
    for row in table.to_pylist():
        inst_id = compact_id(row.get("openalex_id"))
        if not inst_id:
            continue
        region = _string(row.get("region"))
        country = _string(row.get("country_code"))
        result[inst_id] = {
            "inst_id": inst_id,
            "ror": _string(row.get("ror_id")),
            "name": _string(row.get("display_name")),
            "city": _string(row.get("city")),
            "region": region,
            "lat": _float(row.get("latitude")),
            "lon": _float(row.get("longitude")),
            "ror_types": [str(value) for value in (row.get("ror_types") or [])],
            "atlas_type": _string(row.get("atlas_type")) or "other",
            "parent_system": (
                compact_id((row.get("lineage") or [])[0])
                if len(row.get("lineage") or []) > 1
                else ""
            ),
            "ca_flag": region.casefold() == "california" and country.casefold() in {"", "us"},
        }
    return result


def _load_overrides(path: str | Path) -> dict[str, list[str]]:
    overrides: dict[str, list[str]] = defaultdict(list)
    if not Path(path).exists():
        return overrides
    with Path(path).open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            author_id = compact_id(row.get("author_id"))
            action = _string(row.get("action"))
            if author_id and action:
                target = compact_id(row.get("target_author_id"))
                overrides[author_id].append(f"{action}:{target}" if target else action)
    return overrides


def _raw_institution_row(
    institution: Mapping[str, Any], registry_row: Mapping[str, Any] | None
) -> dict[str, Any] | None:
    inst_id = compact_id(institution.get("id"))
    if not inst_id:
        return None
    if registry_row:
        return dict(registry_row)
    geo = institution.get("geo")
    geo = geo if isinstance(geo, Mapping) else {}
    types = institution.get("ror_types") or institution.get("types") or institution.get("type")
    if isinstance(types, str):
        types = [types] if types else []
    return {
        "inst_id": inst_id,
        "ror": compact_id(institution.get("ror")),
        "name": _string(institution.get("display_name")),
        "city": _string(geo.get("city") or institution.get("city")),
        "region": _string(geo.get("region") or institution.get("region")),
        "lat": _float(geo.get("latitude") or institution.get("latitude")),
        "lon": _float(geo.get("longitude") or institution.get("longitude")),
        "ror_types": [str(value) for value in types if value] if isinstance(types, list) else [],
        "atlas_type": "other",
        "parent_system": (
            compact_id((institution.get("lineage") or [])[0])
            if len(institution.get("lineage") or []) > 1
            else ""
        ),
        "ca_flag": False,
    }


def _atomic_write_table(path: Path, rows: Iterable[Mapping[str, Any]], schema: pa.Schema) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(list(rows), schema=schema)
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".parquet", prefix=f".{path.stem}-", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        pq.write_table(table, temporary, compression="zstd")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _qc_markdown(metrics: Mapping[str, int], *, generated_at: str, source: str) -> str:
    rows = [
        ("Source raw work rows", metrics["source_work_rows"]),
        ("Normalized unique works", metrics["works"]),
        ("Authorship rows", metrics["authorships"]),
        ("Authors with non-null IDs", metrics["authors"]),
        ("Linked/raw institution rows", metrics["institutions"]),
        ("Authorships with missing raw affiliation", metrics["missing_affiliations"]),
        ("Authorships with null author IDs", metrics["null_author_ids"]),
        ("Unresolved institution links", metrics["unresolved_institution_links"]),
        (
            "Works with CA-like affiliation but no resolved CA institution",
            metrics["ca_affiliation_without_resolved_institution"],
        ),
        ("Works with ca_led=true", metrics["ca_led_works"]),
        ("Works with ca_any_author=true", metrics["ca_any_author_works"]),
        ("Near-duplicate works collapsed into a kept work", metrics["near_duplicates_collapsed"]),
        (
            "Mis-attached OpenAlex abstracts blanked",
            metrics.get("misattached_abstracts_blanked", 0),
        ),
        ("Near-duplicate groups", metrics["near_duplicate_groups"]),
        (
            "Same-title article pairs kept apart (distinct DOIs)",
            metrics["skipped_same_title_distinct_doi"],
        ),
        ("Authorships CA by registry institution", metrics["authorships_ca_registry"]),
        ("Authorships CA by raw affiliation string", metrics["authorships_ca_raw_affiliation"]),
        (
            "Authorships CA by author carry-forward (no affiliation, +/-2 years)",
            metrics["authorships_ca_carry_forward"],
        ),
    ]
    lines = [
        "# OpenAlex normalization QC",
        "",
        f"Generated at (UTC): `{generated_at}`",
        f"Source: `{source}`",
        "",
        "The normalizer treats the reviewed California institution registry as "
        "the authoritative resolved-CA set. `ca_led` is true only when the "
        "first authorship has a California basis; `ca_any_author` "
        "is true when any authorship does. An authorship's `ca_basis` is "
        "`registry` (resolved CA institution), `raw_affiliation` (strict California "
        "pattern in the raw affiliation string) or `author_carry_forward` (no "
        "affiliation at all, same author has a CA authorship within 2 years). "
        "A CA-like unresolved affiliation is "
        "reported when its affiliation contains `California` or a standalone "
        "`CA` token but no resolved CA institution is linked for that work.",
        "",
        "| Check | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    lines.extend(
        [
            "",
            "This report is generated by `make qc`; when no ignored live raw table "
            "is present, the command uses the committed S2.2 fixture as a safe "
            "development fallback.",
            "",
        ]
    )
    return "\n".join(lines)


def _apply_carry_forward(
    authorships: list[dict[str, Any]],
    works: Sequence[Mapping[str, Any]],
    author_state: dict[str, dict[str, Any]],
) -> None:
    """Mark empty-affiliation authorships ``author_carry_forward`` (in place).

    An authorship with no institutions and no real raw affiliation inherits California
    from the same author when that author has a registry/raw CA authorship on a work
    published within ``CARRY_FORWARD_YEAR_WINDOW`` years.
    """
    year_of = {row["work_id"]: row["year"] for row in works}
    ca_years: dict[str, list[int]] = defaultdict(list)
    for row in authorships:
        year = year_of.get(row["work_id"])
        if row["author_id"] and row["ca_basis"] and isinstance(year, int):
            ca_years[row["author_id"]].append(year)
    for row in authorships:
        year = year_of.get(row["work_id"])
        if (
            row["ca_basis"]
            or not row["author_id"]
            or not isinstance(year, int)
            or row["institution_ids"]
            or not is_placeholder_affiliation(row["raw_affiliation"])
        ):
            continue
        if any(
            abs(year - other) <= CARRY_FORWARD_YEAR_WINDOW for other in ca_years[row["author_id"]]
        ):
            row["ca_basis"] = CA_BASIS_CARRY
            author_state[row["author_id"]]["ca_works"].add(row["work_id"])


def normalize_records(
    records: Iterable[Mapping[str, Any]],
    *,
    institution_path: str | Path,
    output_dir: str | Path,
    qc_path: str | Path,
    source: str,
    author_overrides_path: str | Path = "config/author_overrides.csv",
    suppressions_path: str | Path | None = "curation/suppressions.csv",
    generated_at: str | None = None,
    state_agencies_path: str | Path | None = STATE_AGENCIES_PATH,
) -> NormalizationResult:
    """Normalize raw OpenAlex work objects into C3-shaped Parquet tables.

    Works and authors listed in ``suppressions_path`` are dropped here as well as at
    export (owner decision GOV-B, 2026-11-10: suppressed records are excluded at ingest).
    """

    registry = _read_registry(institution_path)
    agencies = (
        load_state_agencies(state_agencies_path)
        if state_agencies_path is not None and Path(state_agencies_path).exists()
        else []
    )
    for agency in agencies:
        registry.setdefault(agency.id, registry_row(agency))
    overrides = _load_overrides(author_overrides_path)
    suppressed_authors: frozenset[str] = frozenset()
    suppressed_works: frozenset[str] = frozenset()
    if suppressions_path is not None and Path(suppressions_path).exists():
        suppressed_authors, suppressed_works = load_suppressions(suppressions_path)
    work_rows: dict[str, Mapping[str, Any]] = {}
    source_count = 0
    for record in records:
        source_count += 1
        work_id = compact_id(record.get("id"))
        if work_id and work_id not in suppressed_works:
            work_rows[work_id] = record

    works: list[dict[str, Any]] = []
    authorships: list[dict[str, Any]] = []
    institution_rows: dict[str, dict[str, Any]] = {}
    author_state: dict[str, dict[str, Any]] = {}
    missing_affiliations = 0
    null_author_ids = 0
    unresolved_links = 0
    ca_affiliation_without_resolved: set[str] = set()

    for work_id in sorted(work_rows):
        work = work_rows[work_id]
        raw_authorships = work.get("authorships") or []
        if not isinstance(raw_authorships, Sequence) or isinstance(raw_authorships, (str, bytes)):
            raw_authorships = []
        work_ca_like = False
        work_resolved_ca = False
        total_authors = len(raw_authorships)

        for index, raw_authorship in enumerate(raw_authorships):
            if not isinstance(raw_authorship, Mapping):
                continue
            author = raw_authorship.get("author")
            author = author if isinstance(author, Mapping) else {}
            author_id = compact_id(author.get("id"))
            if author_id and author_id in suppressed_authors:
                continue
            author_name = _string(author.get("display_name"))
            institution_values = raw_authorship.get("institutions") or []
            if not isinstance(institution_values, Sequence) or isinstance(
                institution_values, (str, bytes)
            ):
                institution_values = []
            institution_ids: list[str] = []
            for institution in institution_values:
                if not isinstance(institution, Mapping):
                    continue
                inst_id = compact_id(institution.get("id"))
                if not inst_id:
                    continue
                institution_ids.append(inst_id)
                if inst_id not in registry:
                    unresolved_links += 1
                row = _raw_institution_row(institution, registry.get(inst_id))
                if row:
                    institution_rows[inst_id] = row
            institution_ids = list(dict.fromkeys(institution_ids))
            raw_affiliation_values = raw_authorship.get("raw_affiliation_strings")
            if isinstance(raw_affiliation_values, Sequence) and not isinstance(
                raw_affiliation_values, (str, bytes)
            ):
                raw_affiliation = " | ".join(
                    _string(value) for value in raw_affiliation_values if value
                )
            else:
                raw_affiliation = _string(raw_authorship.get("raw_affiliation"))
            matched_agencies = match_state_agencies(raw_affiliation, agencies)
            if matched_agencies:
                # Replace the umbrella OpenAlex linked (CalEPA / State of California) with
                # the named agency, so the work is not counted for both.
                institution_ids = apply_state_agencies(institution_ids, matched_agencies)
                for agency_id in matched_agencies:
                    institution_rows[agency_id] = dict(registry[agency_id])
            if not raw_affiliation:
                missing_affiliations += 1
            if not author_id:
                null_author_ids += 1

            resolved_ca = any(
                registry.get(inst_id, {}).get("ca_flag") for inst_id in institution_ids
            )
            ca_like = _looks_california(raw_affiliation)
            if resolved_ca:
                ca_basis = CA_BASIS_REGISTRY
            elif matches_california_affiliation(raw_affiliation):
                ca_basis = CA_BASIS_RAW
            else:
                ca_basis = ""
            work_resolved_ca = work_resolved_ca or resolved_ca
            work_ca_like = work_ca_like or ca_like
            position = _author_position(index, total_authors, raw_authorship.get("author_position"))
            authorships.append(
                {
                    "work_id": work_id,
                    "author_id": author_id,
                    "author_name": author_name,
                    "position": position,
                    "is_corresponding": bool(raw_authorship.get("is_corresponding", False)),
                    "institution_ids": institution_ids,
                    "raw_affiliation": raw_affiliation,
                    "ca_basis": ca_basis,
                }
            )

            if author_id:
                state = author_state.setdefault(
                    author_id,
                    {
                        "author_id": author_id,
                        "name": author_name,
                        "orcid": _string(author.get("orcid")),
                        "works": set(),
                        "ca_works": set(),
                    },
                )
                state["name"] = state["name"] or author_name
                state["orcid"] = state["orcid"] or _string(author.get("orcid"))
                state["works"].add(work_id)
                if ca_basis:
                    state["ca_works"].add(work_id)

        if work_ca_like and not work_resolved_ca:
            ca_affiliation_without_resolved.add(work_id)
        location = _location(work)
        open_access = work.get("open_access")
        open_access = open_access if isinstance(open_access, Mapping) else {}
        primary_topic = work.get("primary_topic")
        primary_topic = primary_topic if isinstance(primary_topic, Mapping) else {}
        pub_year = _number(work.get("publication_year"))
        works.append(
            {
                "work_id": work_id,
                "doi": _string(work.get("doi")),
                "title": _string(work.get("title")),
                "abstract": _abstract_from_inverted_index(work.get("abstract_inverted_index")),
                "year": pub_year,
                "pub_date": _string(work.get("publication_date")),
                "type": _string(work.get("type")),
                "journal": _string(_source(work).get("display_name")),
                "is_oa": bool(open_access.get("is_oa", work.get("is_oa", False))),
                "oa_status": _string(open_access.get("oa_status")),
                "oa_url": _string(
                    open_access.get("oa_url")
                    or location.get("landing_page_url")
                    or location.get("pdf_url")
                ),
                "license": _string(location.get("license")),
                "openalex_topics": _topic_ids(work),
                "primary_topic": compact_id(primary_topic.get("id")),
                "cited_by_count": _number(work.get("cited_by_count")) or 0,
                # AT-3 excludes retracted works from analytics; OpenAlex sends a boolean.
                "is_retracted": work.get("is_retracted") is True,
                "first_seen": _string(work.get("fetched_at_utc")),
                "last_updated": _string(work.get("updated_date")),
                "ca_led": False,
                "ca_any_author": False,
            }
        )

    _apply_carry_forward(authorships, works, author_state)
    ca_any_works = {row["work_id"] for row in authorships if row["ca_basis"]}
    ca_led_works = {
        row["work_id"] for row in authorships if row["ca_basis"] and row["position"] == "first"
    }
    for row in works:
        row["ca_any_author"] = row["work_id"] in ca_any_works
        row["ca_led"] = row["work_id"] in ca_led_works

    # Blank abstracts OpenAlex attached to unrelated works (atlas.ingest.abstract_qc),
    # so no page, rule or model shows or uses another paper's abstract.
    misattached = misattached_abstract_ids(works)
    for row in works:
        if row["work_id"] in misattached:
            row["abstract"] = ""

    # Collapse near-duplicate works before anything is written. Authorships and
    # author work sets of collapsed works are re-pointed to the kept work.
    all_works = works
    collapse = _collapse_near_duplicates(all_works)
    works = collapse.kept
    keeper_of = {row["work_id"]: row["duplicate_of"] for row in collapse.duplicate_rows}
    any_ca_by_id = {row["work_id"]: row["ca_any_author"] for row in all_works}
    kept_by_id = {row["work_id"]: row for row in works}
    for duplicate_id, keeper_id in keeper_of.items():
        kept_row = kept_by_id[keeper_id]
        kept_row["ca_any_author"] = bool(kept_row["ca_any_author"] or any_ca_by_id[duplicate_id])
    authorships = _repoint_authorships(authorships, keeper_of)
    work_year = {row["work_id"]: row["year"] for row in works}

    authors = []
    for author_id in sorted(author_state):
        state = author_state[author_id]
        author_works = {keeper_of.get(work, work) for work in state["works"]}
        ca_works = {keeper_of.get(work, work) for work in state["ca_works"]}
        years = [work_year[work] for work in author_works if work_year.get(work) is not None]
        authors.append(
            {
                "author_id": author_id,
                "name": state["name"],
                "orcid": state["orcid"],
                "ca_works_count": len(ca_works),
                "first_year": min(years) if years else None,
                "last_year": max(years) if years else None,
                "domain_tags": [],
                "override_flags": overrides.get(author_id, []),
            }
        )

    metrics = {
        "source_work_rows": source_count,
        "works": len(works),
        "authorships": len(authorships),
        "authors": len(authors),
        "institutions": len(institution_rows),
        "missing_affiliations": missing_affiliations,
        "null_author_ids": null_author_ids,
        "unresolved_institution_links": unresolved_links,
        "ca_affiliation_without_resolved_institution": len(
            {work for work in ca_affiliation_without_resolved if work not in keeper_of}
        ),
        "ca_led_works": sum(bool(row["ca_led"]) for row in works),
        "ca_any_author_works": sum(bool(row["ca_any_author"]) for row in works),
        "misattached_abstracts_blanked": len(misattached),
        "near_duplicates_collapsed": len(collapse.duplicate_rows),
        "near_duplicate_groups": len(set(keeper_of.values())),
        "skipped_same_title_distinct_doi": collapse.skipped_distinct_doi,
        "authorships_ca_registry": sum(r["ca_basis"] == CA_BASIS_REGISTRY for r in authorships),
        "authorships_ca_raw_affiliation": sum(r["ca_basis"] == CA_BASIS_RAW for r in authorships),
        "authorships_ca_carry_forward": sum(r["ca_basis"] == CA_BASIS_CARRY for r in authorships),
    }
    output = Path(output_dir)
    _atomic_write_table(output / "works.parquet", works, WORKS_SCHEMA)
    _atomic_write_table(output / "authorships.parquet", authorships, AUTHORSHIPS_SCHEMA)
    _atomic_write_table(output / "authors.parquet", authors, AUTHORS_SCHEMA)
    _atomic_write_table(
        output / "institutions.parquet",
        (institution_rows[key] for key in sorted(institution_rows)),
        INSTITUTIONS_SCHEMA,
    )
    qc = Path(qc_path)
    _atomic_write_text(
        qc,
        _qc_markdown(
            metrics,
            generated_at=generated_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
            source=source,
        ),
    )
    return NormalizationResult(output, qc, metrics)


def normalize_raw_parquet(
    raw_path: str | Path,
    *,
    institution_path: str | Path,
    output_dir: str | Path,
    qc_path: str | Path,
    author_overrides_path: str | Path = "config/author_overrides.csv",
    suppressions_path: str | Path | None = "curation/suppressions.csv",
    generated_at: str | None = None,
) -> NormalizationResult:
    """Read S2.1's raw Parquet and normalize each embedded work JSON object."""

    table = pq.read_table(raw_path, columns=["raw_json", "fetched_at_utc"])
    records = []
    for row in table.to_pylist():
        record = json.loads(row["raw_json"])
        if not isinstance(record, dict):
            raise ValueError("raw_json must contain an OpenAlex work object")
        record["fetched_at_utc"] = row.get("fetched_at_utc") or ""
        records.append(record)
    return normalize_records(
        records,
        institution_path=institution_path,
        output_dir=output_dir,
        qc_path=qc_path,
        source=str(raw_path),
        author_overrides_path=author_overrides_path,
        suppressions_path=suppressions_path,
        generated_at=generated_at,
    )


def normalize_fixture(
    fixture_path: str | Path,
    *,
    institution_path: str | Path,
    output_dir: str | Path,
    qc_path: str | Path,
    author_overrides_path: str | Path = "config/author_overrides.csv",
    suppressions_path: str | Path | None = "curation/suppressions.csv",
    generated_at: str | None = "fixture",
) -> NormalizationResult:
    """Normalize a committed JSON fixture without contacting OpenAlex."""

    payload = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) > 200:
        raise ValueError("S2.2 fixture must be a JSON list of at most 200 works")
    records = [record for record in payload if isinstance(record, Mapping)]
    return normalize_records(
        records,
        institution_path=institution_path,
        output_dir=output_dir,
        qc_path=qc_path,
        source=str(fixture_path),
        author_overrides_path=author_overrides_path,
        suppressions_path=suppressions_path,
        generated_at=generated_at,
    )
