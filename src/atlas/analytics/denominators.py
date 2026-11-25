"""Global-denominator series by publication year (BQ-2.1, BQ-2.2; A3 section 7 Module 2).

Series are declared in ``config/denominator_series.yml``. This module counts the available ones
from stored inputs and never calls the network:

- A (all types) and A-article_review, B and B-article_review: OpenAlex by-year counts fetched by
  ``scripts/fetch_denominator_series.py`` and read from its 30-day cache
  (``data/interim/denominator_series_cache.json``). The cache entry must match the active query
  version and filter digest; a missing or other-version entry raises.
- C: California-connected records that the OpenAlex query matched (``works.parquet`` joined to the
  raw works table for the run-id route).
- D: published works with ``plastic_related`` true (the region's ``index.json``); shown
  beside, never
  divided.

Ratios are allowed only between series that list each other in ``comparable_with`` and share the
same ``counting_unit`` text. A mismatch raises. Pending series are listed with their status and are
not counted. Partial years (the as-of year and later) are flagged, not dropped.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from atlas.query import openalex_filter, type_filters

DEFAULT_CONFIG = Path("config/denominator_series.yml")
OUTPUT_SCHEMA = "denominator_series.v1"
TREND_SCHEMA = "em7.v1"
CACHE_SCHEMA = "denominator_series_cache.v1"
CACHE_MAX_AGE = timedelta(days=30)
STATUSES = ("available", "pending_fetch", "waits_for")
SCOPES = ("global", "california")
COMPUTE_KINDS = (
    "trend_global",
    "corpus_query_route",
    "published_plastic_related",
    "denominator_cache",
)
SENSITIVITIES = ("all", "article_review")
# Type clause of the article+review sensitivity series. Repeated type keys are ANDed, so it sits
# beside the exclude_types clauses.
ARTICLE_REVIEW_FILTER = "type:article|review"
# Pollution-core v0 term set (A3 section 5.3) that series B reads. The path is absolute, so the
# fetcher and the builder agree whatever the working directory.
POLLUTION_CORE_PATH = Path(__file__).resolve().parents[3] / "config" / "pollution_core_v0.yml"
# Series fetched by scripts/fetch_denominator_series.py: id -> (term set, type sensitivity).
# "query" is the active plastics query. "core" is the pollution-core v0 terms alone, with the
# query's exclusions and no qualified terms.
FETCH_SERIES: dict[str, tuple[str, str]] = {
    "A-all": ("query", "all"),
    "A-article_review": ("query", "article_review"),
    "B-all": ("core", "all"),
    "B-article_review": ("core", "article_review"),
}
REQUIRED_KEYS = (
    "id",
    "label",
    "counting_unit",
    "source",
    "scope",
    "status",
    "comparable_with",
    "beside_only",
    "note",
)
# Run-id families whose records the OpenAlex query (title/abstract search and type filters) matched:
# the query ingest, the Europe PMC audit (search AND DOI) and the eScholarship audit (location AND
# query). The ORCID and ROR DOI routes use a local text rule instead, so they are not query routes.
QUERY_ROUTES = frozenset({"openalex-works", "europepmc-audit", "escholarship-ingest"})
_ROUTE_CUT = re.compile(r"-\d")


@dataclass(frozen=True)
class SeriesSpec:
    id: str
    label: str
    counting_unit: str
    source: str
    scope: str
    status: str
    comparable_with: tuple[str, ...]
    beside_only: bool
    note: str
    waits_for: str | None = None
    compute: str | None = None
    sensitivity: str = "all"
    cache_series: str | None = None


def route_family(source_run_id: str) -> str:
    """``openalex-works-20261110T...`` -> ``openalex-works``; ``escholarship-ingest`` unchanged."""

    family = _ROUTE_CUT.split(source_run_id or "", maxsplit=1)[0]
    return family or "unknown"


def _text(entry: Mapping[str, Any], key: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"series {entry.get('id')!r}: {key} must be non-empty text")
    return value


def _spec_from_entry(entry: Any) -> SeriesSpec:
    if not isinstance(entry, Mapping):
        raise ValueError("each series entry must be a mapping")
    missing = [key for key in REQUIRED_KEYS if key not in entry]
    if missing:
        raise ValueError(f"series {entry.get('id')!r} is missing {', '.join(missing)}")
    series_id = _text(entry, "id")
    status = _text(entry, "status")
    scope = _text(entry, "scope")
    if status not in STATUSES:
        raise ValueError(f"{series_id}: unknown status {status!r}")
    if scope not in SCOPES:
        raise ValueError(f"{series_id}: unknown scope {scope!r}")
    waits_for = entry.get("waits_for") or None
    if status == "available" and waits_for:
        raise ValueError(f"{series_id}: an available series cannot wait for {waits_for}")
    if status != "available" and not waits_for:
        raise ValueError(f"{series_id}: status {status} needs a waits_for task")
    compute = entry.get("compute") or None
    if status == "available" and compute not in COMPUTE_KINDS:
        raise ValueError(f"{series_id}: unknown compute kind {compute!r}")
    cache_series = entry.get("cache_series") or None
    cache_known = isinstance(cache_series, str) and cache_series in FETCH_SERIES
    if compute == "denominator_cache" and not cache_known:
        raise ValueError(
            f"{series_id}: denominator_cache needs cache_series in {list(FETCH_SERIES)}"
        )
    sensitivity = entry.get("sensitivity", "all")
    if sensitivity not in SENSITIVITIES:
        raise ValueError(f"{series_id}: unknown sensitivity {sensitivity!r}")
    if cache_known and FETCH_SERIES[cache_series][1] != sensitivity:
        raise ValueError(f"{series_id}: sensitivity {sensitivity} does not match {cache_series}")
    comparable = entry["comparable_with"]
    if not isinstance(comparable, list) or not all(isinstance(item, str) for item in comparable):
        raise ValueError(f"{series_id}: comparable_with must be a list of series ids")
    beside_only = entry["beside_only"]
    if not isinstance(beside_only, bool):
        raise ValueError(f"{series_id}: beside_only must be true or false")
    return SeriesSpec(
        id=series_id,
        label=_text(entry, "label"),
        counting_unit=_text(entry, "counting_unit"),
        source=_text(entry, "source"),
        scope=scope,
        status=status,
        comparable_with=tuple(comparable),
        beside_only=beside_only,
        note=_text(entry, "note"),
        waits_for=str(waits_for) if waits_for else None,
        compute=str(compute) if compute else None,
        sensitivity=sensitivity,
        cache_series=cache_series if cache_known else None,
    )


def validate_ratio_pairs(specs: Mapping[str, SeriesSpec]) -> list[tuple[str, str]]:
    """Check every declared ratio pair; return the unordered pairs in config order.

    Raises ValueError for an unknown or self reference, a missing reciprocal entry, a beside-only
    series in a pair, or two series whose counting_unit text differs.
    """

    pairs: list[tuple[str, str]] = []
    seen: set[frozenset[str]] = set()
    for spec in specs.values():
        for other_id in spec.comparable_with:
            if other_id == spec.id:
                raise ValueError(f"{spec.id} cannot be compared with itself")
            if other_id not in specs:
                raise ValueError(f"{spec.id} lists unknown series {other_id}")
            other = specs[other_id]
            if spec.id not in other.comparable_with:
                raise ValueError(
                    f"{spec.id} lists {other_id}, but {other_id} does not list it back"
                )
            if spec.beside_only or other.beside_only:
                raise ValueError(
                    f"{spec.id}/{other_id}: beside_only series are shown beside a ratio, "
                    "never divided"
                )
            if spec.sensitivity != other.sensitivity:
                raise ValueError(
                    f"ratio {spec.id}/{other_id} crosses type sensitivity "
                    f"({spec.sensitivity} vs {other.sensitivity})"
                )
            if spec.counting_unit != other.counting_unit:
                raise ValueError(
                    f"ratio {spec.id}/{other_id} is not like-for-like: counting_unit differs "
                    f"({spec.counting_unit!r} vs {other.counting_unit!r})"
                )
            key = frozenset((spec.id, other_id))
            if key not in seen:
                seen.add(key)
                pairs.append((spec.id, other_id))
    return pairs


def load_series_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, SeriesSpec]:
    """Read and validate the series config; returns specs keyed by id in config order."""

    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entries = payload.get("series") if isinstance(payload, Mapping) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("denominator config needs a non-empty series list")
    specs: dict[str, SeriesSpec] = {}
    for entry in entries:
        spec = _spec_from_entry(entry)
        if spec.id in specs:
            raise ValueError(f"duplicate series id {spec.id}")
        specs[spec.id] = spec
    validate_ratio_pairs(specs)
    return specs


def _year(value: Any) -> int:
    try:
        return int(str(value))
    except ValueError as exc:
        raise ValueError(f"not a publication year: {value!r}") from exc


def _year_row(year: int, count: int, retracted: int | None, as_of: date, **extra: int) -> dict:
    """One output row. ``partial_year`` is true for the as-of year and any later year."""

    return {
        "year": year,
        "count": count,
        "retracted": retracted,
        "partial_year": year >= as_of.year,
        **extra,
    }


def _by_year_rows(by_year: Any, *, as_of: date, source: str) -> list[dict]:
    """Rows from a ``{year: count}`` object; no retraction split (group_by cannot split them)."""

    if not isinstance(by_year, Mapping):
        raise ValueError(f"{source} has no by_year object")
    rows = []
    for key, value in sorted(by_year.items(), key=lambda item: _year(item[0])):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{source}: count for {key} must be a non-negative integer")
        rows.append(_year_row(_year(key), value, None, as_of))
    return rows


def trend_rows(
    payload: Mapping[str, Any], *, as_of: date, expected_query_version: str | None = None
) -> list[dict]:
    """Rows for series A from a ``trend_global.json`` payload (no retraction split available)."""

    if payload.get("schema_version") != TREND_SCHEMA:
        raise ValueError(f"trend_global.json schema is {payload.get('schema_version')!r}")
    version = str(payload.get("query_version") or "")
    if expected_query_version is not None and version != expected_query_version:
        raise ValueError(
            f"trend_global.json is for query {version!r}; the active query is "
            f"{expected_query_version!r}. Rerun scripts/fetch_trend_global.py."
        )
    return _by_year_rows(payload.get("by_year"), as_of=as_of, source="trend_global.json")


def load_pollution_core(path: str | Path = POLLUTION_CORE_PATH) -> dict[str, Any]:
    """Read and check the pollution-core v0 term set (A3 section 5.3).

    ValueError on a missing or malformed list, an empty or duplicate core term, or a core term that
    is also an excluded lifecycle term. Whether every core term is a queries.yml term is checked
    where the query config is known (``fetch_series_filters``).
    """

    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a mapping")
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"{path}: version must be non-empty text")
    lists: dict[str, list[str]] = {}
    for key in ("core_terms", "excluded_lifecycle_terms", "qualified_not_included_v0"):
        value = payload.get(key)
        if not isinstance(value, list) or not all(
            isinstance(term, str) and term.strip() for term in value
        ):
            raise ValueError(f"{path}: {key} must be a list of non-empty text")
        lists[key] = value
    core = lists["core_terms"]
    if not core:
        raise ValueError(f"{path}: core_terms is empty")
    duplicates = sorted({term for term in core if core.count(term) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate core terms {duplicates}")
    overlap = sorted(set(core) & set(lists["excluded_lifecycle_terms"]))
    if overlap:
        raise ValueError(f"{path}: core terms are also excluded lifecycle terms: {overlap}")
    return {"version": version, "source": str(payload.get("source") or ""), **lists}


def fetch_series_filters(
    config: Mapping[str, Any],
    series_id: str,
    *,
    pollution_core: Mapping[str, Any] | None = None,
) -> list[str]:
    """OpenAlex filter clauses for one fetched series.

    ``A-all`` is the clause list ``scripts/fetch_trend_global.py`` sends. ``B`` uses only the
    pollution-core v0 terms (A3 section 5.3) with the query's exclusions and type filters, and no
    qualified terms, so B is inside A. No series has a language clause.
    """

    if series_id not in FETCH_SERIES:
        raise ValueError(f"unknown fetched series {series_id!r}")
    terms, sensitivity = FETCH_SERIES[series_id]
    if terms == "query":
        query = config
    else:
        core = pollution_core if pollution_core is not None else load_pollution_core()
        core_terms = list(core["core_terms"])
        unknown = [term for term in core_terms if term not in config["core_terms"]]
        if unknown:
            raise ValueError(f"pollution-core terms not in queries.yml core_terms: {unknown}")
        query = {**config, "core_terms": core_terms, "qualified_terms": []}
    filters = [openalex_filter(query), *type_filters(config)]
    if sensitivity == "article_review":
        filters.append(ARTICLE_REVIEW_FILTER)
    return filters


def filter_digest(filters: Sequence[str]) -> str:
    """Short SHA-256 of the joined filter clauses; any change to a term or a type changes it."""

    return hashlib.sha256(",".join(filters).encode("utf-8")).hexdigest()[:16]


def cache_key(series_id: str, query_version: str, digest: str) -> str:
    """Cache key: series id, query version and filter digest."""

    return f"{series_id}|{query_version}|{digest}"


def load_denominator_cache(path: str | Path) -> dict[str, Any]:
    """Read the denominator cache; ValueError when the file is not a cache of this schema."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != CACHE_SCHEMA:
        raise ValueError(f"{path} is not a denominator cache (schema {CACHE_SCHEMA})")
    if not isinstance(payload.get("entries"), dict):
        raise ValueError(f"{path} has no entries object")
    return payload


