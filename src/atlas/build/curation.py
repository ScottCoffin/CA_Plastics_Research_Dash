"""Curation inputs applied by the S3.1 site export (S10.2 corrections).

Three CSV files under ``curation/`` are read at export time:

* ``suppressions.csv``: authors and works removed from every public payload;
* ``overrides_works.csv``: allowlisted field overrides on work rows;
* ``author_merges.csv``: authorships re-pointed from one author ID to another.

Every active row needs a non-empty ``reviewed_by``. Malformed rows raise
``ValueError`` so that a bad correction stops the build instead of being
skipped silently. Author splits are not represented here; they need an
OpenAlex correction request (see ``docs/CORRECTIONS.md``).
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SUPPRESSIONS_HEADER = ("kind", "id", "reason", "requested_at", "reviewed_by")
WORK_OVERRIDES_HEADER = ("work_id", "field", "value", "reason", "reviewed_by", "reviewed_at")
AUTHOR_MERGES_HEADER = ("from_author_id", "to_author_id", "reason", "reviewed_by", "reviewed_at")
SUPPRESSION_KINDS = ("author", "work")
OPENALEX_PREFIX = "https://openalex.org/"

# Public field name -> (table, row key, value type). ``work`` fields live on the
# work row; ``label`` fields live on the work label row (S2.3 output).
WORK_OVERRIDE_FIELDS: dict[str, tuple[str, str, str]] = {
    "title": ("work", "title", "text"),
    "publication_year": ("work", "year", "int"),
    "ca_led": ("work", "ca_led", "bool"),
    "ca_any_author": ("work", "ca_any_author", "bool"),
    "plastic_related": ("label", "plastic_related", "bool"),
    "study_type": ("label", "study_type", "text"),
    "domain_tags": ("label", "domain_tags", "tags"),
    "facet_tags": ("label", "facet_tags", "tags"),
}


@dataclass(frozen=True)
class Curation:
    """Validated curation actions, keyed by compact OpenAlex IDs."""

    suppressed_authors: frozenset[str] = frozenset()
    suppressed_works: frozenset[str] = frozenset()
    work_overrides: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    author_merges: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CuratedTables:
    """Normalized tables after curation, plus counts for build metadata."""

    works: list[dict[str, Any]]
    authorships: list[dict[str, Any]]
    authors: list[dict[str, Any]]
    labels: dict[str, dict[str, Any]]
    counts: dict[str, int]


def compact_id(value: object) -> str:
    """Strip whitespace and the OpenAlex URL prefix from an ID."""
    text = str(value or "").strip()
    return text[len(OPENALEX_PREFIX) :] if text.startswith(OPENALEX_PREFIX) else text


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _read(path: str | Path, header: Sequence[str]) -> list[tuple[int, dict[str, str]]]:
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != tuple(header):
            raise ValueError(f"{path}: header must be {','.join(header)}")
        rows = []
        for number, row in enumerate(reader, start=2):
            rows.append(
                (
                    number,
                    {key: (value or "").strip() for key, value in row.items() if key},
                )
            )
        return rows


def _require(row: Mapping[str, str], number: int, path: str | Path, names: Sequence[str]) -> None:
    for name in names:
        if not row.get(name):
            raise ValueError(f"{path} row {number}: {name} is required")


def _coerce(name: str, kind: str, raw: str, path: str | Path, number: int) -> Any:
    if kind == "tags":
        return sorted({part.strip() for part in raw.split("|") if part.strip()})
    if not raw:
        raise ValueError(f"{path} row {number}: value is required for {name}")
    if kind == "text":
        return raw
    if kind == "int":
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"{path} row {number}: {name} must be an integer") from None
    lowered = raw.lower()
    if lowered not in {"true", "false"}:
        raise ValueError(f"{path} row {number}: {name} must be true or false")
    return lowered == "true"


def load_suppressions(path: str | Path) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(author_ids, work_ids)`` listed in ``suppressions.csv``."""
    authors: set[str] = set()
    works: set[str] = set()
    for number, row in _read(path, SUPPRESSIONS_HEADER):
        _require(row, number, path, ("kind", "id", "reason", "reviewed_by"))
        kind = row["kind"].lower()
        if kind not in SUPPRESSION_KINDS:
            raise ValueError(f"{path} row {number}: kind must be author or work")
        (authors if kind == "author" else works).add(compact_id(row["id"]))
    return frozenset(authors), frozenset(works)


def load_work_overrides(path: str | Path) -> dict[str, dict[str, Any]]:
    """Return typed ``{work_id: {field: value}}`` from ``overrides_works.csv``."""
    overrides: dict[str, dict[str, Any]] = {}
    for number, row in _read(path, WORK_OVERRIDES_HEADER):
        _require(row, number, path, ("work_id", "field", "reason", "reviewed_by", "reviewed_at"))
        name = row["field"]
        if name not in WORK_OVERRIDE_FIELDS:
            allowed = ", ".join(sorted(WORK_OVERRIDE_FIELDS))
            raise ValueError(
                f"{path} row {number}: field {name!r} cannot be overridden; allowed: {allowed}"
            )
        work_id = compact_id(row["work_id"])
        values = overrides.setdefault(work_id, {})
        if name in values:
            raise ValueError(f"{path} row {number}: {name} is overridden twice for one work")
        _table, _key, kind = WORK_OVERRIDE_FIELDS[name]
        values[name] = _coerce(name, kind, row["value"], path, number)
    return overrides


