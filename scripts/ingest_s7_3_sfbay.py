from __future__ import annotations

import argparse

from atlas.ingest.monitoring.sfbay import ingest_workbook


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize the cleared SF Bay / 5 Gyres XLSX")
    parser.add_argument("workbook", help="locally held source XLSX")
    parser.add_argument("--output-dir", default="data/processed/normalized/sf_bay_5gyres")
    parser.add_argument(
        "--allow-hash-change", action="store_true", help="require manual schema review first"
    )
    args = parser.parse_args()
    report = ingest_workbook(
        args.workbook, output_dir=args.output_dir, allow_hash_change=args.allow_hash_change
    )
    print(report)


if __name__ == "__main__":
    main()
