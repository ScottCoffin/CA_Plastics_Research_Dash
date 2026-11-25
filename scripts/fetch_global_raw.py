"""PLAT-4a: budget-guarded, resumable raw fetch of the global plastics query (unpublished).

Modes: ``--dry-run`` prints request URLs (no network). ``--estimate`` makes one count
request and records the expected works, pages and USD in ``<raw-dir>/estimate.json``; paging
refuses to start until that exists. Default mode pages into ``<raw-dir>`` and resumes from
``state.json``. Expected budget or rate stops exit 0 with progress saved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from atlas.ingest.global_raw import (
    DEFAULT_BUDGET,
    DEFAULT_CONFIG,
    DEFAULT_MAX_CREDITS,
    DEFAULT_RAW_DIR,
    DEFAULT_USAGE_LOG,
    GLOBAL_PER_PAGE,
    GLOBAL_START_YEAR,
    StateMismatchError,
    dry_run,
    estimate_global,
    fetch_global,
)
from atlas.ingest.openalex import load_openalex_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--estimate", action="store_true", help="one count request; no paging")
    mode.add_argument("--dry-run", action="store_true", help="print request URLs and stop")
    parser.add_argument("--restart", action="store_true", help="archive saved state, start over")
    parser.add_argument("--start-year", type=int, default=GLOBAL_START_YEAR)
    parser.add_argument("--end-year", type=int, help="default: current UTC year")
    parser.add_argument("--per-page", type=int, default=GLOBAL_PER_PAGE)
    parser.add_argument(
        "--max-credits", type=float, default=DEFAULT_MAX_CREDITS, help="credit cap per run"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    args = parser.parse_args(argv)

    try:
        if args.dry_run:
            result = dry_run(
                config_path=args.config,
                start_year=args.start_year,
                end_year=args.end_year,
                per_page=args.per_page,
            )
        elif args.estimate:
            load_openalex_key()
            result = estimate_global(
                config_path=args.config,
                budget_path=args.budget,
                raw_dir=args.raw_dir,
                usage_log=args.usage_log,
                start_year=args.start_year,
                end_year=args.end_year,
                per_page=args.per_page,
            )
        else:
            load_openalex_key()
            result = fetch_global(
                config_path=args.config,
                budget_path=args.budget,
                raw_dir=args.raw_dir,
                usage_log=args.usage_log,
                start_year=args.start_year,
                end_year=args.end_year,
                per_page=args.per_page,
                max_credits=args.max_credits,
                restart=args.restart,
            )
    except StateMismatchError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