def resolve_cache_entries(
    specs: Mapping[str, SeriesSpec], cache: Mapping[str, Any], *, query_config: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    """The cache entry that each cache-backed series needs for the active query and filters.

    A missing entry (never fetched, fetched for another query version, or for other filters)
    raises. The builder never falls back to another entry.
    """

    version = str(query_config.get("version") or "")
    entries = cache["entries"]
    resolved: dict[str, dict[str, Any]] = {}
    for spec in specs.values():
        if spec.status != "available" or spec.compute != "denominator_cache":
            continue
        digest = filter_digest(fetch_series_filters(query_config, str(spec.cache_series)))
        entry = entries.get(cache_key(str(spec.cache_series), version, digest))
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"{spec.id}: the denominator cache has no {spec.cache_series} entry for query "
                f"{version}; run scripts/fetch_denominator_series.py"
            )
        resolved[spec.id] = dict(entry)
    return resolved


def cache_rows(entry: Mapping[str, Any], *, as_of: date) -> list[dict]:
    """Rows for a cache-backed series: counts only, since group_by has no retraction split."""

    return _by_year_rows(
        entry.get("by_year"), as_of=as_of, source=f"{entry.get('series_id')} cache entry"
    )


def cache_is_stale_by_age(fetched_at: object, *, as_of: date) -> bool:
    """True when the entry was fetched 30 or more days before the as-of date."""

    try:
        fetched = datetime.fromisoformat(str(fetched_at))
    except ValueError as exc:
        raise ValueError(f"cache entry has no valid fetched_at: {fetched_at!r}") from exc
    return as_of - fetched.date() >= CACHE_MAX_AGE


