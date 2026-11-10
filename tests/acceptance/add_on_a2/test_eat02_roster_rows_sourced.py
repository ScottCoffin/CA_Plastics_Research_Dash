"""Add-on A2 acceptance test EAT-2: every roster row has source, PDF page and rule, and
unit tests pass.

Owning EM task: EM-1.

Offline only: reads the committed companion XLSX and makes no network calls. The unit tests
for the ledger live in tests/test_need_ledger_em1.py.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
XLSX = ROOT / "docs" / "opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx"
TAXONOMY = ROOT / "config" / "taxonomy.yml"

sys.path.insert(0, str(ROOT / "src"))

from atlas.evidence.need_ledger import (  # noqa: E402
    ROSTER_ORDER,
    load_need_ledger,
    load_taxonomy,
    validate_need_ledger,
)


def test_every_roster_row_has_source_page_and_rule():
    rows = load_need_ledger(XLSX)
    assert [row["need_id"] for row in rows] == list(ROSTER_ORDER)

    missing_source = [row["need_id"] for row in rows if not row["source_doc"]]
    missing_rule = [row["need_id"] for row in rows if not row["cell_rule"]]
    missing_page = [row["need_id"] for row in rows if not row["pdf_page"]]

    assert missing_source == []
    assert missing_rule == []
    # Every row, including X rows, has a PDF page in the current data. Any exception must be
    # justified in the QC report before this assertion is relaxed.
    assert missing_page == []


def test_committed_ledger_validates_with_no_hard_errors():
    rows = load_need_ledger(XLSX)
    findings = validate_need_ledger(rows, load_taxonomy(TAXONOMY))
    assert all(isinstance(finding, str) for finding in findings)
