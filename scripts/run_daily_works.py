"""Run one guarded daily OpenAlex works refresh.

Expected OpenAlex budget/rate responses are reported as a deferred run with
exit code zero. The workflow can then leave existing outputs in place and let
the next scheduled invocation resume from the unchanged high-water mark.
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

from atlas.ingest.daily import run_daily_ingest
from atlas.ingest.openalex import OpenAlexPaths, load_institution_ids, load_openalex_key


def _write_github_output(name: str, value: object) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{name}={value}\n")


def _write_summary(message: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{message}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--max-credits", type=float, default=None)
    parser.add_argument("--max-cost-usd", type=float, default=None)
    parser.add_argument("--allow-candidate", action="store_true")
    args = parser.parse_args(argv)

    load_openalex_key()
    start_year = args.start_year
    if (
        start_year is None
        and args.end_year is None
        and args.updated_since is None
        and not args.high_water.exists()
    ):
        # The first scheduled run is intentionally bounded to the current year;
        # subsequent runs use the inclusive high-water mark automatically.
        start_year = datetime.now(UTC).year
    result = run_daily_ingest(
        institution_ids=load_institution_ids(args.institution_parquet),
        config_path=args.config,
        paths=OpenAlexPaths(
            raw_dir=args.raw_dir,
            output_parquet=args.output,
            high_water_mark=args.high_water,
            usage_log=args.usage_log,
        ),
        start_year=start_year,
        end_year=args.end_year,
        updated_since=args.updated_since,
        allow_candidate=args.allow_candidate,
        max_pages=args.max_pages,
        max_credits=args.max_credits,
        max_cost_usd=args.max_cost_usd,
    )
    _write_github_output("status", result["status"])
    _write_github_output("reason", result.get("reason", ""))
    if result["status"] == "deferred":
        message = (
            f"## OpenAlex refresh deferred\n\nReason: `{result['reason']}`. "
            "Existing outputs and high-water state were preserved; the next run will retry."
        )
        print(message.replace("\n", " "))
        _write_summary(message)
        return 0
    print(
        f"Daily OpenAlex refresh succeeded: fetched={result.get('fetched', 0)} "
        f"rows_written={result.get('rows_written', 0)}"
    )
    _write_summary(
        "## OpenAlex refresh succeeded\n\n"
        f"Fetched `{result.get('fetched', 0)}` works; "
        f"stored `{result.get('rows_written', 0)}` unique rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