def corpus_rows(
    records: Iterable[Mapping[str, Any]], *, as_of: date
) -> tuple[list[dict], dict, int]:
    """Rows for series C from per-record dicts.

    Each record has ``route`` (source_run_id), ``year``, ``ca_any_author`` (of the corpus work the
    record belongs to) and ``is_retracted``. Only California-connected records count. Records on a
    query route make up ``count``; records on other routes (the ORCID and ROR DOI routes) are
    reported in ``other_route`` and not divided.
    Returns (rows, record counts by route family over all records, undated California records).
    """

    count: Counter[int] = Counter()
    retracted: Counter[int] = Counter()
    other: Counter[int] = Counter()
    routes: Counter[str] = Counter()
    undated = 0
    for record in records:
        family = route_family(str(record.get("route") or ""))
        routes[family] += 1
        if not record.get("ca_any_author"):
            continue
        if record.get("year") is None:
            undated += 1
            continue
        year = _year(record["year"])
        if family in QUERY_ROUTES:
            count[year] += 1
            retracted[year] += int(bool(record.get("is_retracted")))
        else:
            other[year] += 1
    rows = [
        _year_row(year, count[year], retracted[year], as_of, other_route=other[year])
        for year in sorted(set(count) | set(other))
    ]
    return rows, dict(sorted(routes.items())), undated


