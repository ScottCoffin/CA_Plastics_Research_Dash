"""Append one run record to ``data/processed/status_history.jsonl`` (S10.1).

Counts and rates are computed from the committed Parquet files. Only counts and the
record's status are printed. Use ``--workflow seed --run-id local --status ok`` once to
seed the history from the current committed data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.build.status import (
    DEFAULT_HISTORY,
    DEFAULT_LABELS,
    DEFAULT_USAGE_LOG,
    DEFAULT_WORKS,
    STATUSES,
    append_record,
    build_run_record,
    last_works_total,
    load_parquet_tables,
    load_usage_rows,
    read_history,
    utc_now_iso,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--status", required=True, choices=STATUSES)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--works", type=Path, default=DEFAULT_WORKS)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    parser.add_argument(
        "--since",
        help="ISO UTC job start; spend = run_summary rows stamped at or after it",
    )
    args = parser.parse_args(argv)

    previous = last_works_total(read_history(args.history))
    labels, works = load_parquet_tables(args.labels, args.works)
    record = build_run_record(
        run_at_utc=utc_now_iso(),
        workflow=args.workflow,
        run_id=args.run_id,
        status=args.status,
        labels=labels,
        works=works,
        usage_rows=load_usage_rows(args.usage_log),
        previous_works_total=previous,
        since=args.since,
    )
    append_record(args.history, record)
    print(
        json.dumps(
            {
                "appended": str(args.history),
                "workflow": record["workflow"],
                "status": record["status"],
                "works_total": record["works_total"],
                "works_added": record["works_added"],
                "labels_total": record["labels_total"],
                "api_spend": record["api_spend"] is not None,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
