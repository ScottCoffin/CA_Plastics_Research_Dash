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

The plastics pass is incremental: authors never fetched (then the oldest) go first,
the file is saved after every batch, and a budget or rate stop keeps what was done so
the next daily run continues. ``plastic_fetched_at_utc`` is empty until covered.
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from datetime import UTC, datetime
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
from atlas.util.cost import ApiCostLogger  # noqa: E402

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
        "select": "id,cited_by_count,summary_stats,works_count",
    }
    return f"{OPENALEX_BASE}/authors?{urllib.parse.urlencode(params)}"


def plastic_works_url(config: dict, ids: list[str], cursor: str = "*") -> str:
    filters = [openalex_filter(config), "authorships.author.id:" + "|".join(ids)]
    filters += type_filters(config)
    params = {
        "filter": ",".join(filters),
        "per-page": 100,
        "cursor": cursor,
        "select": "id,cited_by_count,authorships",
    }
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def _short(value: object) -> str:
    return str(value or "").rsplit("/", 1)[-1]


def row_from_author(author: dict, fetched_at: str) -> dict:
    stats = author.get("summary_stats") or {}
    return {
        "author_id": _short(author.get("id")),
        "cited_by_count": int(author.get("cited_by_count") or 0),
        "h_index": int(stats.get("h_index") or 0),
        "i10_index": int(stats.get("i10_index") or 0),
        "works_count": int(author.get("works_count") or 0),
        "fetched_at_utc": fetched_at,
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


def _empty_plastic() -> dict:
    return {
        "plastic_works_global": None,
        "plastic_citations_global": None,
        "plastic_query_version": "",
        "plastic_fetched_at_utc": "",
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
            if not args.skip_plastics:
                version = str(config.get("version") or "")
                pending = sorted(
                    ids,
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
                    for author, (n, cites) in tally_plastic_works(works, set(batch)).items():
                        rows[author] = {
                            **rows.get(author, {"author_id": author}),
                            "plastic_works_global": n,
                            "plastic_citations_global": cites,
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