def published_rows(works: Iterable[Mapping[str, Any]], *, as_of: date) -> tuple[list[dict], int]:
    """Rows for series D: published works with ``plastic_related`` true, retractions separate."""

    count: Counter[int] = Counter()
    retracted: Counter[int] = Counter()
    undated = 0
    for work in works:
        if work.get("plastic_related") is not True:
            continue
        if work.get("year") is None:
            undated += 1
            continue
        year = _year(work["year"])
        count[year] += 1
        retracted[year] += int(bool(work.get("is_retracted")))
    rows = [_year_row(year, count[year], retracted[year], as_of) for year in sorted(count)]
    return rows, undated


def _fill_years(
    rows: Sequence[Mapping[str, Any]],
    years: Sequence[int],
    *,
    as_of: date,
    retracted_known: bool,
    extra_defaults: Mapping[str, int],
) -> list[dict]:
    """Zero-fill one series over the shared year range so rows line up across series."""

    by_year = {row["year"]: dict(row) for row in rows}
    filled = []
    for year in years:
        if year in by_year:
            filled.append(by_year[year])
            continue
        zero_retracted = 0 if retracted_known else None
        filled.append(_year_row(year, 0, zero_retracted, as_of, **dict(extra_defaults)))
    return filled


def build_series(
    specs: Mapping[str, SeriesSpec] | None = None,
    *,
    trend_global: Mapping[str, Any] | None = None,
    corpus_records: Iterable[Mapping[str, Any]] | None = None,
    published_works: Iterable[Mapping[str, Any]] | None = None,
    denominator_entries: Mapping[str, Mapping[str, Any]] | None = None,
    as_of: date,
    expected_query_version: str | None = None,
) -> dict[str, Any]:
    """Count every available series and describe the pending ones. No I/O.

    ``denominator_entries`` maps a cache-backed series id to its cache entry (see
    ``resolve_cache_entries``). Raises ValueError on a unit-mismatched ratio, a missing input for an
    available series, or an input for another query version. Input fingerprints are added by the
    caller.
    """

    series_specs = dict(specs) if specs is not None else load_series_config()
    pairs = validate_ratio_pairs(series_specs)

    computed: dict[str, dict[str, Any]] = {}
    not_computed: dict[str, dict[str, Any]] = {}
    query_version: str | None = expected_query_version
    for spec in series_specs.values():
        if spec.status != "available":
            not_computed[spec.id] = {
                "status": spec.status,
                "waits_for": spec.waits_for,
                "counting_unit": spec.counting_unit,
            }
            continue
        if spec.compute == "trend_global":
            if trend_global is None:
                raise ValueError(f"{spec.id}: trend_global input is missing")
            rows = trend_rows(
                trend_global, as_of=as_of, expected_query_version=expected_query_version
            )
            query_version = str(trend_global.get("query_version") or "") or query_version
            meta = {
                "rows": rows,
                "retracted_known": False,
                "retractions": (
                    "not separated: the OpenAlex group_by cannot exclude them; included in count"
                ),
                "extra_defaults": {},
                "undated": 0,
            }
        elif spec.compute == "corpus_query_route":
            if corpus_records is None:
                raise ValueError(f"{spec.id}: corpus records input is missing")
            rows, routes, undated = corpus_rows(corpus_records, as_of=as_of)
            meta = {
                "rows": rows,
                "retracted_known": True,
                "retractions": "separate column; included in count",
                "extra_defaults": {"other_route": 0},
                "undated": undated,
                "route_records": routes,
            }
        elif spec.compute == "denominator_cache":
            if denominator_entries is None or spec.id not in denominator_entries:
                raise ValueError(f"{spec.id}: denominator cache entry is missing")
            entry = denominator_entries[spec.id]
            version = str(entry.get("query_version") or "")
            if expected_query_version is not None and version != expected_query_version:
                raise ValueError(
                    f"{spec.id}: cache entry is for query {version!r}; the active query is "
                    f"{expected_query_version!r}. Rerun scripts/fetch_denominator_series.py."
                )
            query_version = version or query_version
            flagged = entry.get("stale") is True
            aged = cache_is_stale_by_age(entry.get("fetched_at"), as_of=as_of)
            if flagged:
                reason: str | None = str(entry.get("stale_reason") or "refresh refused")
            elif aged:
                reason = "fetched 30 or more days before the as-of date"
            else:
                reason = None
            meta = {
                "rows": cache_rows(entry, as_of=as_of),
                "retracted_known": False,
                "retractions": (
                    "not separated: the OpenAlex group_by cannot exclude them; included in count"
                ),
                "extra_defaults": {},
                "undated": 0,
                "cache": {
                    "query_version": version,
                    "filter_digest": str(entry.get("filter_digest") or ""),
                    "fetched_at": str(entry.get("fetched_at") or ""),
                    "stale": flagged or aged,
                    "stale_reason": reason,
                },
            }
        else:
            if published_works is None:
                raise ValueError(f"{spec.id}: published works input is missing")
            rows, undated = published_rows(published_works, as_of=as_of)
            meta = {
                "rows": rows,
                "retracted_known": True,
                "retractions": "separate column; included in count",
                "extra_defaults": {},
                "undated": undated,
            }
        computed[spec.id] = {"spec": spec, **meta}

    all_years = [row["year"] for entry in computed.values() for row in entry["rows"]]
    years = list(range(min(all_years), max(all_years) + 1)) if all_years else []
    series: dict[str, dict[str, Any]] = {}
    for series_id, entry in computed.items():
        spec = entry["spec"]
        series[series_id] = {
            "label": spec.label,
            "counting_unit": spec.counting_unit,
            "scope": spec.scope,
            "source": spec.source,
            "status": spec.status,
            "sensitivity": spec.sensitivity,
            "comparable_with": list(spec.comparable_with),
            "beside_only": spec.beside_only,
            "retractions": entry["retractions"],
            "undated": entry["undated"],
            **({"route_records": entry["route_records"]} if "route_records" in entry else {}),
            **({"cache": entry["cache"]} if "cache" in entry else {}),
            "years": _fill_years(
                entry["rows"],
                years,
                as_of=as_of,
                retracted_known=entry["retracted_known"],
                extra_defaults=entry["extra_defaults"],
            ),
        }
    ratio_pairs = [[a, b] for a, b in pairs if a in series and b in series]
    return {
        "schema_version": OUTPUT_SCHEMA,
        "as_of": as_of.isoformat(),
        "last_complete_year": as_of.year - 1,
        "query_version": query_version,
        "series": series,
        "not_computed": not_computed,
        "ratio_pairs": ratio_pairs,
    }


