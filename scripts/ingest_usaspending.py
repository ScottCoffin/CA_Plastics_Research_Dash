"""Ingest USAspending grants into ``data/interim/grants/usaspending.parquet`` (S8.4).

``--backfill`` walks the last 15 fiscal years (newest first) and stops at the request
cap; rerun it to resume.  ``--incremental`` refetches the current and previous fiscal
year.  ``--dry-run`` prints the planned first-page requests and makes no network calls
or writes.  ``--bulk`` (with ``--backfill`` only) uses the bulk award archive instead of
the search API; it is implemented but not run against the live service.

Failures that defer a run (HTTP errors, unusable responses, page cap) exit 0 with
status ``deferred`` and leave the existing output untouched, following the S8.2 pattern.
Only counts are printed; records are never echoed.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from atlas.ingest.grants.nih_reporter import fiscal_years_for
from atlas.ingest.grants.usaspending import (
    dry_run_plan,
    run_bulk_ingest,
    run_ingest,
    urllib_transport,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backfill", action="store_true", help="last 15 fiscal years, resumable")
    mode.add_argument("--incremental", action="store_true", help="current and previous FY")
    parser.add_argument("--bulk", action="store_true", help="backfill via bulk archive (off)")
    parser.add_argument("--dry-run", action="store_true", help="print planned requests only")
    parser.add_argument("--max-requests", type=int, default=25)
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--taxonomy", type=Path, default=Path("config/taxonomy.yml"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/interim/grants/usaspending.parquet")
    )
    parser.add_argument(
        "--state", type=Path, default=Path("data/interim/grants/usaspending_state.json")
    )
    args = parser.parse_args(argv)
    if args.max_requests < 1:
        parser.error("--max-requests must be at least 1")
    if args.bulk and not args.backfill:
        parser.error("--bulk requires --backfill")
    if args.bulk and args.dry_run:
        parser.error("--dry-run does not apply to --bulk")

    mode_name = "backfill" if args.backfill else "incremental"
    today = datetime.now(UTC).date()
    if args.dry_run:
        plan = dry_run_plan(
            mode=mode_name,
            today=today,
            state_path=args.state,
            max_requests=args.max_requests,
        )
        print(json.dumps(plan, indent=1, sort_keys=True))
        return 0

    query_config = _load_yaml(args.config)
    taxonomy = _load_yaml(args.taxonomy)
    if args.bulk:
        summary = run_bulk_ingest(
            fiscal_years=fiscal_years_for("backfill", today),
            output=args.output,
            state_path=args.state,
            query_config=query_config,
            taxonomy=taxonomy,
            transport=urllib_transport,
            max_requests=args.max_requests,
            today=today,
        )
    else:
        summary = run_ingest(
            mode=mode_name,
            output=args.output,
            state_path=args.state,
            query_config=query_config,
            taxonomy=taxonomy,
            transport=urllib_transport,
            max_requests=args.max_requests,
            today=today,
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
