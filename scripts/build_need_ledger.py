"""Build config/need_ledger.csv and docs/need_ledger_qc.md from the Add-on A2 companion XLSX.

Usage:
    py -3.14 scripts/build_need_ledger.py          # validate, then write CSV and QC report
    py -3.14 scripts/build_need_ledger.py --check  # exit 1 unless committed outputs are fresh

The XLSX is read only. Hard validation errors stop the run with exit code 1 and write nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.evidence.need_ledger import (  # noqa: E402
    load_need_ledger,
    load_taxonomy,
    render_need_ledger_csv,
    render_need_ledger_qc,
    validate_need_ledger,
)

GENERATOR = "scripts/build_need_ledger.py"
XLSX_PATH = ROOT / "docs" / "opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx"
TAXONOMY_PATH = ROOT / "config" / "taxonomy.yml"
CSV_PATH = ROOT / "config" / "need_ledger.csv"
QC_PATH = ROOT / "docs" / "need_ledger_qc.md"


def build_outputs() -> tuple[str, str]:
    """Load, validate, and render (csv_text, qc_text). Raises ValueError on hard errors."""
    rows = load_need_ledger(XLSX_PATH)
    findings = validate_need_ledger(rows, load_taxonomy(TAXONOMY_PATH))
    digest = hashlib.sha256(XLSX_PATH.read_bytes()).hexdigest()
    qc_text = render_need_ledger_qc(
        rows,
        findings,
        source_label=XLSX_PATH.relative_to(ROOT).as_posix(),
        source_sha256=digest,
        generator=GENERATOR,
    )
    return render_need_ledger_csv(rows), qc_text


def _display(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _committed_matches(path: Path, expected: str) -> bool:
    if not path.is_file():
        return False
    return path.read_bytes() == expected.encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the committed CSV or QC report differs from a fresh export",
    )
    args = parser.parse_args(argv)

    try:
        csv_text, qc_text = build_outputs()
    except ValueError as error:
        print(f"Need Ledger build failed: {error}", file=sys.stderr)
        return 1

    if args.check:
        stale = [
            _display(path)
            for path, text in ((CSV_PATH, csv_text), (QC_PATH, qc_text))
            if not _committed_matches(path, text)
        ]
        if stale:
            print(
                "Need Ledger outputs are stale: "
                + ", ".join(stale)
                + "; run scripts/build_need_ledger.py",
                file=sys.stderr,
            )
            return 1
        print("Need Ledger outputs match a fresh export.")
        return 0

    with CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write(csv_text)
    with QC_PATH.open("w", encoding="utf-8", newline="") as handle:
        handle.write(qc_text)
    print(f"Wrote {_display(CSV_PATH)} and {_display(QC_PATH)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
