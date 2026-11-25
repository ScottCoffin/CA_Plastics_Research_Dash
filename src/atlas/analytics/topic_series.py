"""Topic time series data layer (BQ-4.1).

Builds the year series that BQ-4.2 to BQ-4.4 consume: CA (``ca``, the regional corpus) counts per
approved, non-experimental topic tag among plastic-related works, a frozen label snapshot, global
counts by OpenAlex ``primary_topic`` (unscreened query hits), and the analytic-lens block.

The CA side mirrors the export's precedence for ``plastic_related`` (owner review, accepted
model labels, always-relevant and title rules, curation overrides) and its owner tag overrides.
Label sources per tag: ``rule`` (``work_labels.domain_tags``), ``owner`` (``overrides_works.csv``
``domain_tags``). No ``model`` tag labels exist yet; the variant is reserved. Nothing here reads the
network or writes under ``site/``.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.build.curation import (
    Curation,
    load_curation,
    load_model_relevance,
    load_work_low_confidence_false,
    load_work_owner_reviewed,
    load_work_relevance,
)
from atlas.ingest.abstract_qc import misattached_abstract_ids
from atlas.ingest.normalize import compact_id
from atlas.nlp.labels import always_relevant, title_relevant

SCHEMA = "bq4-series-v1"
SNAPSHOT_SCHEMA = "bq4-labels-snapshot-v1"
TOP_N = 30
OTHER_LABEL = "other"
FRAMING_RULE = "a lens is counted only when the work itself uses the frame, with a quoted excerpt"
LENS_CAPTION = (
    "Lens series count plastic-related works that use the framing (the work itself uses the frame, "
    "with a quoted excerpt). Lens counts are shown separately from topic counts and are never "
    "inferred from the topic."
)
GLOBAL_CAVEAT = (
    "Global counts are unscreened OpenAlex query hits grouped by primary_topic, not curated works."
)
NO_LABELS_MESSAGE = "no labels yet"
NO_LENS_MESSAGE = "no lens labels yet"
SNAPSHOT_SCHEMA_ARROW = pa.schema(
    [
        ("work_id", pa.string()),
        ("publication_year", pa.int64()),
        ("plastic_related", pa.bool_()),
        ("kind", pa.string()),
        ("tag", pa.string()),
        ("label_source", pa.string()),
    ]
)
SENSITIVITY_VARIANTS = ("all_sources", "owner_model_only", "rule_only")


@dataclass(frozen=True)
class RelevanceInputs:
    """Plastic-relevance decisions as the export reads them (``curation/`` CSV files)."""

    relevant: Mapping[str, bool] = field(default_factory=dict)
    owner_reviewed: frozenset[str] = frozenset()
    low_confidence_false: frozenset[str] = frozenset()
    model: Mapping[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class SeriesInputs:
    """In-memory inputs; the loader below fills these from the repository files."""

    works: Sequence[Mapping[str, Any]]  # normalized works rows
    labels: Sequence[Mapping[str, Any]]  # work_labels rows
    global_works: Sequence[Mapping[str, Any]]  # global works rows
    taxonomy: Mapping[str, Any]
    query_config: Mapping[str, Any]
    relevance: RelevanceInputs = field(default_factory=RelevanceInputs)
    curation: Curation = field(default_factory=Curation)


@dataclass(frozen=True)
class CaWork:
    """One CA work as the series see it. Sources map a label to ``rule`` or ``owner``."""

    work_id: str
    year: int | None
    plastic_related: bool
    topic_sources: Mapping[str, str] = field(default_factory=dict)
    lens_sources: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CaCorpus:
    """Working set after curation removals, plus the counts the payload reports."""

    works: list[CaWork]
    removed: int


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _year(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)  # type: ignore[call-overload]


def reported_tags(taxonomy: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return ``(reported, excluded)``: approved non-experimental tags, and experimental ones."""

    reported: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for entry in taxonomy.get("domain_tags") or []:
        tag = _text(entry.get("id"))
        if not tag:
            continue
        if entry.get("experimental") is True:
            excluded.append({"tag": tag, "reason": "experimental"})
            continue
        reported.append(
            {
                "tag": tag,
                "label": _text(entry.get("label")) or tag,
                "approval": _text(entry.get("status")) or "approved",
                "seed_concepts": len(entry.get("seed_concepts") or []),
            }
        )
    return reported, excluded


def lens_values(taxonomy: Mapping[str, Any]) -> list[str]:
    facet = (taxonomy.get("facets") or {}).get("analytic_lens") or {}
    return [str(value) for value in facet.get("values") or []]


