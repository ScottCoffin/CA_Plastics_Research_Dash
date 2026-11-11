"""Fetch OpenAlex citation metrics for the exported CA experts.

Writes ``data/processed/author_metrics.parquet`` (author_id, cited_by_count,
h_index, i10_index, works_count, fetched_at_utc) for every author in the
normalized table with a CA-affiliated work. One OpenAlex list call covers 100
authors (1 credit each), so ~2,000 experts cost ~20 credits. Every call goes
through the budget guard; on a budget or rate stop the previous file is kept and
the script exits 0 with a message, so the export simply reuses older metrics.

Metrics are career-wide (all of an author's OpenAlex works, not only plastics
works); the export adds plastics-only citations from the corpus itself.
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
    ]
)
BATCH = 100


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


def row_from_author(author: dict, fetched_at: str) -> dict:
    stats = author.get("summary_stats") or {}
    return {
        "author_id": str(author.get("id") or "").rsplit("/", 1)[-1],
        "cited_by_count": int(author.get("cited_by_count") or 0),
        "h_index": int(stats.get("h_index") or 0),
        "i10_index": int(stats.get("i10_index") or 0),
        "works_count": int(author.get("works_count") or 0),
        "fetched_at_utc": fetched_at,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authors", type=Path, default=Path("data/processed/normalized/authors.parquet")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/author_metrics.parquet")
    )
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    args = parser.parse_args(argv)
    load_openalex_key()
    ids = author_ids(args.authors)
    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        args.usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    rows: list[dict] = []
    run_cost = Decimal(0)
    run_credits = Decimal(0)
    with ApiCostLogger(f"author-metrics-{fetched_at}", args.usage_log) as logger:
        for start in range(0, len(ids), BATCH):
            error = budget.reserve_error(
                cost_usd=prior_cost + run_cost, credits=prior_credits + run_credits
            )
            if error:
                print(f"author metrics deferred: {error}; keeping {args.output}")
                return 0
            before = len(logger.request_metrics)
            try:
                body = _request_json(authors_url(ids[start : start + BATCH]), logger=logger)
            except OpenAlexRateLimitError as exc:
                print(f"author metrics deferred: rate limited ({exc}); keeping {args.output}")
                return 0
            for record in logger.request_metrics[before:]:
                credits = Decimal(str(record.get("credits") or 10))
                run_credits += credits
                run_cost += credits * budget.cost_per_credit_usd
            rows.extend(row_from_author(a, fetched_at) for a in body.get("results") or [])
    rows = sorted({r["author_id"]: r for r in rows}.values(), key=lambda r: r["author_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), args.output, compression="zstd")
    print(f"author metrics: {len(rows)} of {len(ids)} authors; {run_credits} credits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
