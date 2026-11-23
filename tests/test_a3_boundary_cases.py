"""BQ-G7: boundary calibration cases for the A3 labelling guide (owner decision 2026-11-18)."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "curation" / "a3_boundary_cases.csv"
EXAMPLES = ROOT / "curation" / "a3_guide_examples.csv"
GUIDE = ROOT / "docs" / "LABELING_GUIDE_A3_ADDENDUM.md"
COLUMNS = [
    "case_id",
    "work_id",
    "doi",
    "citation",
    "plastics_centrality",
    "decided_by",
    "decided_at",
    "rationale",
    "evidence_quotes",
    "evidence_pages",
    "plastic_mention_pages",
    "source_pdf_zotero_key",
    "quote_check",
]
MAY_BE_EMPTY = {"work_id", "doi"}
CENTRALITY = {"primary", "substantial", "incidental", "none", "not_assessed"}
ZOTERO_KEYS = {"ashworth_2026": "QPEYMFCM", "foellmer_2022": "XL2RKVXT"}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_boundary_cases_have_exactly_the_two_owner_decided_cases() -> None:
    with CASES.open(encoding="utf-8", newline="") as handle:
        assert next(csv.reader(handle)) == COLUMNS
    assert [r["case_id"] for r in _rows(CASES)] == ["ashworth_2026", "foellmer_2022"]


def test_every_column_is_filled_except_identifiers_for_foellmer() -> None:
    for row in _rows(CASES):
        for column in COLUMNS:
            if column in MAY_BE_EMPTY and row["case_id"] == "foellmer_2022":
                continue
            assert row[column].strip(), (row["case_id"], column)


def test_centrality_is_a_guide_value_and_the_owner_decision() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    for row in _rows(CASES):
        value = row["plastics_centrality"]
        assert value in CENTRALITY, row["case_id"]
        assert f"`{value}`" in guide, row["case_id"]
        assert value == "incidental", row["case_id"]
        assert row["decided_by"] == "owner"
        assert row["decided_at"] == "2026-11-18"


def test_case_ids_match_the_guide_example_rows_and_copy_their_identifiers() -> None:
    guide_examples = {r["example_id"]: r for r in _rows(EXAMPLES) if r["role"] == "guide_example"}
    boundary = {k for k, r in guide_examples.items() if r["plastics_centrality"] == "incidental"}
    cases = _rows(CASES)
    assert {r["case_id"] for r in cases} <= set(guide_examples)
    assert {r["case_id"] for r in cases} == boundary
    for row in cases:
        example = guide_examples[row["case_id"]]
        for column in ("work_id", "doi", "citation", "plastics_centrality"):
            assert row[column] == example[column], (row["case_id"], column)
        assert row["source_pdf_zotero_key"] == ZOTERO_KEYS[row["case_id"]]


def test_each_quote_has_a_page_and_the_quote_check_note() -> None:
    for row in _rows(CASES):
        quotes = row["evidence_quotes"].split(" | ")
        pages = row["evidence_pages"].split("|")
        assert 2 <= len(quotes) <= 4, row["case_id"]
        assert len(pages) == len(quotes), row["case_id"]
        assert all(page.isdigit() for page in pages), row["case_id"]
        for quote in quotes:
            assert quote.startswith('"') and quote.endswith('"'), row["case_id"]
            assert len(quote.strip('"').split()) <= 40, row["case_id"]
        assert row["quote_check"] == "matched pdfminer text 2026-11-22"
