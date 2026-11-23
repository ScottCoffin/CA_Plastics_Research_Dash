"""Global-denominator series by publication year (BQ-2.1; A3 section 7 Module 2).

Series are declared in ``config/denominator_series.yml``. This module counts the available ones
from stored inputs and never calls the network:

- A: ``site/data/trend_global.json`` (the EM-7 global denominator).
- C: California-connected records that the OpenAlex query matched (``works.parquet`` joined to the
  raw works table for the run-id route).
- D: published works with ``plastic_related`` true (``site/data/index.json``); shown beside, never
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
from datetime import date
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path("config/denominator_series.yml")
OUTPUT_SCHEMA = "denominator_series.v1"
TREND_SCHEMA = "em7.v1"
STATUSES = ("available", "pending_fetch", "waits_for")
SCOPES = ("global", "california")
COMPUTE_KINDS = ("trend_global", "corpus_query_route", "published_plastic_related")
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
    by_year = payload.get("by_year")
    if not isinstance(by_year, Mapping):
        raise ValueError("trend_global.json has no by_year object")
    rows = []
    for key, value in sorted(by_year.items(), key=lambda item: _year(item[0])):
        rows.append(_year_row(_year(key), int(value), None, as_of))
    return rows


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
    trend_global: Mapping[str, Any] | None,
    corpus_records: Iterable[Mapping[str, Any]] | None = None,
    published_works: Iterable[Mapping[str, Any]] | None = None,
    as_of: date,
    expected_query_version: str | None = None,
) -> dict[str, Any]:
    """Count every available series and describe the pending ones. No I/O.

    Raises ValueError on a unit-mismatched ratio, a missing input for an available series, or a
    trend file for another query version. Input fingerprints are added by the caller.
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
            "comparable_with": list(spec.comparable_with),
            "beside_only": spec.beside_only,
            "retractions": entry["retractions"],
            "undated": entry["undated"],
            **({"route_records": entry["route_records"]} if "route_records" in entry else {}),
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
