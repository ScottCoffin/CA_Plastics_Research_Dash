"""Tier B country aggregates from the global partition (PLAT-4b slice 3, data only).

Reads the ignored ``works.parquet`` and ``work_regions.parquet`` written by
``atlas.ingest.global_partition`` and builds ``site/data/global/countries.json``: one entry per
ISO alpha-2 country with at least one work, and one entry per registry region that matched a
work. Every count is an unscreened query hit: the global works were not relevance-screened.

Tier ``B`` is a country with at least ``TIER_B_MIN_WORKS`` works; the rest are tier ``C``. A
work counts toward every country it touches, so country totals can sum to more than the corpus.
Output carries aggregates only: no author names, author ids or per-person rows, no abstracts.

Offline and deterministic: the same inputs and ``generated_at`` give a byte-identical file.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.ingest.global_partition import SCREENING_UNSCREENED

SCHEMA_VERSION = "plat4b-v1"
TIER_B_MIN_WORKS = 50
FIRST_YEAR = 1970
TOP_TOPICS = 10
REGION_MATCHED_BY = "region_predicate"
SOURCE = (
    "Local partition of the PLAT-4a global OpenAlex pages (works.parquet and work_regions.parquet, "
    "from scripts/partition_global.py). Country rows come from institution and author country "
    "codes; registry region rows come from the region predicate in regions/_registry.yml."
)
IS_TEXT = (
    "Counts of unscreened query hits: OpenAlex works that match the active plastics query, "
    "grouped by the countries of their authors' institutions (and author country codes), by "
    "publication year, PubMed id presence, retraction flag and primary topic."
)
IS_NOT_TEXT = (
    "Not a relevance-screened count and not a share of world research. A work with authors in "
    "two countries is counted in both, and the registry region rows are matched by the region "
    "predicate, not the curated corpus of that region. Tier C counts are small and unstable."
)
REGION_NOTE = (
    "Each registry region block is matched by the region predicate (institution, raw affiliation "
    "or registry institution rules), not by the curated corpus of that region."
)
FORBIDDEN_KEY_PARTS = ("author", "person", "orcid", "abstract")


@dataclass(frozen=True)
class WorkFact:
    """The fields tier B needs from one works.parquet row."""

    year: int | None
    has_pmid: bool
    retracted: bool
    topic_id: str | None
    topic_name: str | None


@dataclass(frozen=True)
class WorksTable:
    facts: dict[str, WorkFact]
    query_version: str
    query_hash: str


def load_works(works_path: str | Path) -> WorksTable:
    """Facts per work id. Raises ValueError when the rows mix query identities."""
    table = pq.read_table(
        works_path,
        columns=[
            "work_id",
            "publication_year",
            "pmid",
            "is_retracted",
            "primary_topic_id",
            "primary_topic_name",
            "query_version",
            "query_hash",
        ],
    ).to_pylist()
    identities = {(row["query_version"], row["query_hash"]) for row in table}
    if len(identities) > 1:
        raise ValueError(f"works mix query identities: {sorted(identities)}")
    facts = {
        row["work_id"]: WorkFact(
            year=row["publication_year"],
            has_pmid=bool(row["pmid"]),
            retracted=bool(row["is_retracted"]),
            topic_id=row["primary_topic_id"],
            topic_name=row["primary_topic_name"],
        )
        for row in table
    }
    query_version, query_hash = next(iter(identities)) if identities else ("", "")
    return WorksTable(facts, query_version or "", query_hash or "")


def load_region_members(regions_path: str | Path) -> dict[tuple[str, str], list[str]]:
    """``{(region_kind, region_code): [work_id, ...]}`` for country and registry rows."""
    rows = pq.read_table(
        regions_path, columns=["work_id", "region_kind", "region_code"]
    ).to_pylist()
    members: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        if row["region_kind"] not in ("country", "registry_region"):
            continue
        members.setdefault((row["region_kind"], row["region_code"]), []).append(row["work_id"])
    return members


def load_country_names(explore_path: str | Path) -> dict[str, str]:
    """ISO code -> display name from ``explore.json``; empty when the file is absent."""
    path = Path(explore_path)
    if not path.is_file():
        return {}
    countries = json.loads(path.read_text(encoding="utf-8")).get("countries") or []
    return {str(c["iso"]): str(c["name"]) for c in countries if c.get("iso") and c.get("name")}


def tier_for(works_total: int) -> str:
    return "B" if works_total >= TIER_B_MIN_WORKS else "C"


def aggregate(
    work_ids: Iterable[str], facts: Mapping[str, WorkFact], last_year: int
) -> dict[str, Any]:
    """The count block for one group of works. ``last_year`` is the current (partial) year."""
    by_year: Counter[int] = Counter()
    outside = pmid = retracted = total = 0
    first_year: int | None = None
    topics: Counter[str] = Counter()
    topic_names: dict[str, str | None] = {}
    for work_id in work_ids:
        fact = facts[work_id]
        total += 1
        if fact.year is not None:
            first_year = fact.year if first_year is None else min(first_year, fact.year)
        if fact.year is None or not FIRST_YEAR <= fact.year <= last_year:
            outside += 1
        else:
            by_year[fact.year] += 1
        pmid += fact.has_pmid
        retracted += fact.retracted
        if fact.topic_id:
            topics[fact.topic_id] += 1
            topic_names.setdefault(fact.topic_id, fact.topic_name)
    year_rows: list[dict[str, Any]] = [
        {"year": year, "count": by_year.get(year, 0)} for year in range(FIRST_YEAR, last_year)
    ]
    year_rows.append({"year": last_year, "count": by_year.get(last_year, 0), "partial": True})
    ranked = sorted(topics.items(), key=lambda item: (-item[1], item[0]))[:TOP_TOPICS]
    return {
        "tier": tier_for(total),
        "screening_status": SCREENING_UNSCREENED,
        "works_total": total,
        "works_by_year": year_rows,
        "works_outside_years": outside,
        "works_with_pmid": pmid,
        "first_year": first_year,
        "top_primary_topics": [
            {"id": topic_id, "name": topic_names[topic_id], "count": count}
            for topic_id, count in ranked
        ],
    }


# 2026-11-25 lead check: a count with is_retracted:true returns 65 works for this query, but
# none of them is in the cursor-paged pages (per-year totals still match). Retractions are absent
# from the global store, so no retraction count is published (it would read as a false zero).
RETRACTIONS_NOTE = (
    "Not counted. Retracted works are not in this data set: the source's list results leave "
    "them out, so a retraction share here would read as a false zero."
)


def build(
    works_path: str | Path,
    regions_path: str | Path,
    *,
    generated_at: datetime,
    names: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The full countries.json payload. ``generated_at`` (UTC) sets the current partial year."""
    table = load_works(works_path)
    members = load_region_members(regions_path)
    names = names or {}
    last_year = generated_at.year
    countries: list[dict[str, Any]] = []
    registry: list[dict[str, Any]] = []
    for (kind, code), work_ids in sorted(members.items()):
        missing = [wid for wid in work_ids if wid not in table.facts]
        if missing:
            raise ValueError(
                f"region rows point at {len(missing)} works missing from works.parquet"
            )
        block = aggregate(work_ids, table.facts, last_year)
        if kind == "country":
            countries.append({"iso": code, "name": names.get(code, code), **block})
        else:
            registry.append({"region": code, "matched_by": REGION_MATCHED_BY, **block})
    tiers = Counter(entry["tier"] for entry in countries)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query_version": table.query_version,
        "query_hash": table.query_hash,
        "source": SOURCE,
        "screening_status": SCREENING_UNSCREENED,
        "what_this_is_and_is_not": {"is": IS_TEXT, "is_not": IS_NOT_TEXT},
        "retractions": RETRACTIONS_NOTE,
        "tier_rule": {
            "tier_b_min_works": TIER_B_MIN_WORKS,
            "tier_c": f"Fewer than {TIER_B_MIN_WORKS} works.",
        },
        "years": {
            "first": FIRST_YEAR,
            "last_complete": last_year - 1,
            "partial": last_year,
        },
        "tier_counts": {"B": tiers.get("B", 0), "C": tiers.get("C", 0)},
        "countries": countries,
        "registry_regions_note": REGION_NOTE,
        "registry_regions": registry,
    }


