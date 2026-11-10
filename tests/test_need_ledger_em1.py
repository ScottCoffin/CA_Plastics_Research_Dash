"""Unit tests for the Add-on A2 Need Ledger loader, validator, and CSV/QC export (EM-1)."""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
from pathlib import Path

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "docs" / "opc_needs_csv_Need_Ledger_Data_File_companion_to_Add_on_Spec_A2.xlsx"
TAXONOMY = ROOT / "config" / "taxonomy.yml"
SCRIPT = ROOT / "scripts" / "build_need_ledger.py"
CSV_PATH = ROOT / "config" / "need_ledger.csv"
QC_PATH = ROOT / "docs" / "need_ledger_qc.md"

sys.path.insert(0, str(ROOT / "src"))

from atlas.evidence.need_ledger import (  # noqa: E402
    COLUMNS,
    EXPECTED_ROW_COUNT,
    ROSTER_BLOCK,
    ROSTER_ORDER,
    cell_rule_identifiers,
    expected_drivers,
    expected_group_id,
    load_need_ledger,
    load_taxonomy,
    render_need_ledger_csv,
    render_need_ledger_qc,
    taxonomy_vocabulary,
    validate_need_ledger,
    write_need_ledger_csv,
)

SYNTHETIC_TAXONOMY = {
    "add_on_a2": {
        "study_type": {"values": ["field_occurrence", "source_emission"]},
        "size_class": {"values": ["micro", "nano"]},
        "product_type": ["artificial_turf_infill"],
        "keyword_flags": ["kw_fibers"],
    }
}
REQUIRED_DISCREPANCY = (
    "The 2022 Strategy's Executive Summary states 22 recommended early actions and 13 "
    "research priorities (PDF 5). The Strategy has exactly 22 distinct early-action "
    "codes (PDF 22–24) and 14 distinct research-priority codes (Chapter 2B; PDF 30, "
    'repeated PDF 33–34). The atlas records "13" as a documented source discrepancy, '
    "hard-codes neither total in UI text, and does not speculate about the reason."
)


def _source_for(block: str) -> str:
    if block in {"D", "DI"}:
        return "DTSC_BG2025"
    if block == "DC":
        return "DTSC_2023"
    return "MON2026"


def _statement_for(block: str) -> str:
    return {
        "D": "dtsc_information_request",
        "DI": "dtsc_information_request",
        "DC": "listing_criterion",
        "X": "extension_not_in_source",
    }.get(block, "stated_gap")


def _base_rows() -> list[dict[str, str]]:
    """Return a valid synthetic 70-row ledger in roster order."""
    rows = []
    for need_id in ROSTER_ORDER:
        block = ROSTER_BLOCK[need_id]
        row = dict.fromkeys(COLUMNS, "")
        row.update(
            need_id=need_id,
            block=block,
            policy_driver="|".join(sorted(expected_drivers(need_id))),
            title=f"Title {need_id}",
            paraphrase="Paraphrase text.",
            source_doc=_source_for(block),
            source_item="Item",
            pdf_page="1",
            printed_label="1",
            quote="A short verbatim quote.",
            quote_verification="direct_page_text",
            statement_type=_statement_for(block),
            cell_rule="study_type = 'field_occurrence' AND kw_fibers",
            evidence_cols=(
                "release_exposure: study_type IN ('source_emission')"
                if block in {"D", "DI"}
                else ""
            ),
            rule_confidence="medium",
            dtsc_tier={"D": "narrowed", "DI": "initial_list"}.get(block, ""),
            link_out_ids="" if block == "X" else "LO-1",
            group_id=expected_group_id(need_id),
        )
        rows.append(row)
    return rows


def _row(rows: list[dict[str, str]], need_id: str) -> dict[str, str]:
    return next(row for row in rows if row["need_id"] == need_id)


def _hard_message(rows: list[dict[str, str]], taxonomy=SYNTHETIC_TAXONOMY) -> str:
    with pytest.raises(ValueError) as excinfo:
        validate_need_ledger(rows, taxonomy)
    return str(excinfo.value)


