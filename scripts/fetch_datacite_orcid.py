"""Fetch DataCite outputs for expert ORCIDs (S2.5d).

Writes ``data/processed/expert_datacite_outputs.parquet`` with identifiers,
bibliographic fields and classification flags only. Descriptions are not stored.
Raw DataCite pages are cached under ``data/raw/datacite_orcid/`` (gitignored).

Live calls go to ``api.datacite.org`` only. ``--max-requests`` caps live requests
(default 400). ``--offline`` reads the cache only and fails on any cache miss.
``--limit N`` queries the first N expert ORCIDs in sorted order.

Only the summary counts are printed as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys

from atlas.ingest.datacite_orcid import (
    DEFAULT_MAX_REQUESTS,
    CacheMiss,
    DataCiteHTTPError,
    RequestBudgetExhausted,
    run_expert_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=None, help="query only the first N ORCIDs")
    parser.add_argument(
        "--max-requests",
        type=int,
        default=DEFAULT_MAX_REQUESTS,
        help=f"hard cap on live HTTP requests (default {DEFAULT_MAX_REQUESTS})",
    )
    parser.add_argument(
        "--offline", action="store_true", help="use the cache only; no network calls"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit is not None and args.limit < 1:
        print("--limit must be at least 1", file=sys.stderr)
        return 2
    if args.max_requests < 0:
        print("--max-requests must be zero or more", file=sys.stderr)
        return 2
    try:
        summary = run_expert_outputs(
            limit=args.limit, max_requests=args.max_requests, offline=args.offline
        )
    except (RequestBudgetExhausted, CacheMiss, DataCiteHTTPError) as error:
        print(f"incomplete run, no output written: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