def _ids(values: Iterable[object] | None) -> list[str]:
    return [_text(value) for value in values or [] if _text(value)]


def ca_corpus(inputs: SeriesInputs) -> CaCorpus:
    """Apply the export's plastic-relevance precedence and curation removals to CA works."""

    tags_allowed = {tag["tag"] for tag in reported_tags(inputs.taxonomy)[0]}
    lenses = set(lens_values(inputs.taxonomy))
    labels = {compact_id(row.get("work_id")): row for row in inputs.labels}
    rule_tier2 = {
        work_id
        for work_id, row in labels.items()
        if row.get("plastic_related") is True and row.get("plastic_tier") == "chemicals-in-plastics"
    }
    relevance = dict(inputs.relevance.relevant)  # owner review and assist rows (export order)
    policy = (inputs.query_config.get("relevance_policy") or {}) if inputs.query_config else {}
    if policy.get("tier2_survives_low_confidence_false"):
        for work_id in inputs.relevance.low_confidence_false & rule_tier2:
            relevance[work_id] = True
    relevance_rules = {work_id: bool(row.get("plastic_related")) for work_id, row in labels.items()}
    relevance_rules.update(relevance)
    for work_id, related in inputs.relevance.model.items():
        if work_id not in inputs.relevance.owner_reviewed:
            relevance_rules[work_id] = related
    works_rows = [dict(row) for row in inputs.works]
    shared = misattached_abstract_ids(works_rows)
    for row in works_rows:
        work_id = compact_id(row.get("work_id"))
        if not work_id or work_id in inputs.relevance.owner_reviewed:
            continue
        abstract = "" if work_id in shared else _text(row.get("abstract"))
        text = f"{_text(row.get('title'))} {abstract}"
        if always_relevant(text, inputs.query_config) or title_relevant(
            _text(row.get("title")), inputs.query_config
        ):
            relevance_rules[work_id] = True

    curation = inputs.curation
    removed_ids = curation.suppressed_works | frozenset(
        work_id
        for work_id, values in curation.work_overrides.items()
        if values.get("exclude") is True
    )
    owner_reviewed = inputs.relevance.owner_reviewed
    works: list[CaWork] = []
    removed = 0
    for row in works_rows:
        work_id = compact_id(row.get("work_id"))
        if not work_id:
            continue
        values = curation.work_overrides.get(work_id, {})
        if owner_reviewed and work_id in owner_reviewed:
            values = {k: v for k, v in values.items() if k != "plastic_related"}
        if values.get("ca_any_author", row.get("ca_any_author")) is not True:
            continue
        if work_id in removed_ids:
            removed += 1
            continue
        year = _year(values.get("publication_year", row.get("year")))
        plastic = bool(relevance_rules.get(work_id, False))
        if "plastic_related" in values:
            plastic = bool(values["plastic_related"])
        label = labels.get(work_id, {})
        topic_sources = {
            tag: "rule" for tag in _ids(label.get("domain_tags")) if tag in tags_allowed
        }
        lens_sources = {lens: "rule" for lens in _ids(label.get("facet_tags")) if lens in lenses}
        if "domain_tags" in values:
            topic_sources = {
                tag: "owner" for tag in _ids(values["domain_tags"]) if tag in tags_allowed
            }
        if "facet_tags" in values:
            lens_sources = {lens: "owner" for lens in _ids(values["facet_tags"]) if lens in lenses}
        works.append(
            CaWork(
                work_id=work_id,
                year=year,
                plastic_related=plastic,
                topic_sources=dict(sorted(topic_sources.items())),
                lens_sources=dict(sorted(lens_sources.items())),
            )
        )
    works.sort(key=lambda work: work.work_id)
    return CaCorpus(works=works, removed=removed)


def snapshot_rows(works: Sequence[CaWork]) -> list[dict[str, Any]]:
    """Long rows: one per work and label (topic or lens); one row with null labels if unlabelled."""

    rows: list[dict[str, Any]] = []
    for work in works:
        base = {
            "work_id": work.work_id,
            "publication_year": work.year,
            "plastic_related": work.plastic_related,
        }
        if not work.topic_sources and not work.lens_sources:
            rows.append({**base, "kind": None, "tag": None, "label_source": None})
        for tag, source in work.topic_sources.items():
            rows.append({**base, "kind": "topic", "tag": tag, "label_source": source})
        for lens, source in work.lens_sources.items():
            rows.append({**base, "kind": "lens", "tag": lens, "label_source": source})
    rows.sort(key=lambda r: (r["work_id"], r["kind"] or "", r["tag"] or ""))
    return rows


