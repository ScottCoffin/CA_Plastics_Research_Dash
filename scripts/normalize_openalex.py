"""Normalize S2.1 raw OpenAlex works or the committed S2.2 fixture."""

from __future__ import annotations

import argparse
from pathlib import Path

from atlas.ingest.normalize import normalize_fixture, normalize_raw_parquet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/interim/works_raw.parquet"))
    parser.add_argument(
        "--fixture", type=Path, default=Path("tests/fixtures/s2_2_openalex_works.json")
    )
    parser.add_argument(
        "--institution", type=Path, default=Path("data/processed/institutions.parquet")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/normalized"))
    parser.add_argument("--qc", type=Path, default=Path("docs/normalization_qc.md"))
    args = parser.parse_args()
    if args.input.exists():
        result = normalize_raw_parquet(
            args.input,
            institution_path=args.institution,
            output_dir=args.output_dir,
            qc_path=args.qc,
        )
    else:
        result = normalize_fixture(
            args.fixture,
            institution_path=args.institution,
            output_dir=args.output_dir,
            qc_path=args.qc,
        )
    print(f"S2.2 normalized {result.metrics['works']} works; QC: {result.qc_path}")


if __name__ == "__main__":
    main()
