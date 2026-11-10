"""Ingest state funder sources (S8.6) into ``data/interim/grants/state_funders.parquet``.

Sources: OPC Council summaries, the Delta Science Tracker Excel export, and the CSU COAST
and SCC gap records. Curated rows from ``curation/grants_manual.csv`` override scraped
rows with the same ``grant_key``.

``--max-requests`` caps network calls (0 means cache-only). Cached raw responses under
``data/raw/state_funders/`` are reused without a request; ``--refresh`` refetches pages.
Any HTTP, budget, or robots error defers the run: the script exits 0 with status
``deferred`` and leaves the output untouched. Only counts are printed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from atlas.ingest.grants.state_funders import (
    CURATION_PATH,
    OUTPUT,
    RAW_DIR,
    STATUS_PATH,
    Fetcher,
    run_state_funders,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-requests", type=int, default=60)
    parser.add_argument("--refresh", action="store_true", help="refetch cached pages")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--status", type=Path, default=STATUS_PATH)
    parser.add_argument("--curation", type=Path, default=CURATION_PATH)
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--taxonomy", type=Path, default=Path("config/taxonomy.yml"))
    args = parser.parse_args(argv)
    if args.max_requests < 0:
        parser.error("--max-requests must be at least 0")

    fetcher = Fetcher(raw_dir=args.raw_dir, max_requests=args.max_requests, refresh=args.refresh)
    summary = run_state_funders(
        fetcher=fetcher,
        query_config=_load_yaml(args.config),
        taxonomy=_load_yaml(args.taxonomy),
        output=args.output,
        status_path=args.status,
        curation_path=args.curation,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