def snapshot_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    """Hash of the canonical JSON rows; independent of file format and input order."""

    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda r: json.dumps(r, sort_keys=True)):
        digest.update(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def works_from_snapshot(rows: Sequence[Mapping[str, Any]]) -> list[CaWork]:
    """Rebuild the CA works from frozen snapshot rows (inverse of ``snapshot_rows``)."""

    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["work_id"]].append(row)
    works: list[CaWork] = []
    for work_id in sorted(grouped):
        group = grouped[work_id]
        first = group[0]
        if any(
            (r["publication_year"], r["plastic_related"])
            != (first["publication_year"], first["plastic_related"])
            for r in group
        ):
            raise ValueError(f"snapshot rows for {work_id} disagree on year or plastic_related")
        topic = {r["tag"]: r["label_source"] for r in group if r["kind"] == "topic"}
        lens = {r["tag"]: r["label_source"] for r in group if r["kind"] == "lens"}
        works.append(
            CaWork(
                work_id=work_id,
                year=_year(first["publication_year"]),
                plastic_related=bool(first["plastic_related"]),
                topic_sources=topic,
                lens_sources=lens,
            )
        )
    return works


def write_snapshot(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    table = pa.Table.from_pylist(list(rows), schema=SNAPSHOT_SCHEMA_ARROW)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    pq.write_table(table, tmp)
    tmp.replace(target)


def read_snapshot(path: str | Path) -> list[dict[str, Any]]:
    return pq.read_table(path, schema=SNAPSHOT_SCHEMA_ARROW).to_pylist()


def load_relevance(work_relevance_path: str | Path, model_path: str | Path) -> RelevanceInputs:
    return RelevanceInputs(
        relevant=load_work_relevance(work_relevance_path),
        owner_reviewed=load_work_owner_reviewed(work_relevance_path),
        low_confidence_false=load_work_low_confidence_false(work_relevance_path),
        model=load_model_relevance(model_path),
    )


def load_curation_inputs(suppressions_path: str | Path, overrides_path: str | Path) -> Curation:
    return load_curation(suppressions_path=suppressions_path, work_overrides_path=overrides_path)


def _year_span(years: Iterable[int]) -> list[int]:
    values = list(years)
    return list(range(min(values), max(values) + 1)) if values else []


def _share(count: int, denominator: int) -> float | None:
    return round(count / denominator, 4) if denominator else None


def _by_year(counter: Mapping[int, int], years: Sequence[int], last_complete: int) -> list[dict]:
    return [{"year": y, "count": counter.get(y, 0), "partial": y > last_complete} for y in years]


def _ca_series(
    works: Sequence[CaWork], tags: Sequence[Mapping[str, Any]], last_complete: int
) -> dict[str, Any]:
    plastic = [w for w in works if w.plastic_related and w.year is not None]
    years = _year_span(w.year for w in plastic)  # type: ignore[misc]
    plastic_by_year = Counter(w.year for w in plastic)
    out_tags: list[dict[str, Any]] = []
    for spec in tags:
        tag = spec["tag"]
        counters: dict[str, Counter[int]] = {v: Counter() for v in SENSITIVITY_VARIANTS}
        for work in plastic:
            source = work.topic_sources.get(tag)
            if source is None:
                continue
            counters["all_sources"][work.year] += 1  # type: ignore[index]
            if source in {"owner", "model"}:
                counters["owner_model_only"][work.year] += 1  # type: ignore[index]
            if source == "rule":
                counters["rule_only"][work.year] += 1  # type: ignore[index]
        total = sum(counters["all_sources"].values())
        series = [
            {
                "year": y,
                "count": counters["all_sources"].get(y, 0),
                "share": _share(counters["all_sources"].get(y, 0), plastic_by_year.get(y, 0)),
                "partial": y > last_complete,
            }
            for y in years
        ]
        entry: dict[str, Any] = {
            **spec,
            "status": "labelled" if total else "no_labels_yet",
            "total": total,
            "by_year": series,
            "sensitivity": {
                variant: {
                    "total": sum(counters[variant].values()),
                    "by_year": _by_year(counters[variant], years, last_complete),
                }
                for variant in SENSITIVITY_VARIANTS
            },
        }
        if total == 0:
            entry["message"] = NO_LABELS_MESSAGE
        out_tags.append(entry)
    return {
        "plastic_related_by_year": _by_year(plastic_by_year, years, last_complete),
        "tags": out_tags,
    }


def _lens_block(
    works: Sequence[CaWork], lenses: Sequence[str], last_complete: int
) -> dict[str, Any]:
    plastic = [w for w in works if w.plastic_related and w.year is not None]
    present = sorted({lens for w in plastic for lens in w.lens_sources if lens in lenses})
    block: dict[str, Any] = {"framing_rule": FRAMING_RULE, "caption": LENS_CAPTION, "series": []}
    if not present:
        block.update({"status": "no_lens_labels_yet", "message": NO_LENS_MESSAGE})
        return block
    years = _year_span(w.year for w in plastic)  # type: ignore[misc]
    block["status"] = "labelled"
    for lens in present:
        counter = Counter(w.year for w in plastic if lens in w.lens_sources)
        block["series"].append(
            {
                "lens": lens,
                "total": sum(counter.values()),
                "by_year": _by_year(counter, years, last_complete),
            }
        )
    return block


def _topic_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (_text(row.get("primary_topic_id")), _text(row.get("primary_topic_name")))


def _global_series(rows: Sequence[Mapping[str, Any]], last_complete: int) -> dict[str, Any]:
    dated = [r for r in rows if r.get("publication_year") is not None]
    years = _year_span(int(r["publication_year"]) for r in dated)
    totals = Counter(int(r["publication_year"]) for r in dated)
    named = [r for r in dated if _topic_key(r) != ("", "")]
    complete_counts = Counter(
        _topic_key(r) for r in named if int(r["publication_year"]) <= last_complete
    )
    ranking = sorted(complete_counts, key=lambda k: (-complete_counts[k], k[1], k[0]))[:TOP_N]
    per_topic: dict[tuple[str, str], Counter[int]] = {key: Counter() for key in ranking}
    for row in named:
        key = _topic_key(row)
        if key in per_topic:
            per_topic[key][int(row["publication_year"])] += 1
    topics = [
        {
            "rank": rank,
            "primary_topic_id": key[0],
            "topic": key[1],
            "total_complete_years": complete_counts[key],
            "by_year": _by_year(per_topic[key], years, last_complete),
        }
        for rank, key in enumerate(ranking, start=1)
    ]
    other = Counter(totals)
    for key in ranking:
        other.subtract(per_topic[key])
    return {
        "scope": "global",
        "screening": "unscreened query hits",
        "basis": "OpenAlex primary_topic",
        "caveat": GLOBAL_CAVEAT,
        "top_n": TOP_N,
        "ranking_basis": "count over complete years, ties by topic name then ID",
        "total_by_year": _by_year(totals, years, last_complete),
        "topics": topics,
        OTHER_LABEL: {
            "label": OTHER_LABEL,
            "no_primary_topic_total": sum(1 for r in dated if _topic_key(r) == ("", "")),
            "by_year": _by_year(
                Counter({y: v for y, v in other.items() if v}), years, last_complete
            ),
        },
    }


def check_global_sums(global_block: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` unless top topics plus other equal the total in every year."""

    totals = {row["year"]: row["count"] for row in global_block["total_by_year"]}
    for year, total in totals.items():
        part = sum(
            next(r["count"] for r in topic["by_year"] if r["year"] == year)
            for topic in global_block["topics"]
        )
        part += next(r["count"] for r in global_block[OTHER_LABEL]["by_year"] if r["year"] == year)
        if part != total:
            raise ValueError(f"global series do not sum to the total in {year}: {part} != {total}")


def build_series(
    *,
    works: Sequence[CaWork],
    removed: int,
    global_rows: Sequence[Mapping[str, Any]],
    taxonomy: Mapping[str, Any],
    as_of: Any,
    snapshot: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the bq4-series-v1 payload from frozen CA works and the global rows."""

    last_complete = int(as_of.year) - 1
    tags, excluded = reported_tags(taxonomy)
    global_block = _global_series(global_rows, last_complete)
    check_global_sums(global_block)
    ca_block = _ca_series(works, tags, last_complete)
    ca_block.update(
        {
            "scope": "ca",
            "works": len(works),
            "plastic_related_works": sum(1 for w in works if w.plastic_related),
            "undated_works": sum(1 for w in works if w.year is None),
            "removed_works": removed,
            "tags_excluded": excluded,
        }
    )
    return {
        "schema": SCHEMA,
        "as_of": as_of.isoformat(),
        "last_complete_year": last_complete,
        "labels_snapshot": dict(snapshot),
        "inputs": dict(inputs),
        "ca": ca_block,
        "global": global_block,
        "lens": _lens_block(works, lens_values(taxonomy), last_complete),
    }