def load_author_merges(path: str | Path) -> dict[str, str]:
    """Return ``{from_author_id: final_author_id}``, resolving chained merges."""
    direct: dict[str, str] = {}
    for number, row in _read(path, AUTHOR_MERGES_HEADER):
        _require(row, number, path, ("from_author_id", "to_author_id", "reason", "reviewed_by"))
        source = compact_id(row["from_author_id"])
        target = compact_id(row["to_author_id"])
        if source == target:
            raise ValueError(f"{path} row {number}: from and to are the same author")
        if source in direct:
            raise ValueError(f"{path} row {number}: {source} is merged more than once")
        direct[source] = target
    return {source: _final_target(source, direct, path) for source in direct}


def _final_target(source: str, direct: Mapping[str, str], path: str | Path) -> str:
    seen = {source}
    target = direct[source]
    while target in direct:
        if target in seen:
            raise ValueError(f"{path}: author merge cycle through {target}")
        seen.add(target)
        target = direct[target]
    return target


def load_curation(
    *,
    suppressions_path: str | Path | None = None,
    work_overrides_path: str | Path | None = None,
    author_merges_path: str | Path | None = None,
) -> Curation:
    """Load each curation file that is given; missing paths mean no actions."""
    authors: frozenset[str] = frozenset()
    works: frozenset[str] = frozenset()
    if suppressions_path is not None:
        authors, works = load_suppressions(suppressions_path)
    overrides = load_work_overrides(work_overrides_path) if work_overrides_path else {}
    merges = load_author_merges(author_merges_path) if author_merges_path else {}
    return Curation(
        suppressed_authors=authors,
        suppressed_works=works,
        work_overrides=overrides,
        author_merges=merges,
    )


def apply_curation(
    *,
    works: Sequence[Mapping[str, Any]],
    authorships: Sequence[Mapping[str, Any]],
    authors: Sequence[Mapping[str, Any]],
    labels: Mapping[str, Mapping[str, Any]],
    curation: Curation,
) -> CuratedTables:
    """Apply suppressions, author merges and work overrides before aggregation.

    A suppressed author is removed from authorships, from the author table and
    from every work's author list. A work whose only linked authors were removed
    is dropped with them, so that no orphaned work stays attributed to nobody.
    Authors left without any authorship through this process are dropped too.
    """
    suppressed_authors = curation.suppressed_authors
    merges = curation.author_merges
    counts = {
        "suppressed_authors_listed": len(suppressed_authors),
        "suppressed_works_listed": len(curation.suppressed_works),
        "author_merges_listed": len(merges),
        "authorships_repointed": 0,
        "authorships_removed": 0,
        "works_removed": 0,
        "authors_removed": 0,
        "work_overrides_applied": 0,
        "work_overrides_skipped": 0,
    }

    linked_before_works = {
        _text(row.get("work_id")) for row in authorships if _text(row.get("author_id"))
    } - {""}
    linked_before_authors = {
        _text(row.get("author_id")) for row in authorships if _text(row.get("work_id"))
    } - {""}

    kept_links: list[dict[str, Any]] = []
    for row in authorships:
        work_id = _text(row.get("work_id"))
        author_id = _text(row.get("author_id"))
        resolved = merges.get(author_id, author_id)
        if (
            work_id in curation.suppressed_works
            or author_id in suppressed_authors
            or resolved in suppressed_authors
        ):
            counts["authorships_removed"] += 1
            continue
        if resolved != author_id:
            counts["authorships_repointed"] += 1
            row = {**row, "author_id": resolved}
        kept_links.append(dict(row))

    linked_after_works = {
        _text(row.get("work_id")) for row in kept_links if _text(row.get("author_id"))
    }
    linked_after_authors = {
        _text(row.get("author_id")) for row in kept_links if _text(row.get("work_id"))
    }
    removed_works = curation.suppressed_works | (linked_before_works - linked_after_works)
    removed_authors = (
        suppressed_authors | frozenset(merges) | (linked_before_authors - linked_after_authors)
    )

    kept_works: list[dict[str, Any]] = []
    for row in works:
        work_id = _text(row.get("work_id"))
        if work_id in removed_works:
            counts["works_removed"] += 1
            continue
        kept_works.append(dict(row))

    kept_authors = []
    for row in authors:
        author_id = _text(row.get("author_id"))
        if author_id in removed_authors:
            counts["authors_removed"] += 1
            continue
        kept_authors.append(dict(row))

    by_id = {_text(row.get("work_id")): row for row in kept_works}
    new_labels: dict[str, dict[str, Any]] = {
        work_id: dict(row) for work_id, row in labels.items() if work_id not in removed_works
    }
    for work_id, values in curation.work_overrides.items():
        if work_id not in by_id:
            counts["work_overrides_skipped"] += len(values)
            continue
        for name, value in values.items():
            table, key, _kind = WORK_OVERRIDE_FIELDS[name]
            if table == "work":
                by_id[work_id][key] = value
            else:
                new_labels[work_id] = {
                    "work_id": work_id,
                    **new_labels.get(work_id, {}),
                    key: value,
                }
            counts["work_overrides_applied"] += 1

    return CuratedTables(
        works=kept_works,
        authorships=kept_links,
        authors=kept_authors,
        labels=new_labels,
        counts=counts,
    )
