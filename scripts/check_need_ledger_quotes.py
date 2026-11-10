"""Check Add-on A2 Need Ledger quotes against owner-local source PDFs (local only, never in CI).

Usage:
    py -3.14 scripts/check_need_ledger_quotes.py --write-map-template > scratch/map.json
    py -3.14 scripts/check_need_ledger_quotes.py --pdf-dir PATH --map scratch/map.json
    py -3.14 scripts/check_need_ledger_quotes.py --pdf-dir PATH --map MAP --strict

Without --pdf-dir (and without ATLAS_A2_PDF_DIR) the check prints a skip notice and exits 0.
--strict exits 1 when any row is not_found, match_elsewhere or bad_page.
The PDFs and the map are never committed; the report holds statuses and page numbers only.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.evidence.quote_check import (  # noqa: E402
    FAILING_STATUSES,
    PageExtractor,
    build_pdf_paths,
    build_report,
    check_rows,
    format_summary,
    load_ledger_rows,
    load_source_map,
    map_template_json,
    pdfminer_page_extractor,
    summarize,
    write_report,
)

DEFAULT_CSV = ROOT / "config" / "need_ledger.csv"
DEFAULT_REPORT = ROOT / "data" / "interim" / "need_ledger_quote_check.json"
PDF_DIR_ENV = "ATLAS_A2_PDF_DIR"
SKIP_STATUS = "skipped (no local PDFs)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--pdf-dir", type=Path, help=f"directory of local PDFs (or set {PDF_DIR_ENV})"
    )
    parser.add_argument(
        "--map", type=Path, dest="map_path", help="JSON or YAML source_doc to file map"
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="need ledger CSV")
    parser.add_argument(
        "--report", type=Path, default=DEFAULT_REPORT, help="per-row JSON report path"
    )
    parser.add_argument(
        "--strict", action="store_true", help="exit 1 on not_found, match_elsewhere or bad_page"
    )
    parser.add_argument(
        "--write-map-template",
        action="store_true",
        help="print a template source map to stdout and exit",
    )
    return parser


def main(
    argv: Sequence[str] | None = None, *, extractor: PageExtractor = pdfminer_page_extractor
) -> int:
    args = build_parser().parse_args(argv)
    if args.write_map_template:
        sys.stdout.write(map_template_json())
        return 0

    pdf_dir_value = str(args.pdf_dir) if args.pdf_dir else os.environ.get(PDF_DIR_ENV, "").strip()
    if not pdf_dir_value:
        print(f"Need ledger quote check: status: {SKIP_STATUS}. Set --pdf-dir or {PDF_DIR_ENV}.")
        return 0

    pdf_dir = Path(pdf_dir_value)
    if not pdf_dir.is_dir():
        print(f"Need ledger quote check: PDF directory not found: {pdf_dir.name}", file=sys.stderr)
        return 2
    if args.map_path is None:
        print(
            "Need ledger quote check: --map is required with a PDF directory "
            "(see --write-map-template).",
            file=sys.stderr,
        )
        return 2

    try:
        mapping = load_source_map(args.map_path)
        pdf_paths = build_pdf_paths(mapping, pdf_dir)
        rows = load_ledger_rows(args.csv)
    except (ValueError, OSError) as error:
        print(f"Need ledger quote check: {error}", file=sys.stderr)
        return 2

    results = check_rows(rows, pdf_paths, extractor)
    report = build_report(results)
    write_report(report, args.report)

    print(format_summary(summarize(results)))
    print(f"report written: {args.report}")
    if args.strict and any(result["status"] in FAILING_STATUSES for result in results):
        print("Need ledger quote check: failing rows found (--strict).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
