"""Deterministic provisional labels for normalized OpenAlex works.

S2.3 is intentionally a rule-based candidate layer.  It uses the repository's
owner-supplied query and taxonomy files, while retaining the raw OpenAlex topic
names needed to interpret the normalized topic IDs.  The candidate is not a
validated classifier and is never promoted by this module.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from atlas.ingest.abstract_qc import misattached_abstract_ids
from atlas.ingest.normalize import compact_id

WORK_LABELS_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("plastic_related", pa.bool_()),
        ("plastic_score", pa.int64()),
        ("plastic_tier", pa.string()),
        ("ca_sampled", pa.string()),
        ("ca_setting", pa.list_(pa.string())),
        ("study_type", pa.string()),
        ("domain_tags", pa.list_(pa.string())),
        ("facet_tags", pa.list_(pa.string())),
        ("evidence_level", pa.string()),
        ("evidence_snippets", pa.list_(pa.string())),
        ("model_version", pa.string()),
        ("label_source", pa.string()),
        ("confidence", pa.float64()),
        ("needs_review", pa.bool_()),
        ("topic_ids", pa.list_(pa.string())),
        ("openalex_topic_names", pa.list_(pa.string())),
        ("primary_topic_name", pa.string()),
        ("rule_hits", pa.list_(pa.string())),
    ]
)

MODEL_VERSION = "plastic-v3.1-rule-v1"

# These are intentionally small, transparent matrix facets.  They are an
# independent local implementation of the documented regex-facet approach;
# no Trendspotter code is copied into this repository.
FACET_SEEDS: dict[str, tuple[str, ...]] = {
    "matrix:marine": ("marine", "ocean", "estuary", "estuaries", "coastal", "beach", "bight"),
    "matrix:freshwater": ("freshwater", "river", "lake", "stream", "stormwater"),
    "matrix:soil_and_agriculture": ("soil", "agriculture", "crop", "plant", "terrestrial"),
    "matrix:wastewater": ("wastewater", "sewage", "effluent", "treatment plant"),
    "matrix:air": ("airborne", "atmosphere", "aerosol", "deposition", "inhalation"),
    "matrix:food_and_drink": ("food", "drink", "dietary", "beverage"),
}


@dataclass(frozen=True)
class LabelingResult:
    """Output paths and auditable coverage metrics for one labeling run."""

    output_path: Path
    qc_path: Path
    metrics: dict[str, int]


@dataclass(frozen=True)
class PlasticDecision:
    related: bool
    score: int
    tier: str
    hits: tuple[str, ...]


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(_text(term)).replace(r"\ ", r"\s+")
    plural = r"s?" if _text(term) and _text(term)[-1].casefold() not in {"s", "x", "z"} else ""
    return re.compile(rf"(?<!\w){escaped}{plural}(?!\w)", re.IGNORECASE)


def _matches(text: str, term: str) -> bool:
    return bool(_term_pattern(term).search(text))


def _load_yaml(path: str | Path) -> Mapping[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def _ordered_terms(config: Mapping[str, Any], key: str) -> list[str]:
    values = config.get(key) or []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{key} must be a YAML list")
    return [_text(value) for value in values if _text(value)]


def _qualified_terms(config: Mapping[str, Any]) -> list[tuple[str, list[str]]]:
    values = config.get("qualified_terms") or []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError("qualified_terms must be a YAML list")
    result: list[tuple[str, list[str]]] = []
    for value in values:
        if not isinstance(value, Mapping):
            raise ValueError("qualified_terms entries must be mappings")
        term = _text(value.get("term"))
        contexts = value.get("any_context") or []
        if not term or not isinstance(contexts, Sequence) or isinstance(contexts, (str, bytes)):
            raise ValueError("qualified term entries require term and any_context")
        result.append((term, [_text(context) for context in contexts if _text(context)]))
    return result


def classify_plastic_text(text: str, query_config: Mapping[str, Any]) -> PlasticDecision:
    """Apply ordered candidate rules; exclusions always override inclusions."""

    normalized = _text(text)
    exclusions = _ordered_terms(query_config, "exclusions")
    for term in exclusions:
        if _matches(normalized, term):
            return PlasticDecision(False, 0, "", (f"exclude:{term}",))

    core_hits: list[str] = []
    for term in _ordered_terms(query_config, "core_terms"):
        if _matches(normalized, term):
            core_hits.append(f"core:{term}")
    for term, contexts in _qualified_terms(query_config):
        if _matches(normalized, term) and any(
            _matches(normalized, context) for context in contexts
        ):
            core_hits.append(f"qualified:{term}")
    tier_hits = [
        f"tier_2:{term}"
        for term in _ordered_terms(query_config, "tier_2_terms")
        if _matches(normalized, term)
    ]
    hits = tuple(core_hits + tier_hits)
    if core_hits:
        return PlasticDecision(True, len(hits), "core", hits)
    if tier_hits:
        return PlasticDecision(True, len(tier_hits), "chemicals-in-plastics", tuple(tier_hits))
    return PlasticDecision(False, 0, "", ())


def always_relevant(text: str, query_config: Mapping[str, Any]) -> bool:
    """True when ``text`` matches an owner ``always_relevant_patterns`` regex."""

    patterns = query_config.get("always_relevant_patterns") or []
    if isinstance(patterns, (str, bytes)):
        raise ValueError("always_relevant_patterns must be a YAML list")
    return any(re.search(str(p), text or "", re.IGNORECASE) for p in patterns if p)


def _taxonomy_tags(
    text: str,
    topic_names: Sequence[str],
    taxonomy: Mapping[str, Any],
    *,
    title: str | None = None,
) -> tuple[list[str], list[str]]:
    """Domain tags and matrix facets for one record.

    ``seed_concepts`` match the text plus OpenAlex topic names. Optional
    ``title_seed_concepts`` match only ``title`` (when given; else the whole text), for
    words that are on-topic in a title but usually passing mentions in an abstract.
    Optional ``exclude_concepts`` (matched on the text) veto the tag.
    """
    searchable = " ".join([text, *topic_names])
    title_text = text if title is None else title
    domain_tags: list[str] = []
    configured = taxonomy.get("domain_tags") or []
    if not isinstance(configured, Sequence) or isinstance(configured, (str, bytes)):
        raise ValueError("taxonomy domain_tags must be a YAML list")
    for entry in configured:
        if not isinstance(entry, Mapping):
            raise ValueError("taxonomy domain_tags entries must be mappings")
        tag_id = _text(entry.get("id"))
        seeds = entry.get("seed_concepts") or []
        if not tag_id or not isinstance(seeds, Sequence) or isinstance(seeds, (str, bytes)):
            continue
        title_seeds = entry.get("title_seed_concepts") or []
        excludes = entry.get("exclude_concepts") or []
        if isinstance(title_seeds, (str, bytes)) or isinstance(excludes, (str, bytes)):
            raise ValueError(f"taxonomy lists for {tag_id} must be YAML lists")
        if any(_matches(text, _text(term)) for term in excludes if _text(term)):
            continue
        if any(_matches(searchable, _text(seed)) for seed in seeds if _text(seed)) or any(
            _matches(title_text, _text(seed)) for seed in title_seeds if _text(seed)
        ):
            domain_tags.append(tag_id)

    facets = [
        facet
        for facet, seeds in FACET_SEEDS.items()
        if any(_matches(searchable, seed) for seed in seeds)
    ]
    return domain_tags, facets


def _raw_topic_info(raw: Mapping[str, Any]) -> tuple[dict[str, str], str]:
    topics = raw.get("topics") or []
    topic_names: dict[str, str] = {}
    if isinstance(topics, Sequence) and not isinstance(topics, (str, bytes)):
        for topic in topics:
            if not isinstance(topic, Mapping):
                continue
            topic_id = compact_id(topic.get("id"))
            display_name = _text(topic.get("display_name"))
            if topic_id and display_name:
                topic_names[topic_id] = display_name
    primary = raw.get("primary_topic")
    primary_name = _text(primary.get("display_name")) if isinstance(primary, Mapping) else ""
    return topic_names, primary_name


def _atomic_write_table(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".parquet", prefix=f".{path.stem}-", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        pq.write_table(
            pa.Table.from_pylist(list(rows), schema=WORK_LABELS_SCHEMA),
            temporary,
            compression="zstd",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _qc_markdown(metrics: Mapping[str, int], *, source: str, generated_at: str) -> str:
    rows = [
        ("Normalized work rows", metrics["normalized_work_rows"]),
        ("Label rows", metrics["label_rows"]),
        ("Raw OpenAlex work rows", metrics["raw_work_rows"]),
        ("Missing raw work rows", metrics["missing_raw_work_rows"]),
        ("Normalized topic ID rows", metrics["topic_id_rows"]),
        ("Matched raw topic-name rows", metrics["matched_topic_rows"]),
        ("Missing raw topic-name rows", metrics["missing_topic_rows"]),
        ("Missing primary-topic names", metrics["missing_primary_topic_rows"]),
        ("Plastic-related rows", metrics["plastic_related_rows"]),
        ("Excluded rows", metrics["excluded_rows"]),
        ("Rows with provisional domain tags", metrics["domain_tagged_rows"]),
        ("Mis-attached (ignored) abstracts", metrics.get("misattached_abstract_rows", 0)),
        ("Always-relevant rule rows", metrics.get("always_relevant_rows", 0)),
    ]
    lines = [
        "# Provisional work-label QC",
        "",
        f"Generated at (UTC): `{generated_at}`",
        f"Source: `{source}`",
        "",
        "This is an owner-supplied candidate rule layer, not a validated classifier. "
        "`label_source=rule`, `confidence` is nullable and uncalibrated, and the "
        "candidate remains unpromoted.",
        "",
        "| Check | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {label} | {value} |" for label, value in rows)
    lines.extend(
        [
            "",
            "Topic display names are joined from raw OpenAlex records by `work_id`; "
            "missing raw rows and missing topic entries are retained and counted.",
            "",
        ]
    )
    return "\n".join(lines)


def label_records(
    normalized_works: Iterable[Mapping[str, Any]],
    raw_records: Iterable[Mapping[str, Any]],
    *,
    query_config_path: str | Path = "config/queries.yml",
    taxonomy_path: str | Path = "config/taxonomy.yml",
    output_path: str | Path,
    qc_path: str | Path,
    source: str,
    generated_at: str = "",
) -> LabelingResult:
    """Label normalized works while retaining every normalized work row."""

    query_config = _load_yaml(query_config_path)
    taxonomy = _load_yaml(taxonomy_path)
    raw_by_id = {
        compact_id(record.get("id") or record.get("openalex_id")): record
        for record in raw_records
        if compact_id(record.get("id") or record.get("openalex_id"))
    }
    normalized_by_id = {
        compact_id(row.get("work_id")): row
        for row in normalized_works
        if compact_id(row.get("work_id"))
    }
    rows: list[dict[str, Any]] = []
    # Abstracts OpenAlex attached to unrelated works are ignored (normally blanked
    # already by normalization; repeated here for older normalized tables).
    shared = misattached_abstract_ids(normalized_by_id.values())
    topic_id_rows = matched_topic_rows = missing_topic_rows = missing_primary_topic_rows = 0
    missing_raw_work_rows = plastic_related_rows = excluded_rows = domain_tagged_rows = 0
    always_relevant_rows = 0
    for work_id in sorted(normalized_by_id):
        work = normalized_by_id[work_id]
        raw = raw_by_id.get(work_id)
        missing_raw = raw is None
        if missing_raw:
            missing_raw_work_rows += 1
            raw = {}
        raw_topic_names, raw_primary_name = _raw_topic_info(raw)
        topic_ids = [
            compact_id(value) for value in (work.get("openalex_topics") or []) if compact_id(value)
        ]
        topic_names = [
            raw_topic_names[topic_id] for topic_id in topic_ids if topic_id in raw_topic_names
        ]
        topic_id_rows += len(topic_ids)
        matched_topic_rows += len(topic_names)
        missing_topic_count = len(topic_ids) - len(topic_names)
        missing_topic_rows += missing_topic_count
        primary_topic = compact_id(work.get("primary_topic"))
        primary_topic_name = raw_primary_name if primary_topic and raw_primary_name else ""
        if primary_topic and not primary_topic_name:
            missing_primary_topic_rows += 1
        title = _text(work.get("title"))
        abstract = "" if work_id in shared else _text(work.get("abstract"))
        text = " ".join(value for value in (title, abstract) if value)
        decision = classify_plastic_text(text, query_config)
        if not decision.related and always_relevant(text, query_config):
            # Owner rule: micro-nano plastics (any spelling) is always plastic-related.
            decision = PlasticDecision(True, 1, "always", ("always:micro-nano plastics",))
            always_relevant_rows += 1
        if decision.related:
            plastic_related_rows += 1
        if decision.hits and decision.hits[0].startswith("exclude:"):
            excluded_rows += 1
        domain_tags, facet_tags = _taxonomy_tags(
            text, [*topic_names, raw_primary_name], taxonomy, title=title
        )
        if domain_tags:
            domain_tagged_rows += 1
        needs_review = (
            missing_raw
            or bool(missing_topic_count)
            or bool(primary_topic and not primary_topic_name)
        )
        rows.append(
            {
                "work_id": work_id,
                "plastic_related": decision.related,
                "plastic_score": decision.score,
                "plastic_tier": decision.tier,
                "ca_sampled": "unclear",
                "ca_setting": [],
                "study_type": _text(work.get("type")),
                "domain_tags": domain_tags,
                "facet_tags": facet_tags,
                "evidence_level": "abstract" if abstract else None,
                "evidence_snippets": [],
                "model_version": MODEL_VERSION,
                "label_source": "rule",
                "confidence": None,
                "needs_review": needs_review,
                "topic_ids": topic_ids,
                "openalex_topic_names": topic_names,
                "primary_topic_name": primary_topic_name,
                "rule_hits": list(decision.hits),
            }
        )
    metrics = {
        "normalized_work_rows": len(normalized_by_id),
        "label_rows": len(rows),
        "raw_work_rows": len(raw_by_id),
        "missing_raw_work_rows": missing_raw_work_rows,
        "topic_id_rows": topic_id_rows,
        "matched_topic_rows": matched_topic_rows,
        "missing_topic_rows": missing_topic_rows,
        "missing_primary_topic_rows": missing_primary_topic_rows,
        "plastic_related_rows": plastic_related_rows,
        "excluded_rows": excluded_rows,
        "domain_tagged_rows": domain_tagged_rows,
        "misattached_abstract_rows": len(shared),
        "always_relevant_rows": always_relevant_rows,
    }
    if metrics["label_rows"] != metrics["normalized_work_rows"]:
        raise AssertionError("label output must retain one row per normalized work")
    _atomic_write_table(Path(output_path), rows)
    qc_file = Path(qc_path)
    qc_file.parent.mkdir(parents=True, exist_ok=True)
    qc_file.write_text(
        _qc_markdown(metrics, source=source, generated_at=generated_at or "runtime"),
        encoding="utf-8",
    )
    return LabelingResult(Path(output_path), qc_file, metrics)


def read_raw_parquet(path: str | Path) -> list[dict[str, Any]]:
    """Read raw OpenAlex JSON rows from S2.1's Parquet table."""

    rows = pq.read_table(path, columns=["openalex_id", "raw_json"]).to_pylist()
    result = []
    for row in rows:
        payload = json.loads(_text(row.get("raw_json")))
        if isinstance(payload, Mapping):
            result.append(dict(payload))
    return result


def read_normalized_works(path: str | Path) -> list[dict[str, Any]]:
    """Read the normalized C3 works table."""

    return pq.read_table(path).to_pylist()
