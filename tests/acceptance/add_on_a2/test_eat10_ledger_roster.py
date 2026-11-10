"""Add-on A2 acceptance test EAT-10: the companion ledger data file
docs/opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx has exactly 70
rows with unique IDs matching the roster, 20 columns, and every product_type value and
kw_ flag used in a cell_rule exists in taxonomy.yml.

Owning EM task: EM-1.

Placeholder. Skipped until the owning task lands. Offline only; reads no data
and makes no network calls.
"""

import pytest

pytest.skip(
    "Add-on A2 acceptance test EAT-10 is a placeholder until EM-1 lands",
    allow_module_level=True,
)