def load_trend_global(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def load_corpus_records(works_path: str | Path, raw_path: str | Path) -> list[dict[str, Any]]:
    """Per-record dicts for series C: one per raw OpenAlex record that is in the corpus.

    A raw record that is a kept corpus work takes that work's flags. A collapsed duplicate takes
    its own route and retraction flag from its raw JSON, and the CA flag of the kept work it was
    collapsed into. Raw records with no corpus work (for example removed by suppression) are
    skipped.
    """

    import pyarrow.parquet as pq

    works = pq.read_table(
        works_path, columns=["work_id", "ca_any_author", "is_retracted", "duplicate_work_ids"]
    ).to_pylist()
    kept: dict[str, dict[str, Any]] = {}
    duplicate_of: dict[str, str] = {}
    for row in works:
        kept[row["work_id"]] = row
        for duplicate in row["duplicate_work_ids"] or []:
            duplicate_of[duplicate] = row["work_id"]
    raw = pq.read_table(
        raw_path, columns=["openalex_id", "publication_year", "source_run_id", "raw_json"]
    ).to_pylist()
    records: list[dict[str, Any]] = []
    for row in raw:
        record_id = row["openalex_id"]
        if record_id in kept:
            work = kept[record_id]
            is_retracted = bool(work["is_retracted"])
            ca_any_author = bool(work["ca_any_author"])
        elif record_id in duplicate_of:
            work = kept[duplicate_of[record_id]]
            payload = json.loads(row["raw_json"] or "{}")
            is_retracted = bool(payload.get("is_retracted"))
            ca_any_author = bool(work["ca_any_author"])
        else:
            continue
        records.append(
            {
                "route": row["source_run_id"] or "",
                "year": row["publication_year"],
                "ca_any_author": ca_any_author,
                "is_retracted": is_retracted,
            }
        )
    return records


def load_published_works(index_path: str | Path, works_path: str | Path) -> list[dict[str, Any]]:
    """Published works from the site index, with ``is_retracted`` joined from the works table."""

    import pyarrow.parquet as pq

    payload = json.loads(Path(index_path).read_text(encoding="utf-8"))
    works = payload.get("works") if isinstance(payload, Mapping) else None
    if not isinstance(works, list):
        raise ValueError(f"{index_path} has no works list")
    retracted = {
        row["work_id"]: bool(row["is_retracted"])
        for row in pq.read_table(works_path, columns=["work_id", "is_retracted"]).to_pylist()
    }
    rows: list[dict[str, Any]] = []
    for work in works:
        work_id = work.get("work_id")
        if work_id not in retracted:
            raise ValueError(f"published work {work_id} is not in the normalized works table")
        rows.append(
            {
                "year": work.get("year"),
                "plastic_related": work.get("plastic_related"),
                "is_retracted": retracted[work_id],
            }
        )
    return rows


def input_fingerprint(path: str | Path) -> dict[str, str]:
    """Repo-relative path and SHA-256 of an input file, so a stale output is detectable."""

    data = Path(path).read_bytes()
    return {"path": Path(path).as_posix(), "sha256": hashlib.sha256(data).hexdigest()}


def render_payload(payload: Mapping[str, Any]) -> str:
    """Stable JSON text: indented, UTF-8, LF, trailing newline."""

    return json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
