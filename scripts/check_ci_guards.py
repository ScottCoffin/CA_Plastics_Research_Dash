"""Run the daily-ingest CI guards and exit 1 when any problem is found.

A clean CI checkout commits only ``site/data``, so the raw and normalized
inputs are checked only when they exist, unless ``--require-raw`` or
``--require-normalized`` is given.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from atlas.guards import run_all

DEFAULT_RAW = Path("data/interim/works_raw.parquet")
DEFAULT_NORMALIZED = Path("data/processed/normalized")
DEFAULT_SITE = Path("site/data")


def _format_metrics(metrics: dict[str, object]) -> str:
    return " ".join(f"{key}={value}" for key, value in metrics.items())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--normalized-dir", type=Path, default=DEFAULT_NORMALIZED)
    parser.add_argument("--site-data", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--require-raw", action="store_true")
    parser.add_argument("--require-normalized", action="store_true")
    args = parser.parse_args(argv)

    results = run_all(
        raw_path=args.raw,
        normalized_dir=args.normalized_dir,
        site_data_dir=args.site_data,
        require_raw=args.require_raw,
        require_normalized=args.require_normalized,
    )
    failed = False
    for name in ("raw_works", "normalized", "site_payload"):
        if name not in results:
            print(f"{name}: skipped (input not present)")
            continue
        result = results[name]
        status = "OK" if result.ok else "FAIL"
        print(f"{name}: {status} {_format_metrics(result.metrics)}".rstrip())
        for problem in result.problems:
            print(f"  - {problem}")
        failed = failed or not result.ok
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