def encode(payload: Mapping[str, Any]) -> str:
    """Compact JSON with one country or region per line, LF, trailing newline."""
    lines = ["{"]
    keys = list(payload)
    for index, key in enumerate(keys):
        comma = "," if index < len(keys) - 1 else ""
        value = payload[key]
        if isinstance(value, list):
            lines.append(f"{json.dumps(key)}: [")
            for pos, item in enumerate(value):
                tail = "," if pos < len(value) - 1 else ""
                lines.append(_compact(item) + tail)
            lines.append("]" + comma)
        else:
            lines.append(f"{json.dumps(key)}: {_compact(value)}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def validate(payload: Mapping[str, Any]) -> list[str]:
    """Schema, labels, tier rule, totals and privacy problems in a payload (empty = pass)."""
    problems: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version is not {SCHEMA_VERSION}")
    if payload.get("screening_status") != SCREENING_UNSCREENED:
        problems.append("top-level screening_status is not unscreened_query_hit")
    years = payload.get("years") or {}
    first, last = years.get("first"), years.get("last_complete")
    blocks = list(payload.get("countries") or []) + list(payload.get("registry_regions") or [])
    for entry in blocks:
        label = entry.get("iso") or entry.get("region")
        if entry.get("screening_status") != SCREENING_UNSCREENED:
            problems.append(f"{label}: block is not labelled unscreened_query_hit")
        if entry.get("tier") != tier_for(entry.get("works_total", 0)):
            problems.append(f"{label}: tier does not follow the works threshold")
        by_year = entry.get("works_by_year") or []
        summed = sum(row["count"] for row in by_year) + entry.get("works_outside_years", 0)
        if summed != entry.get("works_total"):
            problems.append(f"{label}: year counts do not add up to works_total")
        if by_year and (by_year[0]["year"] != first or by_year[-2]["year"] != last):
            problems.append(f"{label}: year range differs from the years block")
        if by_year and not by_year[-1].get("partial"):
            problems.append(f"{label}: current year is not flagged partial")
    problems.extend(_forbidden_keys(payload))
    return problems


def _forbidden_keys(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if any(part in str(key).lower() for part in FORBIDDEN_KEY_PARTS):
                found.append(f"{path}.{key}: person-level key")
            found.extend(_forbidden_keys(item, f"{path}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, str):
        for index, item in enumerate(value):
            found.extend(_forbidden_keys(item, f"{path}[{index}]"))
    return found


def parse_generated_at(payload: Mapping[str, Any]) -> datetime:
    return datetime.strptime(str(payload["generated_at"]), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
