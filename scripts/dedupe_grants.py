"""De-duplicate all grant tables (S8.6) into ``grants_merged.parquet`` and an overlap report.

Reads every ``data/interim/grants/*.parquet`` (except the merged output). Writes the
representative rows to ``data/interim/grants/grants_merged.parquet``, a row-level map to
``data/interim/grants/grants_dedupe_map.csv`` (both git-ignored), and the aggregate-only
report to ``docs/grants_overlap_report.md``. Prints counts only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.ingest.grants.dedupe import INTERIM_DIR, REPORT_PATH, run_dedupe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interim-dir", type=Path, default=INTERIM_DIR)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args(argv)
    summary = run_dedupe(interim_dir=args.interim_dir, report_out=args.report)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