@pytest.fixture(scope="module")
def build_script():
    spec = importlib.util.spec_from_file_location("build_need_ledger", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- helpers -----------------------------------------------------------------------------


def test_cell_rule_identifiers_split_literals_and_flags():
    literals, flags = cell_rule_identifiers(
        "study_type IN ('field_occurrence','source_emission') AND (kw_fibers OR kw_tire_wear)"
    )
    assert literals == {"field_occurrence", "source_emission"}
    assert flags == {"kw_fibers", "kw_tire_wear"}


def test_taxonomy_vocabulary_is_union_of_add_on_a2_lists():
    assert taxonomy_vocabulary(SYNTHETIC_TAXONOMY) == {
        "field_occurrence",
        "source_emission",
        "micro",
        "nano",
        "artificial_turf_infill",
        "kw_fibers",
    }


def test_taxonomy_without_add_on_a2_section_is_rejected():
    with pytest.raises(ValueError, match="add_on_a2"):
        taxonomy_vocabulary({})


# --- valid rows and findings -------------------------------------------------------------


def test_valid_synthetic_ledger_has_no_hard_errors_or_findings():
    assert validate_need_ledger(_base_rows(), SYNTHETIC_TAXONOMY) == []


def test_findings_are_reported_without_blocking():
    rows = _base_rows()
    _row(rows, "N1.1")["quote"] = " ".join(["word"] * 31)
    _row(rows, "N1.2")["pdf_page"] = ""
    _row(rows, "X1")["pdf_page"] = ""
    _row(rows, "N1.3")["policy_driver"] = "MON-2026|OPC-2022"
    _row(rows, "N1.4")["source_doc"] = "MON2026;DTSC_WP"
    _row(rows, "X2")["link_out_ids"] = "LO-3"

    findings = validate_need_ledger(rows, SYNTHETIC_TAXONOMY)

    assert any(f.startswith("quote_length: N1.1") and "31 words" in f for f in findings)
    assert any(f.startswith("pdf_page_empty: N1.2") for f in findings)
    assert not any("X1" in f for f in findings if f.startswith("pdf_page_empty"))
    assert any(f.startswith("driver_deviation: N1.3") for f in findings)
    assert any(f.startswith("source_doc_list: N1.4") for f in findings)
    assert any(f.startswith("link_out_on_x: X2") for f in findings)


def test_quote_at_thirty_words_is_not_a_finding():
    rows = _base_rows()
    _row(rows, "N1.1")["quote"] = " ".join(["word"] * 30)
    assert validate_need_ledger(rows, SYNTHETIC_TAXONOMY) == []


# --- hard errors -------------------------------------------------------------------------


def test_wrong_column_order_is_hard_error():
    rows = _base_rows()
    keys = list(rows[0])
    rows[0] = {key: rows[0][key] for key in [keys[1], keys[0], *keys[2:]]}
    assert "columns differ" in _hard_message(rows)


def test_row_count_must_be_seventy():
    message = _hard_message(_base_rows()[:-1])
    assert "row count is 69; expected 70" in message


def test_duplicate_missing_and_extra_ids_are_hard_errors():
    rows = _base_rows()
    rows[1]["need_id"] = rows[0]["need_id"]
    message = _hard_message(rows)
    assert "duplicate need_id N1.1" in message
    assert "roster IDs missing from ledger" in message

    rows = _base_rows()
    rows[0]["need_id"] = "N9.9"
    message = _hard_message(rows)
    assert "IDs not in roster: N9.9" in message


def test_block_must_match_roster_block():
    rows = _base_rows()
    _row(rows, "N2.1")["block"] = "3"
    assert "block '3' does not match roster block '2'" in _hard_message(rows)


@pytest.mark.parametrize(
    ("need_id", "column", "bad_value", "fragment"),
    [
        ("N1.1", "statement_type", "bogus", "statement_type 'bogus'"),
        ("N1.1", "quote_verification", "guessed", "quote_verification 'guessed'"),
        ("N1.1", "rule_confidence", "high", "rule_confidence 'high'"),
        ("N1.1", "policy_driver", "FOO", "policy_driver 'FOO'"),
        ("N1.1", "policy_driver", "", "policy_driver is empty"),
        ("N1.1", "source_doc", "NOPE", "source_doc 'NOPE'"),
        ("N1.1", "source_doc", "", "source_doc is empty"),
        ("D1", "dtsc_tier", "bogus", "dtsc_tier 'bogus'"),
        ("N1.1", "block", "Q", "block 'Q'"),
        ("N1.1", "cell_rule", "", "cell_rule is empty"),
    ],
)
def test_enum_and_required_field_violations_are_hard_errors(need_id, column, bad_value, fragment):
    rows = _base_rows()
    _row(rows, need_id)[column] = bad_value
    assert fragment in _hard_message(rows)


@pytest.mark.parametrize(
    ("need_id", "group_id", "fragment"),
    [
        ("D3a", "", "group_id '' does not match roster rule 'D3'"),
        ("D6f", "D3", "group_id 'D3' does not match roster rule 'D6'"),
        ("N1.1", "D3", "group_id 'D3' does not match roster rule ''"),
        ("D1", "D9", "group_id 'D9' is not allowed"),
    ],
)
def test_group_id_rule_is_hard(need_id, group_id, fragment):
    rows = _base_rows()
    _row(rows, need_id)["group_id"] = group_id
    assert fragment in _hard_message(rows)


@pytest.mark.parametrize("need_id", ["D1", "DI3"])
def test_evidence_cols_required_for_d_and_di(need_id):
    rows = _base_rows()
    _row(rows, need_id)["evidence_cols"] = ""
    assert "evidence_cols is required for block" in _hard_message(rows)


def test_evidence_cols_not_required_for_other_blocks():
    rows = _base_rows()
    assert _row(rows, "N1.1")["evidence_cols"] == ""
    assert validate_need_ledger(rows, SYNTHETIC_TAXONOMY) == []


def test_literal_and_keyword_outside_taxonomy_are_hard_errors():
    rows = _base_rows()
    _row(rows, "N1.1")["cell_rule"] = "study_type = 'bogus_value' AND kw_unknown"
    _row(rows, "D1")["evidence_cols"] = "release_exposure: study_type IN ('not_a_type')"
    message = _hard_message(rows)
    assert "cell_rule literal 'bogus_value'" in message
    assert "cell_rule keyword flag 'kw_unknown'" in message
    assert "evidence_cols literal 'not_a_type'" in message


def test_all_hard_errors_are_listed_together():
    rows = _base_rows()
    _row(rows, "N1.1")["statement_type"] = "bogus"
    _row(rows, "N1.2")["quote_verification"] = "guessed"
    message = _hard_message(rows)
    assert "statement_type 'bogus'" in message
    assert "quote_verification 'guessed'" in message


# --- loading -----------------------------------------------------------------------------


def test_load_normalizes_none_whitespace_and_blank_rows(tmp_path):
    path = tmp_path / "ledger.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(list(COLUMNS))
    values = dict.fromkeys(COLUMNS, "x")
    values.update(need_id="N1.1", block="1", quote="\n  quoted text\n", notes="None")
    sheet.append([values[name] for name in COLUMNS])
    blank = [None] * len(COLUMNS)
    blank[0] = "None"
    blank[1] = None
    sheet.append(blank)
    sheet.append([])
    workbook.save(path)

    rows = load_need_ledger(path)

    assert len(rows) == 1
    assert rows[0]["quote"] == "quoted text"
    assert rows[0]["notes"] == ""
    assert list(rows[0].keys()) == list(COLUMNS)


# --- CSV and QC export -------------------------------------------------------------------


def test_csv_is_roster_ordered_lf_only_and_round_trips():
    rows = _base_rows()
    _row(rows, "N1.1")["title"] = 'Comma, "quote", and\nnewline'
    shuffled = list(reversed(rows))

    text = render_need_ledger_csv(shuffled)

    assert "\r" not in text
    assert text.endswith("\n")
    parsed = list(csv.reader(io.StringIO(text, newline="")))
    assert tuple(parsed[0]) == COLUMNS
    assert [record[0] for record in parsed[1:]] == list(ROSTER_ORDER)
    assert parsed[ROSTER_ORDER.index("N1.1") + 1][COLUMNS.index("title")] == (
        'Comma, "quote", and\nnewline'
    )


def test_csv_render_rejects_ids_outside_roster():
    rows = _base_rows()
    rows[0]["need_id"] = "N9.9"
    with pytest.raises(ValueError, match="outside the roster"):
        render_need_ledger_csv(rows)


def test_write_csv_uses_lf_and_utf8(tmp_path):
    path = tmp_path / "need_ledger.csv"
    rows = _base_rows()
    _row(rows, "N1.1")["title"] = "En dash – text"
    write_need_ledger_csv(rows, path)
    raw = path.read_bytes()
    assert b"\r\n" not in raw
    assert raw.decode("utf-8") == render_need_ledger_csv(rows)


def test_qc_report_has_required_text_and_no_quote_text():
    rows = _base_rows()
    _row(rows, "N1.1")["quote"] = "UNIQUE_QUOTE_MARKER"
    _row(rows, "N1.1")["paraphrase"] = "UNIQUE_PARAPHRASE_MARKER"
    report = render_need_ledger_qc(rows, [], "docs/x.xlsx", "ab" * 32, "scripts/x.py")

    assert REQUIRED_DISCREPANCY in report
    assert "UNIQUE_QUOTE_MARKER" not in report
    assert "UNIQUE_PARAPHRASE_MARKER" not in report
    assert "- SHA-256: `" + "ab" * 32 + "`" in report
    assert "| 1 | 11 |" in report
    assert "| 2 | 10 |" in report
    assert "| DI | 16 |" in report


def test_qc_report_counts_findings_by_kind():
    rows = _base_rows()
    _row(rows, "N1.1")["quote"] = " ".join(["word"] * 31)
    findings = validate_need_ledger(rows, SYNTHETIC_TAXONOMY)
    report = render_need_ledger_qc(rows, findings, "docs/x.xlsx", "0" * 64, "scripts/x.py")
    assert "- quote_length: 1" in report


# --- real companion file -----------------------------------------------------------------


def test_real_xlsx_loads_and_validates_with_no_hard_errors():
    rows = load_need_ledger(XLSX)
    assert len(rows) == EXPECTED_ROW_COUNT
    assert [row["need_id"] for row in rows] == list(ROSTER_ORDER)
    findings = validate_need_ledger(rows, load_taxonomy(TAXONOMY))
    kinds = {finding.split(":", 1)[0] for finding in findings}
    assert kinds <= {"quote_length", "pdf_page_empty", "driver_deviation", "source_doc_list"}
    assert "driver_deviation" not in kinds
    assert "pdf_page_empty" not in kinds


def test_committed_csv_and_qc_report_match_fresh_export(build_script):
    csv_text, qc_text = build_script.build_outputs()
    assert CSV_PATH.read_bytes() == csv_text.encode("utf-8")
    assert QC_PATH.read_bytes() == qc_text.encode("utf-8")
    assert build_script.main(["--check"]) == 0


def test_check_mode_exits_nonzero_when_committed_output_is_stale(
    build_script, tmp_path, monkeypatch
):
    stale_csv = tmp_path / "need_ledger.csv"
    stale_csv.write_text("stale\n", encoding="utf-8")
    monkeypatch.setattr(build_script, "CSV_PATH", stale_csv)
    assert build_script.main(["--check"]) == 1


def test_check_mode_exits_nonzero_when_output_is_missing(build_script, tmp_path, monkeypatch):
    monkeypatch.setattr(build_script, "QC_PATH", tmp_path / "missing.md")
    assert build_script.main(["--check"]) == 1
