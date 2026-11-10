"""Ingest NIH RePORTER grants into ``data/interim/grants/nih_reporter.parquet`` (S8.2).

``--backfill`` walks the last 15 fiscal years (newest first) and stops at the request
cap; rerun it to resume.  ``--incremental`` refetches the current and previous fiscal
year.  ``--dry-run`` prints the planned requests and makes no network calls or writes.

Failures that defer a run (HTTP errors, unusable responses, offset ceiling) exit 0 with
status ``deferred`` and leave the existing output untouched, following the S2.4 pattern.
Only counts are printed; records are never echoed.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from atlas.ingest.grants.nih_reporter import dry_run_plan, run_ingest, urllib_transport


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
    parser.add_argument("--dry-run", action="store_true", help="print planned requests only")
    parser.add_argument("--max-requests", type=int, default=25)
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--taxonomy", type=Path, default=Path("config/taxonomy.yml"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/interim/grants/nih_reporter.parquet")
    )
    parser.add_argument(
        "--state", type=Path, default=Path("data/interim/grants/nih_reporter_state.json")
    )
    args = parser.parse_args(argv)
    if args.max_requests < 1:
        parser.error("--max-requests must be at least 1")

    mode_name = "backfill" if args.backfill else "incremental"
    query_config = _load_yaml(args.config)
    today = datetime.now(UTC).date()
    if args.dry_run:
        plan = dry_run_plan(
            mode=mode_name,
            today=today,
            query_config=query_config,
            state_path=args.state,
            max_requests=args.max_requests,
        )
        print(json.dumps(plan, indent=1, sort_keys=True))
        return 0

    summary = run_ingest(
        mode=mode_name,
        output=args.output,
        state_path=args.state,
        query_config=query_config,
        taxonomy=_load_yaml(args.taxonomy),
        transport=urllib_transport,
        max_requests=args.max_requests,
        today=today,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
