"""Export normalized atlas tables into deterministic static-site payloads.

The exporter deliberately keeps the browser contract independent from the
Parquet C3 tables.  ``index.json`` contains only fields needed for list views
and filtering; complete researcher records are split into one file per author.
All output is JSON-serializable, sorted by stable IDs, and written atomically.
"""

from __future__ import annotations

import gzip
import json
import re
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.build.curation import (
    apply_curation,
    load_curation,
    load_model_relevance,
    load_work_owner_reviewed,
    load_work_relevance,
)

SCHEMA_VERSION = "s3.1"


@dataclass(frozen=True)
class ExportResult:
    """Files and counts produced by one export run."""

    output_dir: Path
    metadata_path: Path
    counts: dict[str, int]
    sizes: dict[str, dict[str, int]]
    curation: dict[str, int] = field(default_factory=dict)


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _bool(value: object) -> bool:
    return bool(value)


def _list(value: object) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _sorted_unique(values: Iterable[object]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _read(path: str | Path, *, required: bool = True) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        if required:
            raise FileNotFoundError(f"required exporter input is missing: {file_path}")
        return []
    return [dict(row) for row in pq.read_table(file_path).to_pylist()]


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(text)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _work_label(row: Mapping[str, Any] | None) -> dict[str, Any]:
    row = row or {}
    return {
        "plastic_related": row.get("plastic_related"),
        "plastic_tier": _text(row.get("plastic_tier")),
        "domain_tags": _sorted_unique(_list(row.get("domain_tags"))),
        "facet_tags": _sorted_unique(_list(row.get("facet_tags"))),
        "study_type": _text(row.get("study_type")),
        "needs_review": row.get("needs_review"),
    }


def _work_payload(
    row: Mapping[str, Any],
    label: Mapping[str, Any] | None,
    authors_by_work: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any]:
    work_id = _text(row.get("work_id"))
    authorships = authors_by_work.get(work_id, [])
    author_ids = _sorted_unique(a.get("author_id") for a in authorships)
    institution_ids = _sorted_unique(
        institution_id
        for authorship in authorships
        for institution_id in _list(authorship.get("institution_ids"))
    )
    tags = _work_label(label)
    return {
        "work_id": work_id,
        "title": _text(row.get("title")),
        "year": row.get("year"),
        "type": _text(row.get("type")),
        "ca_led": _bool(row.get("ca_led")),
        "ca_any_author": _bool(row.get("ca_any_author")),
        "cited_by_count": _int(row.get("cited_by_count")),
        "author_ids": author_ids,
        "institution_ids": institution_ids,
        **tags,
    }


def _datasets_by_work(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, str]]]:
    """Group S9.2 work-dataset links by work; each entry is ``{doi, relation, evidence_type}``."""
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        work_id = _text(row.get("work_id"))
        doi = _text(row.get("dataset_doi"))
        if work_id and doi:
            grouped[work_id].append(
                {
                    "doi": doi,
                    "relation": _text(row.get("relation_type")),
                    "evidence_type": _text(row.get("evidence_type")),
                }
            )
    return {
        work_id: sorted(items, key=lambda item: (item["doi"], item["evidence_type"]))
        for work_id, items in grouped.items()
    }


# Corresponding-author emails sometimes appear inside abstracts; the public payload
# must not carry them (S10.2 privacy scan).
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


def _redact_contacts(text: str) -> str:
    return _EMAIL_RE.sub("[email removed]", text)


