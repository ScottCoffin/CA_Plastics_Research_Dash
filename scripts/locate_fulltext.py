"""Create license-aware OA full-text locators from normalized and raw works."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow.parquet as pq

from atlas.fulltext import coverage_report, locate_records, write_locator


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--works", type=Path, default=Path("data/processed/normalized/works.parquet")
    )
    parser.add_argument("--raw", type=Path, default=Path("data/interim/works_raw.parquet"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/normalized/fulltext_locators.parquet")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("data/processed/normalized/fulltext_coverage.md")
    )
    args = parser.parse_args()

    candidates = pq.read_table(
        args.works, columns=["work_id", "is_oa", "oa_url", "license"]
    ).to_pylist()
    raw_rows = pq.read_table(args.raw, columns=["openalex_id", "raw_json"]).to_pylist()
    raw_by_id = {str(row["openalex_id"]).rsplit("/", 1)[-1]: row["raw_json"] for row in raw_rows}
    rows = locate_records(candidates, raw_by_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_locator(rows, str(args.output))
    args.report.write_text(
        coverage_report(rows, source=f"{args.works} + {args.raw}"), encoding="utf-8"
    )
    print(f"Located {len(rows)} candidate works: {args.output}; coverage: {args.report}")


if __name__ == "__main__":
    main()
