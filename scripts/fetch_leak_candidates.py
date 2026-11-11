"""Fetch S4.2 leak-test candidates: plastics works with a California place name but no CA author.

One budget-guarded, cursor-paged OpenAlex pull of works matching the active plastics query
AND a California place-term filter. Works with any authorship institution in the CA registry
are dropped; the rest are scanned with the S1.4 gazetteer (title + abstract) and only works
with at least one hit are kept.

Outputs:
* ``data/interim/leak_candidates.parquet`` (ignored): every non-CA work pulled, with text,
  author IDs, gazetteer hit names.
* ``curation/leak_gazetteer_hits_v1.csv`` (committed): work_id, matched_names,
  query_version, fetched_at_utc for the works with at least one gazetteer hit.

The pull stops without fetching pages when the meta count exceeds ``--max-works``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import urllib.parse
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.geo.gazetteer import DEFAULT_DATABASE_PATH, lookup, normalize_name  # noqa: E402
from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    OpenAlexRateLimitError,
    _request_json,
    load_openalex_key,
)
from atlas.query import load_query_config, openalex_filter, type_filters  # noqa: E402
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger  # noqa: E402

PLACE_TERMS = (
    "California",
    '"San Francisco Bay"',
    '"Monterey Bay"',
    '"Santa Monica Bay"',
    '"Southern California Bight"',
    '"Sacramento River"',
    '"San Joaquin"',
    '"Lake Tahoe"',
    '"Los Angeles"',
    '"San Diego"',
    '"Channel Islands"',
    '"Salton Sea"',
)
SELECT = (
    "id,display_name,publication_year,type,open_access,primary_location,"
    "authorships,abstract_inverted_index,topics"
)
HIT_COLUMNS = ["work_id", "matched_names", "query_version", "fetched_at_utc"]
# State- and country-level matches are implied by the search terms and carry no signal.
# Spot/building (S) and vegetation (V) features are mostly generic words (mines, patches).
GENERIC_FEATURE_TYPES = {"A.ADM1", "A.PCLI"}
EXCLUDED_CLASSES = {"S", "V", "R"}
MIN_SINGLE_TOKEN_LEN = 5
# A single capitalised word counts only if it is a populated place of at least this size
# (Berkeley, Davis, Oakland); smaller single-word names are mostly ordinary words.
MIN_SINGLE_TOKEN_POPULATION = 50000
MAX_NGRAM = 4
_CAP_TOKEN = re.compile(r"[A-Z][\w'.-]*")
_WORD = re.compile(r"[\w'.-]+")


class Stop(Exception):
    """Budget, rate or size stop."""


def place_filter() -> str:
    return "title_and_abstract.search:(" + " OR ".join(PLACE_TERMS) + ")"


def works_url(config: dict, *, per_page: int, cursor: str = "*") -> str:
    filters = [openalex_filter(config), place_filter(), *type_filters(config)]
    params = {
        "filter": ",".join(filters),
        "per-page": per_page,
        "cursor": cursor,
        "select": SELECT,
    }
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def _short(value: object) -> str:
    return str(value or "").rsplit("/", 1)[-1]


def reconstruct_abstract(index: dict | None) -> str:
    if not index:
        return ""
    slots: dict[int, str] = {}
    for word, positions in index.items():
        for position in positions:
            slots[int(position)] = word
    return " ".join(slots[key] for key in sorted(slots))


def candidate_ngrams(text: str) -> set[str]:
    """Capitalised word windows (1..4 tokens) of the text, as raw strings."""
    words = _WORD.findall(text)
    found: set[str] = set()
    for start, word in enumerate(words):
        if not _CAP_TOKEN.fullmatch(word):
            continue
        for size in range(1, MAX_NGRAM + 1):
            window = words[start : start + size]
            if len(window) < size or not all(_CAP_TOKEN.fullmatch(w) for w in window):
                break
            gram = " ".join(w.strip(".-'") for w in window)
            if size == 1 and len(gram) < MIN_SINGLE_TOKEN_LEN:
                continue
            found.add(gram)
    return found


def load_known_names(database: Path = DEFAULT_DATABASE_PATH) -> set[str]:
    """Normalised GeoNames variants, used only to skip lookups that cannot match."""
    with sqlite3.connect(database) as connection:
        names = {row[0] for row in connection.execute("SELECT normalized_name FROM name_variant")}
    with (ROOT / "config" / "gazetteer_ca.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            for alias in (row["name"], *(row.get("alias") or "").split("|")):
                if alias:
                    names.add(normalize_name(alias))
    return names


def _population(geonames_id: int | None) -> int:
    if geonames_id is None:
        return 0
    with sqlite3.connect(DEFAULT_DATABASE_PATH) as connection:
        row = connection.execute(
            "SELECT population FROM feature WHERE geonames_id = ?", (geonames_id,)
        ).fetchone()
    return int(row[0] or 0) if row else 0


def is_place_hit(gram: str) -> bool:
    """Gazetteer lookup (blacklist respected) filtered to informative place matches."""
    usable = [
        m
        for m in lookup(gram)
        if m.feature_type not in GENERIC_FEATURE_TYPES
        and m.feature_type.split(".")[0] not in EXCLUDED_CLASSES
    ]
    if " " in gram.strip():
        return bool(usable)
    return any(
        m.feature_type.startswith("P.")
        and _population(m.geonames_id) >= MIN_SINGLE_TOKEN_POPULATION
        for m in usable
    )


def gazetteer_hits(text: str, known: set[str], cache: dict[str, bool]) -> list[str]:
    """Matched n-grams (via ``atlas.geo.gazetteer.lookup``, blacklist respected)."""
    hits: set[str] = set()
    for gram in candidate_ngrams(text):
        key = normalize_name(gram)
        if key not in known:
            continue
        if key not in cache:
            cache[key] = is_place_hit(gram)
        if cache[key]:
            hits.add(gram)
    # Drop n-grams contained in a longer matched one ("San Francisco" in "San Francisco Bay").
    return sorted(h for h in hits if not any(h != o and h in o for o in hits))


def ca_registry_ids(path: Path) -> set[str]:
    rows = pq.read_table(path, columns=["openalex_id"]).to_pylist()
    return {_short(r["openalex_id"]) for r in rows if r["openalex_id"]}


def record_from_work(work: dict, fetched_at: str) -> dict:
    authorships = work.get("authorships") or []
    institutions = sorted(
        {
            _short(inst.get("id"))
            for a in authorships
            for inst in a.get("institutions") or []
            if inst.get("id")
        }
    )
    authors = sorted(
        {_short((a.get("author") or {}).get("id")) for a in authorships if a.get("author")} - {""}
    )
    source = ((work.get("primary_location") or {}).get("source")) or {}
    return {
        "work_id": _short(work.get("id")),
        "title": work.get("display_name") or "",
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "year": work.get("publication_year"),
        "type": work.get("type") or "",
        "oa_status": (work.get("open_access") or {}).get("oa_status") or "",
        "journal": source.get("display_name") or "",
        "author_ids": authors,
        "institution_ids": institutions,
        "topics": [t.get("display_name") or "" for t in (work.get("topics") or [])[:3]],
        "fetched_at_utc": fetched_at,
    }


def finish(
    records: list[dict], args: argparse.Namespace, version: str, fetched_at: str, *, count, credits
) -> int:
    registry = ca_registry_ids(args.registry)
    unique = {r["work_id"]: r for r in records}  # cursor paging can repeat a work
    non_ca = [r for r in unique.values() if not (set(r["institution_ids"]) & registry)]
    known = load_known_names()
    cache: dict[str, bool] = {}
    for record in non_ca:
        names = gazetteer_hits(f"{record['title']}. {record['abstract']}", known, cache)
        record["gazetteer_names"] = names
    hits = [r for r in non_ca if r["gazetteer_names"]]
    args.raw.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pylist(non_ca) if non_ca else pa.table({"work_id": []}),
        args.raw,
        compression="zstd",
    )
    args.hits.parent.mkdir(parents=True, exist_ok=True)
    with args.hits.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HIT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in sorted(hits, key=lambda r: r["work_id"]):
            writer.writerow(
                {
                    "work_id": r["work_id"],
                    "matched_names": json.dumps(r["gazetteer_names"], ensure_ascii=False),
                    "query_version": version,
                    "fetched_at_utc": fetched_at,
                }
            )
    print(
        f"{len(records)} rows, {len(unique)} unique of meta.count {count}; "
        f"non-CA {len(non_ca)}; gazetteer hits {len(hits)}; {credits} credits"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument(
        "--registry", type=Path, default=Path("data/processed/institutions.parquet")
    )
    parser.add_argument("--raw", type=Path, default=Path("data/interim/leak_candidates.parquet"))
    parser.add_argument("--hits", type=Path, default=Path("curation/leak_gazetteer_hits_v1.csv"))
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    parser.add_argument("--max-works", type=int, default=6000)
    parser.add_argument(
        "--rescan-raw",
        action="store_true",
        help="re-run the gazetteer pass on the saved raw parquet without any API call",
    )
    args = parser.parse_args(argv)
    if not args.rescan_raw:
        load_openalex_key()
    config = load_query_config(args.config)
    version = str(config.get("version") or "")
    if args.rescan_raw:
        saved = pq.read_table(args.raw).to_pylist()
        fetched_at = saved[0]["fetched_at_utc"]
        return finish(saved, args, version, fetched_at, count=None, credits=Decimal(0))
    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        args.usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    spent = {"cost": Decimal(0), "credits": Decimal(0)}
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")

    def call(url: str, logger: ApiCostLogger) -> dict:
        error = budget.reserve_error(
            cost_usd=prior_cost + spent["cost"], credits=prior_credits + spent["credits"]
        )
        if error:
            raise Stop(error)
        before = len(logger.request_metrics)
        try:
            body = _request_json(url, logger=logger)
        except OpenAlexRateLimitError as exc:
            raise Stop(f"rate limited ({exc})") from exc
        for record in logger.request_metrics[before:]:
            credits = Decimal(str(record.get("credits") or 10))
            spent["credits"] += credits
            spent["cost"] += credits * budget.cost_per_credit_usd
        return body

    works: list[dict] = []
    count = None
    try:
        with ApiCostLogger(f"leak-candidates-{fetched_at}", args.usage_log) as logger:
            probe = call(works_url(config, per_page=1), logger)
            count = int((probe.get("meta") or {}).get("count") or 0)
            print(f"meta.count={count}")
            if count > args.max_works:
                raise Stop(f"meta.count {count} exceeds --max-works {args.max_works}")
            cursor = "*"
            while cursor:
                body = call(works_url(config, per_page=100, cursor=cursor), logger)
                works.extend(body.get("results") or [])
                cursor = (body.get("meta") or {}).get("next_cursor")
                if not body.get("results"):
                    break
    except Stop as stop:
        print(f"stopped: {stop}; credits used {spent['credits']}")
        return 1
    records = [record_from_work(w, fetched_at) for w in works]
    return finish(records, args, version, fetched_at, count=count, credits=spent["credits"])


if __name__ == "__main__":
    raise SystemExit(main())