def _full_work_payload(
    row: Mapping[str, Any],
    slim: Mapping[str, Any],
    datasets: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    payload = {
        **dict(slim),
        "doi": _text(row.get("doi")),
        "abstract": _redact_contacts(_text(row.get("abstract"))),
        "pub_date": _text(row.get("pub_date")),
        "journal": _text(row.get("journal")),
        "is_oa": _bool(row.get("is_oa")),
        "oa_status": _text(row.get("oa_status")),
        "oa_url": _text(row.get("oa_url")),
        "license": _text(row.get("license")),
        "openalex_topics": _sorted_unique(_list(row.get("openalex_topics"))),
        "primary_topic": _text(row.get("primary_topic")),
        "last_updated": _text(row.get("last_updated")),
    }
    # Additive: the key is omitted entirely for works without dataset links.
    if datasets:
        payload["datasets"] = [dict(item) for item in datasets]
    return payload


def _write_author_details(
    output_dir: Path,
    authors: Sequence[Mapping[str, Any]],
    works_by_author: Mapping[str, list[Mapping[str, Any]]],
) -> None:
    for author in authors:
        author_id = _text(author.get("author_id"))
        if not author_id:
            continue
        detail = {
            "schema_version": SCHEMA_VERSION,
            "author": dict(author),
            "works": list(works_by_author.get(author_id, [])),
        }
        _atomic_json(output_dir / "authors" / f"{author_id}.json", detail)


EXPERTS_PER_INSTITUTION = 150
INSTITUTION_WORKS_MAX_BYTES = 25_000_000


def _institution_experts(
    authorship_rows: Sequence[Mapping[str, Any]],
    full_work_by_id: Mapping[str, Mapping[str, Any]],
    index_by_id: Mapping[str, Mapping[str, Any]],
    career: Mapping[str, Mapping[str, int]],
) -> dict[str, list[dict[str, Any]]]:
    """Authors per institution from authorship rows that list the institution itself."""
    works_at: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    for row in authorship_rows:
        author_id = _text(row.get("author_id"))
        work_id = _text(row.get("work_id"))
        if not author_id or work_id not in full_work_by_id:
            continue
        names.setdefault(author_id, _text(row.get("author_name")))
        for inst_id in {_text(i) for i in _list(row.get("institution_ids")) if _text(i)}:
            works_at[(inst_id, author_id)].add(work_id)
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for (inst_id, author_id), work_ids in works_at.items():
        works = [full_work_by_id[w] for w in work_ids]
        years = [w["year"] for w in works if isinstance(w.get("year"), int)]
        topics: Counter[str] = Counter()
        per_year: Counter[str] = Counter()
        for work in works:
            topics.update({t for t in work.get("domain_tags", []) if not t.startswith("matrix:")})
            if isinstance(work.get("year"), int):
                per_year[str(work["year"])] += 1
        indexed = index_by_id.get(author_id)
        metrics = career.get(author_id, {})
        plastic_here = sum(1 for w in works if w.get("plastic_related") is True)
        if indexed:
            plastic_count = indexed.get("plastic_works_count")
            plastic_cites = indexed.get("plastic_citations")
            h_index = indexed.get("h_index")
            name = indexed.get("name") or names.get(author_id, "")
        else:
            covered = bool(metrics.get("plastic_covered"))
            plastic_count = metrics.get("plastic_works") if covered else plastic_here
            plastic_cites = metrics.get("plastic_cites") if covered else None
            h_index = metrics.get("h_index")
            name = names.get(author_id, "")
        grouped[inst_id].append(
            {
                "author_id": author_id,
                "name": name,
                "in_atlas_index": indexed is not None,
                "works_at_institution": len(work_ids),
                "first_year": min(years) if years else None,
                "last_year": max(years) if years else None,
                "plastic_works_count": plastic_count,
                "plastic_citations": plastic_cites,
                "h_index": h_index,
                "topics": sorted(topics.items(), key=lambda kv: (-kv[1], kv[0]))[:5],
                "years": dict(sorted(per_year.items())),
            }
        )
    for experts in grouped.values():
        experts.sort(key=lambda e: (-e["works_at_institution"], -(e["h_index"] or 0), e["name"]))
    return grouped


def _ca_connection(
    authorships: Sequence[Mapping[str, Any]],
    ca_institutions: set[str],
    institution_names: Mapping[str, str],
) -> dict[str, Any]:
    """California co-authors on a work, and the California institutions they list."""
    authors: list[dict[str, Any]] = []
    institutions: dict[str, set[str]] = {}
    seen: set[str] = set()
    for row in authorships:
        author_id = _text(row.get("author_id"))
        ca_ids = sorted({_text(i) for i in _list(row.get("institution_ids"))} & ca_institutions)
        basis = _text(row.get("ca_basis"))
        if not (ca_ids or basis) or author_id in seen:
            continue
        seen.add(author_id)
        authors.append(
            {
                "author_id": author_id,
                "name": _text(row.get("author_name")),
                "ca_basis": basis,
                "institution_ids": ca_ids,
            }
        )
        for inst_id in ca_ids:
            institutions.setdefault(inst_id, set())
            if basis:
                institutions[inst_id].add(basis)
    return {
        "authors": authors,
        "institutions": [
            {
                "inst_id": inst_id,
                "name": institution_names.get(inst_id, inst_id),
                "ca_basis": sorted(bases),
            }
            for inst_id, bases in sorted(institutions.items())
        ],
    }


def _write_institution_works(
    output_dir: Path,
    institutions: Sequence[Mapping[str, Any]],
    full_work_by_id: Mapping[str, Mapping[str, Any]],
    works_for_institution: Mapping[str, set[str]],
    authors_by_work: Mapping[str, list[Mapping[str, Any]]],
    experts_by_institution: Mapping[str, list[dict[str, Any]]] | None = None,
    abstracts_for_collaborators: bool = True,
) -> None:
    """One lazily loaded publication file per institution (evidence-map page).

    Out-of-state institutions appear only through co-authorship with California
    researchers; their files carry ``scope: "collaborator"`` and a per-work
    ``ca_connection``.
    """
    folder = output_dir / "institution_works"
    folder.mkdir(parents=True, exist_ok=True)
    written: set[str] = set()
    ca_ids = {_text(i.get("inst_id")) for i in institutions if i.get("ca_flag")}
    names = {_text(i.get("inst_id")): _text(i.get("name")) for i in institutions}
    experts_by_institution = experts_by_institution or {}
    for institution in institutions:
        inst_id = _text(institution.get("inst_id"))
        if not inst_id or not institution.get("work_count"):
            continue
        collaborator = not institution.get("ca_flag")
        works = []
        for work_id in sorted(works_for_institution.get(inst_id, set())):
            if work_id not in full_work_by_id:
                continue
            ordered = sorted(
                authors_by_work.get(work_id, []),
                key=lambda a: {"first": 0, "last": 2}.get(_text(a.get("position")), 1),
            )
            entry = {
                **dict(full_work_by_id[work_id]),
                "author_names": [_text(a.get("author_name")) for a in ordered],
            }
            if collaborator:
                entry["ca_connection"] = _ca_connection(ordered, ca_ids, names)
                if not abstracts_for_collaborators:
                    entry["abstract"] = ""
            works.append(entry)
        works.sort(key=lambda w: (-(w.get("year") or 0), _text(w.get("title"))))
        name = f"{inst_id}.json"
        written.add(name)
        experts = experts_by_institution.get(inst_id, [])[:EXPERTS_PER_INSTITUTION]
        _atomic_json(
            folder / name,
            {
                "schema_version": SCHEMA_VERSION,
                "institution": {
                    **{k: institution[k] for k in institution if k not in {"years", "top_experts"}},
                    "scope": "collaborator" if collaborator else "california",
                },
                "experts": experts,
                "works": works,
            },
        )
    for stale in folder.glob("*.json"):
        if stale.name not in written:
            stale.unlink()


def _aggregate(works: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_year: defaultdict[int, dict[str, int]] = defaultdict(
        lambda: {"count": 0, "plastic_related_count": 0}
    )
    by_type: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"count": 0, "plastic_related_count": 0}
    )
    by_tag: defaultdict[str, dict[str, int]] = defaultdict(
        lambda: {"count": 0, "plastic_related_count": 0}
    )
    for work in works:
        related = work.get("plastic_related") is True
        year = work.get("year")
        if isinstance(year, int):
            by_year[year]["count"] += 1
            by_year[year]["plastic_related_count"] += int(related)
        work_type = _text(work.get("type")) or "unknown"
        by_type[work_type]["count"] += 1
        by_type[work_type]["plastic_related_count"] += int(related)
        for tag in _sorted_unique(
            [*_list(work.get("domain_tags")), *_list(work.get("facet_tags"))]
        ):
            by_tag[tag]["count"] += 1
            by_tag[tag]["plastic_related_count"] += int(related)
    return {
        "by_year": [{"year": year, **by_year[year]} for year in sorted(by_year)],
        "by_type": [{"type": work_type, **by_type[work_type]} for work_type in sorted(by_type)],
        "by_tag": [{"tag": tag, **by_tag[tag]} for tag in sorted(by_tag)],
    }


