"""Add-on A2 acceptance test EAT-10: the companion ledger data file
docs/opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx has exactly 70
rows with unique IDs matching the roster, 20 columns, and every product_type value and
kw_ flag used in a cell_rule exists in taxonomy.yml.

Owning EM task: EM-1.

Offline only: reads the committed XLSX and taxonomy.yml and makes no network calls.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
XLSX = ROOT / "docs" / "opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx"
TAXONOMY = ROOT / "config" / "taxonomy.yml"

sys.path.insert(0, str(ROOT / "src"))

from atlas.evidence.need_ledger import (  # noqa: E402
    COLUMNS,
    ROSTER_ORDER,
    cell_rule_identifiers,
    load_need_ledger,
    load_taxonomy,
    taxonomy_vocabulary,
)

PRODUCT_CALL = re.compile(r"list_(?:contains|has_any)\(product_type,\s*(\[[^\]]*\]|'[^']*')\)")
QUOTED = re.compile(r"'([^']*)'")


def _section():
    return load_taxonomy(TAXONOMY)["add_on_a2"]


def test_ledger_has_70_rows_with_roster_ids_and_20_columns():
    rows = load_need_ledger(XLSX)
    assert len(rows) == 70
    assert len(COLUMNS) == 20
    assert all(tuple(row.keys()) == COLUMNS for row in rows)
    ids = [row["need_id"] for row in rows]
    assert len(set(ids)) == 70
    assert set(ids) == set(ROSTER_ORDER)
    assert ids == list(ROSTER_ORDER)


def test_product_types_and_keyword_flags_in_cell_rules_exist_in_taxonomy():
    section = _section()
    product_types = set(section["product_type"])
    keyword_flags = set(section["keyword_flags"])
    vocabulary = taxonomy_vocabulary(load_taxonomy(TAXONOMY))

    rows = load_need_ledger(XLSX)
    checked_products = 0
    checked_flags = 0
    for row in rows:
        literals, flags = cell_rule_identifiers(row["cell_rule"])
        for call in PRODUCT_CALL.finditer(row["cell_rule"]):
            for literal in QUOTED.findall(call.group(1)):
                checked_products += 1
                assert literal in product_types, (row["need_id"], literal)
        for flag in flags:
            checked_flags += 1
            assert flag in keyword_flags, (row["need_id"], flag)
        for literal in literals:
            assert literal in vocabulary, (row["need_id"], literal)
        _, evidence_flags = cell_rule_identifiers(row["evidence_cols"])
        assert evidence_flags <= keyword_flags, row["need_id"]

    # Guard against the regexes silently matching nothing.
    assert checked_products > 0
    assert checked_flags > 0
