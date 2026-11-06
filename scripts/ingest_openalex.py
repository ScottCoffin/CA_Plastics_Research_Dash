"""Run the S2.1 OpenAlex works ingester."""

from __future__ import annotations

import argparse
from pathlib import Path

from atlas.ingest.openalex import (
    OpenAlexPaths,
    ingest_fixture,
    ingest_live,
    load_institution_ids,
    load_openalex_key,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--updated-since")
    parser.add_argument(
        "--institution-parquet", type=Path, default=Path("data/processed/institutions.parquet")
    )
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/openalex_works"))
    parser.add_argument("--output", type=Path, default=Path("data/interim/works_raw.parquet"))
    parser.add_argument(
        "--high-water", type=Path, default=Path("data/interim/openalex_works_high_water_mark.json")
    )
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--allow-candidate", action="store_true")
    args = parser.parse_args()

    paths = OpenAlexPaths(
        raw_dir=args.raw_dir,
        output_parquet=args.output,
        high_water_mark=args.high_water,
        usage_log=args.usage_log,
    )
    if args.fixture:
        result = ingest_fixture(args.fixture, paths=paths)
    else:
        if (
            args.start_year is None
            and args.end_year is None
            and args.updated_since is None
            and not args.high_water.exists()
        ):
            parser.error("live mode requires --start-year/--end-year or --updated-since")
        load_openalex_key()
        result = ingest_live(
            config_path=args.config,
            institution_ids=load_institution_ids(args.institution_parquet),
            paths=paths,
            start_year=args.start_year,
            end_year=args.end_year,
            updated_since=args.updated_since,
            per_page=args.per_page,
            max_pages=args.max_pages,
            allow_candidate=args.allow_candidate,
        )
    print(result)


if __name__ == "__main__":
    main()