def export_site(
    *,
    works_path: str | Path,
    authors_path: str | Path,
    authorships_path: str | Path,
    institutions_path: str | Path,
    labels_path: str | Path | None = None,
    work_dataset_links_path: str | Path | None = None,
    suppressions_path: str | Path | None = None,
    work_overrides_path: str | Path | None = None,
    author_merges_path: str | Path | None = None,
    work_relevance_path: str | Path | None = None,
    model_relevance_path: str | Path | None = None,
    author_metrics_path: str | Path | None = None,
    output_dir: str | Path = "site/data",
    generated_at: str | None = None,
    ca_authors_only: bool = True,
) -> ExportResult:
    """Build all S3.1 payloads from normalized C3 tables.

    ``ca_authors_only`` keeps the Experts index and author files to authors with at
    least one California-affiliated authorship (``ca_works_count > 0``).

    ``labels_path`` is optional so the exporter can build a useful fixture or
    an early refresh before S2.3 output exists.  Missing label fields remain
    ``null`` rather than being inferred by the site builder.

    The optional ``curation/`` inputs (suppressions, work overrides and author
    merges) are applied before any payload is built; see ``atlas.build.curation``.
    ``work_relevance_path`` (``curation/work_relevance.csv``, reviewed plastic-relevance
    calls) replaces the rule's ``plastic_related`` first; owner overrides still win.
    ``author_metrics_path`` (``scripts/fetch_author_metrics.py``) adds career-wide
    OpenAlex ``cited_by_count`` and ``h_index``; merged records sum citations and keep
    the largest h-index. Plastics counts use the author's whole OpenAlex record when
    fetched (``plastic_basis`` = ``openalex``), else the exported CA corpus.
    """

    works_rows = _read(works_path)
    author_rows = _read(authors_path)
    authorship_rows = _read(authorships_path)
    institution_rows = _read(institutions_path)
    # Publish only California research: works with no CA authorship on any basis
    # (registry, raw affiliation, carry-forward) stay in the corpus but not on the site.
    # Applies in CA-only mode (the live export); fixtures without the column are unaffected.
    non_ca = {
        _text(row.get("work_id"))
        for row in works_rows
        if ca_authors_only and "ca_any_author" in row and row.get("ca_any_author") is False
    }
    if non_ca:
        works_rows = [row for row in works_rows if _text(row.get("work_id")) not in non_ca]
        authorship_rows = [
            row for row in authorship_rows if _text(row.get("work_id")) not in non_ca
        ]
    label_rows = _read(labels_path, required=False) if labels_path else []
    labels = {_text(row.get("work_id")): row for row in label_rows if _text(row.get("work_id"))}
    # Precedence, highest first: owner decision (owner_review confirmed/changed), owner AT-1
    # overrides, accepted model labels, Haiku (pending rows), then the rule's label.
    owner_reviewed: frozenset[str] = frozenset()
    if work_relevance_path:
        owner_reviewed = load_work_owner_reviewed(work_relevance_path)
        for work_id, related in load_work_relevance(work_relevance_path).items():
            labels[work_id] = {
                "work_id": work_id,
                **labels.get(work_id, {}),
                "plastic_related": related,
            }
    if model_relevance_path:
        for work_id, related in load_model_relevance(model_relevance_path).items():
            if work_id in owner_reviewed:
                continue  # never overrides an owner decision
            labels[work_id] = {
                "work_id": work_id,
                **labels.get(work_id, {}),
                "plastic_related": related,
            }
    # S9.2 links are opt-in: without a path, author payloads are byte-identical to before.
    link_rows = _read(work_dataset_links_path, required=False) if work_dataset_links_path else []
    datasets_by_work = _datasets_by_work(link_rows)
    curation = load_curation(
        suppressions_path=suppressions_path,
        work_overrides_path=work_overrides_path,
        author_merges_path=author_merges_path,
    )
    if owner_reviewed:
        # An owner decision in the works review app beats an AT-1 plastic_related override.
        trimmed = {
            work_id: {k: v for k, v in values.items() if k != "plastic_related"}
            if work_id in owner_reviewed
            else values
            for work_id, values in curation.work_overrides.items()
        }
        curation = replace(curation, work_overrides=trimmed)
    curated = apply_curation(
        works=works_rows,
        authorships=authorship_rows,
        authors=author_rows,
        labels=labels,
        curation=curation,
    )
    works_rows = curated.works
    authorship_rows = curated.authorships
    author_rows = curated.authors
    labels = curated.labels

    authors_by_work: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    works_by_author: defaultdict[str, list[str]] = defaultdict(list)
    institutions_by_author: defaultdict[str, set[str]] = defaultdict(set)
    institutions_by_work: defaultdict[str, set[str]] = defaultdict(set)
    for row in authorship_rows:
        work_id = _text(row.get("work_id"))
        author_id = _text(row.get("author_id"))
        if work_id:
            authors_by_work[work_id].append(row)
        if author_id:
            if work_id:
                works_by_author[author_id].append(work_id)
            institutions_by_author[author_id].update(
                _text(i) for i in _list(row.get("institution_ids")) if _text(i)
            )
        if work_id:
            institutions_by_work[work_id].update(
                _text(i) for i in _list(row.get("institution_ids")) if _text(i)
            )

    slim_works = [
        _work_payload(row, labels.get(_text(row.get("work_id"))), authors_by_work)
        for row in sorted(works_rows, key=lambda item: _text(item.get("work_id")))
        if _text(row.get("work_id"))
    ]
    full_work_by_id = {
        _text(row.get("work_id")): _full_work_payload(
            row,
            slim_works[index],
            datasets_by_work.get(_text(row.get("work_id")), ()),
        )
        for index, row in enumerate(
            sorted(
                (item for item in works_rows if _text(item.get("work_id"))),
                key=lambda item: _text(item.get("work_id")),
            )
        )
    }

    # Recount CA works from the curated authorships, so works removed by curation
    # (suppressed or owner-excluded) no longer count. Matches normalize's count when
    # nothing is removed.
    ca_institutions = {
        _text(row.get("inst_id")) for row in institution_rows if _bool(row.get("ca_flag"))
    }
    ca_works_by_author: defaultdict[str, set[str]] = defaultdict(set)
    # ``ca_basis`` (registry / raw_affiliation / author_carry_forward) is written by
    # normalize; tables without the column count institutions only, as before.
    has_ca_basis = any(_text(row.get("ca_basis")) for row in authorship_rows)
    if ca_institutions or has_ca_basis:
        for row in authorship_rows:
            if _text(row.get("ca_basis")) or ca_institutions.intersection(
                _text(i) for i in _list(row.get("institution_ids"))
            ):
                ca_works_by_author[_text(row.get("author_id"))].add(_text(row.get("work_id")))

    def ca_works_count(row: Mapping[str, Any]) -> int:
        if not ca_institutions and not has_ca_basis:
            return _int(row.get("ca_works_count"))
        return len(ca_works_by_author.get(_text(row.get("author_id")), ()))

    metric_rows = _read(author_metrics_path, required=False) if author_metrics_path else []
    career: dict[str, dict[str, int]] = {}
    for metric in metric_rows:
        target = curation.author_merges.get(
            _text(metric.get("author_id")), _text(metric.get("author_id"))
        )
        entry = career.setdefault(
            target, {"cited_by_count": 0, "h_index": 0, "plastic_works": 0, "plastic_cites": 0}
        )
        entry["cited_by_count"] += _int(metric.get("cited_by_count"))
        entry["h_index"] = max(entry["h_index"], _int(metric.get("h_index")))
        if _text(metric.get("plastic_fetched_at_utc")):
            # Whole-record plastics metrics (all of the author's OpenAlex works).
            entry["plastic_covered"] = 1
            entry["plastic_works"] += _int(metric.get("plastic_works_global"))
            entry["plastic_cites"] += _int(metric.get("plastic_citations_global"))
    slim_by_id = {work["work_id"]: work for work in slim_works}

    author_index: list[dict[str, Any]] = []
    for row in sorted(author_rows, key=lambda item: _text(item.get("author_id"))):
        author_id = _text(row.get("author_id"))
        if not author_id:
            continue
        if ca_authors_only and ca_works_count(row) <= 0:
            # spec A3.1: the researcher list shows California-affiliated researchers;
            # out-of-state co-authors stay visible on each work's author list.
            continue
        author_work_ids = sorted(set(works_by_author.get(author_id, [])))
        plastic_works = [
            slim_by_id[work_id]
            for work_id in author_work_ids
            if work_id in slim_by_id and slim_by_id[work_id].get("plastic_related") is True
        ]
        metrics = career.get(author_id, {})
        corpus_cites = sum(_int(w.get("cited_by_count")) for w in plastic_works)
        whole_record = bool(metrics.get("plastic_covered"))
        author_index.append(
            {
                "author_id": author_id,
                "name": _text(row.get("name")),
                "orcid": _text(row.get("orcid")),
                "ca_works_count": ca_works_count(row),
                "first_year": row.get("first_year"),
                "last_year": row.get("last_year"),
                "domain_tags": _sorted_unique(_list(row.get("domain_tags"))),
                "work_count": len(author_work_ids),
                "work_ids": author_work_ids,
                "cited_by_count": metrics.get("cited_by_count"),
                "h_index": metrics.get("h_index"),
                # Whole OpenAlex record when fetched (basis "openalex"); otherwise the
                # CA corpus only (basis "atlas_corpus"), which understates specialists
                # whose plastics papers mostly lack CA co-authors.
                "plastic_works_count": (
                    metrics["plastic_works"] if whole_record else len(plastic_works)
                ),
                "plastic_citations": metrics["plastic_cites"] if whole_record else corpus_cites,
                "plastic_basis": "openalex" if whole_record else "atlas_corpus",
                "ca_plastic_works_count": len(plastic_works),
                "institution_ids": sorted(institutions_by_author.get(author_id, set())),
            }
        )

    experts_by_institution = _institution_experts(
        authorship_rows,
        full_work_by_id,
        {a["author_id"]: a for a in author_index},
        career,
    )
    institutions: list[dict[str, Any]] = []
    work_lookup = {work["work_id"]: work for work in slim_works}
    authors_for_institution: defaultdict[str, set[str]] = defaultdict(set)
    works_for_institution: defaultdict[str, set[str]] = defaultdict(set)
    for author_id, work_ids in works_by_author.items():
        for institution_id in institutions_by_author.get(author_id, set()):
            authors_for_institution[institution_id].add(author_id)
            works_for_institution[institution_id].update(work_ids)
    for work_id, institution_ids in institutions_by_work.items():
        for institution_id in institution_ids:
            works_for_institution[institution_id].add(work_id)
    for row in sorted(institution_rows, key=lambda item: _text(item.get("inst_id"))):
        inst_id = _text(row.get("inst_id"))
        if not inst_id:
            continue
        inst_work_ids = sorted(works_for_institution.get(inst_id, set()))
        inst_tags = [
            tag
            for work_id in inst_work_ids
            for tag in [
                *_list(work_lookup.get(work_id, {}).get("domain_tags")),
                *_list(work_lookup.get(work_id, {}).get("facet_tags")),
            ]
        ]
        years = sorted(
            {
                work_lookup[work_id]["year"]
                for work_id in inst_work_ids
                if work_id in work_lookup and isinstance(work_lookup[work_id].get("year"), int)
            }
        )
        institutions.append(
            {
                "inst_id": inst_id,
                "ror": _text(row.get("ror")),
                "name": _text(row.get("name")),
                "city": _text(row.get("city")),
                "region": _text(row.get("region")),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "atlas_type": _text(row.get("atlas_type")) or "other",
                "ca_flag": _bool(row.get("ca_flag")),
                "work_count": len(inst_work_ids),
                "author_count": len(authors_for_institution.get(inst_id, set())),
                "years": years,
                "domain_tags": _sorted_unique(inst_tags),
                "top_experts": [
                    {
                        "author_id": e["author_id"],
                        "name": e["name"],
                        "works": e["works_at_institution"],
                        "topic": e["topics"][0][0] if e["topics"] else "",
                        "in_atlas_index": e["in_atlas_index"],
                    }
                    for e in experts_by_institution.get(inst_id, [])[:3]
                ],
            }
        )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    timestamp = generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    counts = {
        "works": len(slim_works),
        "authors": len(author_index),
        "institutions": len(institutions),
        "ca_institutions": sum(item["ca_flag"] for item in institutions),
        "labeled_works": len(labels.keys() & work_lookup.keys()),
    }
    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp,
        "counts": counts,
        "authors": author_index,
        "works": slim_works,
    }
    _atomic_json(output / "index.json", index)
    _atomic_json(
        output / "institutions.json",
        {"schema_version": SCHEMA_VERSION, "generated_at": timestamp, "institutions": institutions},
    )
    _atomic_json(
        output / "aggregates.json",
        {"schema_version": SCHEMA_VERSION, "generated_at": timestamp, **_aggregate(slim_works)},
    )
    _write_author_details(
        output,
        author_index,
        {
            author_id: [
                full_work_by_id[work_id]
                # dict.fromkeys drops duplicates left by merged authorships, keeping order.
                for work_id in dict.fromkeys(work_ids)
                if work_id in full_work_by_id
            ]
            for author_id, work_ids in works_by_author.items()
        },
    )
    _write_institution_works(
        output,
        institutions,
        full_work_by_id,
        works_for_institution,
        authors_by_work,
        experts_by_institution,
    )
    inst_works_bytes = sum(f.stat().st_size for f in (output / "institution_works").glob("*.json"))
    if inst_works_bytes > INSTITUTION_WORKS_MAX_BYTES:
        # Size guard: collaborator files drop abstracts first (California files keep theirs).
        _write_institution_works(
            output,
            institutions,
            full_work_by_id,
            works_for_institution,
            authors_by_work,
            experts_by_institution,
            abstracts_for_collaborators=False,
        )
    features = []
    for institution in institutions:
        if not institution["ca_flag"] or institution["lat"] is None or institution["lon"] is None:
            continue
        properties = {key: value for key, value in institution.items() if key not in {"lat", "lon"}}
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [institution["lon"], institution["lat"]],
                },
                "properties": properties,
            }
        )
    _atomic_json(
        output / "institutions.geojson",
        {"type": "FeatureCollection", "features": features},
    )

    sizes: dict[str, dict[str, int]] = {}
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.name == "build_metadata.json":
            continue
        raw = path.read_bytes()
        sizes[str(path.relative_to(output)).replace("\\", "/")] = {
            "bytes": len(raw),
            "gzip_bytes": len(gzip.compress(raw, mtime=0)),
        }
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": timestamp,
        "counts": counts,
        "files": sizes,
        "payload_bytes": sum(item["bytes"] for item in sizes.values()),
        "payload_gzip_bytes": sum(item["gzip_bytes"] for item in sizes.values()),
        "curation": curated.counts,
    }
    metadata_path = output / "build_metadata.json"
    _atomic_json(metadata_path, metadata)
    result_sizes = dict(sizes)
    result_sizes["build_metadata.json"] = {
        "bytes": metadata_path.stat().st_size,
        "gzip_bytes": len(gzip.compress(metadata_path.read_bytes(), mtime=0)),
    }
    return ExportResult(output, metadata_path, counts, result_sizes, curated.counts)
