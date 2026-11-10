"""Ingest California Sea Grant research projects into ``data/interim/grants/`` (S8.5).

Output is ``data/interim/grants/ca_sea_grant.parquet``.

The crawl reads robots.txt, then keyword-filtered listing pages and the plastic-related
project pages they link to.  Raw pages are cached under ``data/raw/ca_sea_grant/``, so a
rerun reuses them.  ``--max-requests`` caps live requests (default 150).  A run that
hits the cap is ``partial`` and exits 0; rerun it to continue.  A failed fetch is
``deferred``, exits 0, and leaves the existing output untouched.

Only counts are printed; records are never echoed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from atlas.ingest.grants.ca_sea_grant import MAX_REQUESTS, run_ingest


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-requests", type=int, default=MAX_REQUESTS)
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--taxonomy", type=Path, default=Path("config/taxonomy.yml"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/interim/grants/ca_sea_grant.parquet")
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/ca_sea_grant"))
    args = parser.parse_args(argv)
    if args.max_requests < 1:
        parser.error("--max-requests must be at least 1")

    summary = run_ingest(
        output=args.output,
        cache_dir=args.cache_dir,
        query_config=_load_yaml(args.config),
        taxonomy=_load_yaml(args.taxonomy),
        max_requests=args.max_requests,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
