"""Fetch OpenAlex citation metrics for the exported CA experts.

Writes ``data/processed/author_metrics.parquet`` with, per author with a CA-affiliated
work:

* career metrics (``cited_by_count``, ``h_index``, ``i10_index``, ``works_count``) from
  ``/authors`` list calls (100 authors per call, 1 credit each), refreshed every run;
* plastics metrics across the author's WHOLE OpenAlex record, not only the CA corpus
  (``plastic_works_global``, ``plastic_citations_global``): works matching the active
  query (``config/queries.yml``) for a batch of authors, cursor-paged (10 credits per
  page). Comparing career citations with corpus-only plastics citations understated
  specialists whose plastics work mostly lacks CA co-authors (e.g. 42% vs 98.5%).

The plastics pass is incremental: only authors never fetched, fetched under another query
version, or older than --plastics-max-age-days (30) are refreshed, oldest first;
the file is saved after every batch, and a budget or rate stop keeps what was done so
the next daily run continues. ``plastic_fetched_at_utc`` is empty until covered.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    OpenAlexRateLimitError,
    _request_json,
    load_openalex_key,
)
from atlas.query import load_query_config, openalex_filter, type_filters  # noqa: E402
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError  # noqa: E402

SCHEMA = pa.schema(
    [
        ("author_id", pa.string()),
        ("cited_by_count", pa.int64()),
        ("h_index", pa.int64()),
        ("i10_index", pa.int64()),
        ("works_count", pa.int64()),
        ("fetched_at_utc", pa.string()),
        ("plastic_works_global", pa.int64()),
        ("plastic_citations_global", pa.int64()),
        ("plastic_query_version", pa.string()),
        ("plastic_fetched_at_utc", pa.string()),
        # JSON columns (2026-11-12, owner request: expert page). Citations received per
        # year (OpenAlex counts_by_year, last ~10 years), the author's own affiliations,
        # and plastics citations received per year over the whole-record plastics works.
        ("counts_by_year_json", pa.string()),
        ("last_known_institutions_json", pa.string()),
        ("affiliations_json", pa.string()),
        ("plastic_counts_by_year_json", pa.string()),
        # Whole-record works per publication year (group_by, 1 credit per author) and the
        # robust first publication year used for the m-quotient.
        ("works_by_year_json", pa.string()),
        ("first_pub_year", pa.int64()),
        ("career_fetched_at_utc", pa.string()),
    ]
)
BATCH = 100
PLASTIC_BATCH = 25


class Stop(Exception):
    """Budget or rate stop: save progress and exit cleanly."""


def author_ids(authors_path: Path) -> list[str]:
    rows = pq.read_table(authors_path, columns=["author_id", "ca_works_count"]).to_pylist()
    return sorted(
        {r["author_id"] for r in rows if r["author_id"] and (r["ca_works_count"] or 0) > 0}
    )


def authors_url(ids: list[str]) -> str:
    params = {
        "filter": "openalex:" + "|".join(ids),
        "per-page": len(ids),
        "select": (
            "id,cited_by_count,summary_stats,works_count,counts_by_year,"
            "last_known_institutions,affiliations"
        ),
    }
    return f"{OPENALEX_BASE}/authors?{urllib.parse.urlencode(params)}"


def plastic_works_url(config: dict, ids: list[str], cursor: str = "*") -> str:
    filters = [openalex_filter(config), "authorships.author.id:" + "|".join(ids)]
    filters += type_filters(config)
    params = {
        "filter": ",".join(filters),
        "per-page": 100,
        "cursor": cursor,
        "select": "id,cited_by_count,authorships,counts_by_year",
    }
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def works_by_year_url(config: dict, author: str) -> str:
    filters = ["authorships.author.id:" + author, *type_filters(config)]
    params = {"filter": ",".join(filters), "group_by": "publication_year"}
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def _short(value: object) -> str:
    return str(value or "").rsplit("/", 1)[-1]


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _institution(item: dict) -> dict:
    return {
        "id": _short(item.get("id")),
        "name": str(item.get("display_name") or ""),
        "country_code": str(item.get("country_code") or ""),
    }


def works_by_year(body: dict) -> dict[int, int]:
    """``{year: works}`` from a ``group_by=publication_year`` response."""
    out: dict[int, int] = {}
    for group in body.get("group_by") or []:
        try:
            year = int(str(group.get("key")))
        except ValueError:
            continue
        out[year] = out.get(year, 0) + int(group.get("count") or 0)
    return out


def robust_first_year(counts: dict[int, int], *, window: int = 5) -> int | None:
    """Earliest publication year that is not an isolated outlier.

    A year counts as the career start when the author has at least two works in it and
    the following ``window`` years together, which skips single works misattributed by
    OpenAlex author disambiguation decades before the real career. Authors with a single
    work fall back to that year.
    """
    years = sorted(year for year, n in counts.items() if n > 0)
    for year in years:
        if sum(counts.get(y, 0) for y in range(year, year + window + 1)) >= 2:
            return year
    return years[0] if years else None


def row_from_author(author: dict, fetched_at: str) -> dict:
    stats = author.get("summary_stats") or {}
    return {
        "author_id": _short(author.get("id")),
        "cited_by_count": int(author.get("cited_by_count") or 0),
        "h_index": int(stats.get("h_index") or 0),
        "i10_index": int(stats.get("i10_index") or 0),
        "works_count": int(author.get("works_count") or 0),
        "fetched_at_utc": fetched_at,
        "counts_by_year_json": _json(
            sorted(
                (
                    {"year": int(c["year"]), "cited_by_count": int(c.get("cited_by_count") or 0)}
                    for c in author.get("counts_by_year") or []
                    if c.get("year")
                ),
                key=lambda c: c["year"],
            )
        ),
        "last_known_institutions_json": _json(
            [_institution(i) for i in author.get("last_known_institutions") or []]
        ),
        "affiliations_json": _json(
            [
                {
                    **_institution(a.get("institution") or {}),
                    "years": sorted(int(y) for y in a.get("years") or []),
                }
                for a in author.get("affiliations") or []
                if (a.get("institution") or {}).get("id")
            ]
        ),
    }


def tally_plastic_works(works: list[dict], batch: set[str]) -> dict[str, list[int]]:
    """``{author_id: [works, citations]}`` for batch authors on each matching work."""
    tally: dict[str, list[int]] = {author: [0, 0] for author in batch}
    for work in works:
        authors = {_short((a.get("author") or {}).get("id")) for a in work.get("authorships") or []}
        for author in authors & batch:
            tally[author][0] += 1
            tally[author][1] += int(work.get("cited_by_count") or 0)
    return tally


def tally_plastic_by_year(works: list[dict], batch: set[str]) -> dict[str, dict[int, int]]:
    """``{author_id: {year: citations received that year}}`` over the matching works."""
    tally: dict[str, dict[int, int]] = {author: {} for author in batch}
    for work in works:
        authors = {_short((a.get("author") or {}).get("id")) for a in work.get("authorships") or []}
        for author in authors & batch:
            for count in work.get("counts_by_year") or []:
                if not count.get("year"):
                    continue
                year = int(count["year"])
                tally[author][year] = tally[author].get(year, 0) + int(
                    count.get("cited_by_count") or 0
                )
    return tally


def _empty_plastic() -> dict:
    return {
        "plastic_works_global": None,
        "plastic_citations_global": None,
        "plastic_query_version": "",
        "plastic_fetched_at_utc": "",
        "counts_by_year_json": "",
        "last_known_institutions_json": "",
        "affiliations_json": "",
        "plastic_counts_by_year_json": "",
        "works_by_year_json": "",
        "first_pub_year": None,
        "career_fetched_at_utc": "",
    }


def _save(path: Path, rows: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(
        [{**_empty_plastic(), **rows[k]} for k in sorted(rows)], schema=SCHEMA
    )
    temp = path.with_suffix(".tmp.parquet")
    pq.write_table(table, temp, compression="zstd")
    temp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authors", type=Path, default=Path("data/processed/normalized/authors.parquet")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/author_metrics.parquet")
    )
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    parser.add_argument("--skip-plastics", action="store_true")
    parser.add_argument("--skip-career", action="store_true", help="skip works-per-year pass")
    parser.add_argument(
        "--career-max-age-days",
        type=int,
        default=180,
        help="refresh works-per-year (first publication year) only when older than this",
    )
    parser.add_argument(
        "--plastics-max-age-days",
        type=int,
        default=30,
        help="refresh whole-record plastics counts only when older than this (or new query)",
    )
    args = parser.parse_args(argv)
    load_openalex_key()
    ids = author_ids(args.authors)
    config = load_query_config(args.config)
    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        args.usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    existing: dict[str, dict] = {}
    if args.output.exists():
        existing = {r["author_id"]: r for r in pq.read_table(args.output).to_pylist()}
    rows: dict[str, dict] = {k: v for k, v in existing.items() if k in set(ids)}
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    spent = {"cost": Decimal(0), "credits": Decimal(0)}

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
        except OpenAlexUsageMetadataError as exc:
            # A gateway failure (e.g. HTTP 504) without a credit header: save and stop;
            # the next run resumes from the saved rows.
            raise Stop(f"OpenAlex request failed ({exc})") from exc
        for record in logger.request_metrics[before:]:
            credits = Decimal(str(record.get("credits") or 10))
            spent["credits"] += credits
            spent["cost"] += credits * budget.cost_per_credit_usd
        return body

    status = "complete"
    with ApiCostLogger(f"author-metrics-{fetched_at}", args.usage_log) as logger:
        try:
            for start in range(0, len(ids), BATCH):
                body = call(authors_url(ids[start : start + BATCH]), logger)
                for author in body.get("results") or []:
                    row = row_from_author(author, fetched_at)
                    rows[row["author_id"]] = {**rows.get(row["author_id"], {}), **row}
            _save(args.output, rows)
            if not args.skip_career:
                career_cutoff = (
                    datetime.now(UTC) - timedelta(days=args.career_max_age_days)
                ).isoformat()
                pending_career = [
                    a
                    for a in ids
                    if (rows.get(a, {}).get("career_fetched_at_utc") or "") < career_cutoff
                ]
                for done, author in enumerate(pending_career, 1):
                    counts = works_by_year(call(works_by_year_url(config, author), logger))
                    rows[author] = {
                        **rows.get(author, {"author_id": author}),
                        "works_by_year_json": _json(
                            [{"year": y, "works": n} for y, n in sorted(counts.items())]
                        ),
                        "first_pub_year": robust_first_year(counts),
                        "career_fetched_at_utc": fetched_at,
                    }
                    if done % 100 == 0:
                        _save(args.output, rows)
                _save(args.output, rows)
            if not args.skip_plastics:
                version = str(config.get("version") or "")
                cutoff = (
                    datetime.now(UTC) - timedelta(days=args.plastics_max_age_days)
                ).isoformat()

                def stale(author: str) -> bool:
                    row = rows.get(author, {})
                    fetched = row.get("plastic_fetched_at_utc") or ""
                    return (
                        row.get("plastic_query_version") != version
                        or fetched < cutoff
                        or not row.get("plastic_counts_by_year_json")
                    )

                pending = sorted(
                    [a for a in ids if stale(a)],
                    key=lambda a: (
                        rows.get(a, {}).get("plastic_query_version") == version,
                        rows.get(a, {}).get("plastic_fetched_at_utc") or "",
                        a,
                    ),
                )
                for start in range(0, len(pending), PLASTIC_BATCH):
                    batch = pending[start : start + PLASTIC_BATCH]
                    works: list[dict] = []
                    cursor = "*"
                    while cursor:
                        body = call(plastic_works_url(config, batch, cursor), logger)
                        works.extend(body.get("results") or [])
                        cursor = (body.get("meta") or {}).get("next_cursor")
                    by_year = tally_plastic_by_year(works, set(batch))
                    for author, (n, cites) in tally_plastic_works(works, set(batch)).items():
                        rows[author] = {
                            **rows.get(author, {"author_id": author}),
                            "plastic_works_global": n,
                            "plastic_citations_global": cites,
                            "plastic_counts_by_year_json": _json(
                                [
                                    {"year": y, "cited_by_count": c}
                                    for y, c in sorted(by_year[author].items())
                                ]
                            ),
                            "plastic_query_version": version,
                            "plastic_fetched_at_utc": fetched_at,
                        }
                    _save(args.output, rows)
        except Stop as stop:
            status = f"deferred ({stop})"
            _save(args.output, rows)
    covered = sum(1 for r in rows.values() if r.get("plastic_fetched_at_utc"))
    print(
        f"author metrics {status}: {len(rows)} authors; plastics coverage {covered}/{len(ids)}; "
        f"{spent['credits']} credits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
