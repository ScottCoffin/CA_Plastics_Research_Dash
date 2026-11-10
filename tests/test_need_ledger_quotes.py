"""Offline tests for the Add-on A2 need-ledger quote regression (EM-1). No real PDFs are used."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_need_ledger_quotes.py"
LEDGER_CSV = ROOT / "config" / "need_ledger.csv"

sys.path.insert(0, str(ROOT / "src"))

from atlas.evidence import quote_check as qc  # noqa: E402
from atlas.evidence.quote_check import (  # noqa: E402
    BAD_PAGE,
    MATCH_ELSEWHERE,
    MATCH_NEARBY,
    MATCH_ON_PAGE,
    MISSING_PDF,
    NOT_FOUND,
    NOT_PDF,
    best_fuzzy_ratio,
    build_pdf_paths,
    check_rows,
    load_source_map,
    normalize_text,
    parse_pdf_pages,
)


def _load_script():
    spec = importlib.util.spec_from_file_location("check_need_ledger_quotes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SCRIPT_MODULE = _load_script()


class FakeExtractor:
    """Stands in for pdfminer: serves page text from a dict and records every request."""

    def __init__(self, pages: dict[int, str], page_count: int | None = None) -> None:
        self.pages = pages
        self.page_count = page_count if page_count is not None else (max(pages) if pages else 0)
        self.calls: list[frozenset[int] | None] = []

    def __call__(self, path: Path, pages: frozenset[int] | None) -> dict[int, str]:
        self.calls.append(pages)
        wanted = range(1, self.page_count + 1) if pages is None else sorted(pages)
        return {page: self.pages[page] for page in wanted if page in self.pages}


@pytest.fixture
def pdf_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "pdfs"
    directory.mkdir()
    (directory / "mon.pdf").write_bytes(b"%PDF-1.4 placeholder")
    (directory / "bg.pdf").write_bytes(b"%PDF-1.4 placeholder")
    return directory


def _paths(pdf_dir: Path) -> dict[str, Path]:
    return {"MON2026": pdf_dir / "mon.pdf", "DTSC_BG2025": pdf_dir / "bg.pdf"}


def _row(need_id: str, pdf_page: str, quote: str, source_doc: str = "MON2026") -> dict[str, str]:
    return {"need_id": need_id, "source_doc": source_doc, "pdf_page": pdf_page, "quote": quote}


PAGES = {
    5: "Intro text. Most studies have been conducted along California's coasts.",
    6: "Methods continue here, and the sampling protocol is described in detail.",
    7: "Central Valley sites were sampled with a manta net in spring.",
    20: "Unrelated discussion of Lahontan basin reservoirs and sediment cores.",
}


# Normalization ---------------------------------------------------------------------------


def test_normalize_folds_quotes_dashes_case_and_whitespace() -> None:
    raw = "Coastal’s “data” – 2026—ok\n\n  Mixed   CASE"
    assert normalize_text(raw) == 'coastal\'s "data" - 2026-ok mixed case'


def test_normalize_joins_hyphenated_line_breaks_and_nfkc() -> None:
    assert normalize_text("micro-\nplastic and ﬁbers") == "microplastic and fibers"
    assert normalize_text("micro-\r\n   plastic") == "microplastic"


def test_normalize_removes_soft_hyphen() -> None:
    assert normalize_text("micro­plastic") == "microplastic"


# Page parsing ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("28", (28,)),
        ("151-152", (151, 152)),
        ("151–152", (151, 152)),
        ("6; 10", (6, 10)),
        ("68; 69; 76", (68, 69, 76)),
        ("36-37; 37", (36, 37)),
        ("12;", (12,)),
    ],
)
def test_parse_pdf_pages_accepts_single_ranges_and_lists(
    value: str, expected: tuple[int, ...]
) -> None:
    assert parse_pdf_pages(value) == expected


@pytest.mark.parametrize("value", ["", "  ", "abc", "0", "9-7", "3-", "p. 4", "; ;", "-2"])
def test_parse_pdf_pages_rejects_unparseable_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_pdf_pages(value)


def test_every_committed_ledger_pdf_page_parses() -> None:
    with LEDGER_CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    for row in rows:
        if row["source_doc"] in qc.WEB_SOURCE_DOCS:
            continue
        parse_pdf_pages(row["pdf_page"])


# Statuses --------------------------------------------------------------------------------


def test_match_on_page(pdf_dir: Path) -> None:
    extractor = FakeExtractor(PAGES)
    (result,) = check_rows(
        [_row("N1.1", "5", "Most studies have been conducted along California's coasts")],
        _paths(pdf_dir),
        extractor,
    )
    assert result["status"] == MATCH_ON_PAGE
    assert result["matched_pages"] == [5]
    assert result["ratio"] is None


def test_match_on_page_across_adjacent_pages_in_a_range(pdf_dir: Path) -> None:
    quote = "conducted along California's coasts. Methods continue here"
    (result,) = check_rows([_row("N1.2", "5-6", quote)], _paths(pdf_dir), FakeExtractor(PAGES))
    assert result["status"] == MATCH_ON_PAGE
    assert result["matched_pages"] == [5, 6]


def test_match_nearby_reports_page_drift(pdf_dir: Path) -> None:
    (result,) = check_rows(
        [_row("N1.3", "5", "manta net in spring")], _paths(pdf_dir), FakeExtractor(PAGES)
    )
    assert result["status"] == MATCH_NEARBY
    assert result["matched_pages"] == [7]


def test_match_elsewhere_when_outside_the_nearby_window(pdf_dir: Path) -> None:
    (result,) = check_rows(
        [_row("N1.4", "5", "Lahontan basin reservoirs")], _paths(pdf_dir), FakeExtractor(PAGES)
    )
    assert result["status"] == MATCH_ELSEWHERE
    assert result["matched_pages"] == [20]


def test_not_found_reports_best_fuzzy_ratio(pdf_dir: Path) -> None:
    listed = "Central Valley sites were sampled with a manta net in autumn"
    (result,) = check_rows([_row("N1.5", "7", listed)], _paths(pdf_dir), FakeExtractor(PAGES))
    assert result["status"] == NOT_FOUND
    assert result["matched_pages"] == []
    assert 0.9 < result["ratio"] < 1.0


def test_not_found_with_unrelated_quote_has_low_ratio(pdf_dir: Path) -> None:
    (result,) = check_rows(
        [_row("N1.6", "7", "Quantum chromodynamics lattice gauge simulations")],
        _paths(pdf_dir),
        FakeExtractor(PAGES),
    )
    assert result["status"] == NOT_FOUND
    assert result["ratio"] < 0.6


def test_empty_quote_is_not_found_not_a_match(pdf_dir: Path) -> None:
    (result,) = check_rows([_row("N1.7", "5", "   ")], _paths(pdf_dir), FakeExtractor(PAGES))
    assert result["status"] == NOT_FOUND
    assert result["ratio"] == 0.0


def test_missing_pdf_when_map_has_no_entry_or_file_absent(pdf_dir: Path) -> None:
    extractor = FakeExtractor(PAGES)
    no_entry = _row("D1", "5", "anything", source_doc="DTSC_2023")
    (result,) = check_rows([no_entry], _paths(pdf_dir), extractor)
    assert result["status"] == MISSING_PDF
    absent = {"MON2026": pdf_dir / "gone.pdf"}
    (result,) = check_rows([_row("N1.8", "5", "anything")], absent, extractor)
    assert result["status"] == MISSING_PDF
    assert extractor.calls == []


def test_web_sources_are_not_pdf_and_skip_extraction(pdf_dir: Path) -> None:
    extractor = FakeExtractor(PAGES)
    rows = [_row("D7", "1", "web quote", "DTSC_LIST"), _row("D8", "1", "web quote", "DTSC_RES")]
    results = check_rows(rows, _paths(pdf_dir), extractor)
    assert [result["status"] for result in results] == [NOT_PDF, NOT_PDF]
    assert extractor.calls == []


@pytest.mark.parametrize("value", ["abc", "0", "9-7", ""])
def test_unparseable_page_is_bad_page(pdf_dir: Path, value: str) -> None:
    (result,) = check_rows([_row("N1.9", value, "x")], _paths(pdf_dir), FakeExtractor(PAGES))
    assert result["status"] == BAD_PAGE


def test_listed_pages_beyond_document_end_are_bad_page(pdf_dir: Path) -> None:
    (result,) = check_rows(
        [_row("N1.10", "500", "anything")], _paths(pdf_dir), FakeExtractor(PAGES, page_count=20)
    )
    assert result["status"] == BAD_PAGE


def test_extraction_is_lazy_and_limited_to_needed_pages(pdf_dir: Path) -> None:
    extractor = FakeExtractor(PAGES, page_count=20)
    check_rows([_row("N1.11", "5", "Most studies have been conducted")], _paths(pdf_dir), extractor)
    assert extractor.calls == [frozenset({5})]
    extractor = FakeExtractor(PAGES, page_count=20)
    check_rows([_row("N1.11b", "5", "manta net in spring")], _paths(pdf_dir), extractor)
    assert extractor.calls == [frozenset({5}), frozenset({3, 4, 6, 7})]


def test_whole_document_is_extracted_only_when_nearby_fails(pdf_dir: Path) -> None:
    extractor = FakeExtractor(PAGES, page_count=20)
    check_rows([_row("N1.12", "5", "Lahontan basin reservoirs")], _paths(pdf_dir), extractor)
    assert None in extractor.calls
    assert extractor.calls.count(None) == 1


def test_documents_are_cached_across_rows(pdf_dir: Path) -> None:
    extractor = FakeExtractor(PAGES, page_count=20)
    rows = [_row("N1.13", "5", "Most studies"), _row("N1.14", "5", "manta net in spring")]
    check_rows(rows, _paths(pdf_dir), extractor)
    # Page 5 is extracted once for both rows; the second row only adds its window pages.
    assert extractor.calls == [frozenset({5}), frozenset({3, 4, 6, 7})]


def test_fuzzy_ratio_helper_bounds() -> None:
    assert best_fuzzy_ratio("abc def", "xx abc def yy") == 1.0
    assert best_fuzzy_ratio("", "text") == 0.0
    assert best_fuzzy_ratio("quote", "") == 0.0
    assert 0.0 < best_fuzzy_ratio("quick brown fox jumps", "a slow brown fox leaps over it") < 1.0


# Mapping and paths -----------------------------------------------------------------------


def test_source_map_json_and_template_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"MON2026": "mon.pdf"}), encoding="utf-8")
    assert load_source_map(path) == {"MON2026": "mon.pdf"}
    template = json.loads(qc.map_template_json())
    assert set(template) == set(qc.PDF_SOURCE_DOCS)
    assert "DTSC_LIST" not in template and "DTSC_RES" not in template


def test_source_map_rejects_web_or_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"DTSC_LIST": "x.pdf"}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_source_map(path)


def test_source_map_yaml(tmp_path: Path) -> None:
    path = tmp_path / "map.yml"
    path.write_text("MON2026: mon.pdf\n", encoding="utf-8")
    assert load_source_map(path) == {"MON2026": "mon.pdf"}


def test_build_pdf_paths_rejects_names_escaping_the_directory(pdf_dir: Path) -> None:
    with pytest.raises(ValueError):
        build_pdf_paths({"MON2026": "../escape.pdf"}, pdf_dir)
    with pytest.raises(ValueError):
        build_pdf_paths({"MON2026": "sub/mon.pdf"}, pdf_dir)


# Report and script -----------------------------------------------------------------------

SENTINEL_QUOTE = "ZEBRA-QUOTE-SENTINEL-4471 with words"
SENTINEL_PAGE = "PAGE-TEXT-SENTINEL-9902 about coastal sampling"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    columns = ["need_id", "source_doc", "pdf_page", "quote"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in columns})
    return path


def _write_map(path: Path) -> Path:
    path.write_text(json.dumps({"MON2026": "mon.pdf", "DTSC_BG2025": "bg.pdf"}), encoding="utf-8")
    return path


def test_script_skips_without_pdf_dir_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.delenv("ATLAS_A2_PDF_DIR", raising=False)
    report = tmp_path / "report.json"
    assert SCRIPT_MODULE.main(["--strict", "--report", str(report)]) == 0
    assert "skipped (no local PDFs)" in capsys.readouterr().out
    assert not report.exists()


def test_script_env_var_selects_pdf_dir(
    monkeypatch: pytest.MonkeyPatch, pdf_dir: Path, tmp_path: Path
) -> None:
    csv_path = _write_csv(tmp_path / "ledger.csv", [_row("N1.1", "5", "Most studies")])
    monkeypatch.setenv("ATLAS_A2_PDF_DIR", str(pdf_dir))
    code = SCRIPT_MODULE.main(
        [
            "--map",
            str(_write_map(tmp_path / "map.json")),
            "--csv",
            str(csv_path),
            "--report",
            str(tmp_path / "r.json"),
        ],
        extractor=FakeExtractor(PAGES),
    )
    assert code == 0


def test_script_write_map_template_prints_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert SCRIPT_MODULE.main(["--write-map-template"]) == 0
    template = json.loads(capsys.readouterr().out)
    assert "MON2026" in template and "DTSC_LIST" not in template


@pytest.mark.parametrize(
    ("rows", "strict", "expected"),
    [
        ([_row("N1.1", "5", "Most studies")], True, 0),
        ([_row("N1.3", "5", "manta net in spring")], True, 0),  # match_nearby is not a failure
        ([_row("N1.4", "5", "Lahontan basin reservoirs")], True, 1),  # match_elsewhere fails strict
        ([_row("N1.4", "5", "Lahontan basin reservoirs")], False, 0),
        ([_row("N1.5", "7", "manta net in autumn, unseen wording here")], True, 1),
        ([_row("N1.5", "7", "manta net in autumn, unseen wording here")], False, 0),
        ([_row("N1.9", "abc", "x")], True, 1),
        ([_row("D7", "1", "x", "DTSC_LIST")], True, 0),
    ],
)
def test_script_strict_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    pdf_dir: Path,
    tmp_path: Path,
    rows: list[dict[str, str]],
    strict: bool,
    expected: int,
) -> None:
    monkeypatch.delenv("ATLAS_A2_PDF_DIR", raising=False)
    csv_path = _write_csv(tmp_path / "ledger.csv", rows)
    argv = [
        "--pdf-dir",
        str(pdf_dir),
        "--map",
        str(_write_map(tmp_path / "map.json")),
        "--csv",
        str(csv_path),
        "--report",
        str(tmp_path / "r.json"),
    ]
    if strict:
        argv.append("--strict")
    code = SCRIPT_MODULE.main(argv, extractor=FakeExtractor(PAGES, page_count=20))
    assert code == expected


def test_script_report_contains_statuses_but_no_quote_or_page_text(
    pdf_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pages = {5: SENTINEL_PAGE, 9: "something else"}
    rows = [_row("N1.1", "5", SENTINEL_QUOTE), _row("N1.2", "5", "nothing matches at all here")]
    csv_path = _write_csv(tmp_path / "ledger.csv", rows)
    report_path = tmp_path / "report.json"
    code = SCRIPT_MODULE.main(
        [
            "--pdf-dir",
            str(pdf_dir),
            "--map",
            str(_write_map(tmp_path / "map.json")),
            "--csv",
            str(csv_path),
            "--report",
            str(report_path),
        ],
        extractor=FakeExtractor(pages, page_count=12),
    )
    assert code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "ZEBRA" not in text and "SENTINEL" not in text and "something else" not in text
    report = json.loads(text)
    assert report["counts"][NOT_FOUND] == 2
    assert {row["need_id"] for row in report["rows"]} == {"N1.1", "N1.2"}
    assert set(report["rows"][0]) == {
        "need_id",
        "source_doc",
        "status",
        "pages",
        "matched_pages",
        "ratio",
    }
    assert "ZEBRA" not in capsys.readouterr().out


def test_script_rejects_pdf_dir_without_map(
    monkeypatch: pytest.MonkeyPatch, pdf_dir: Path, tmp_path: Path
) -> None:
    monkeypatch.delenv("ATLAS_A2_PDF_DIR", raising=False)
    assert (
        SCRIPT_MODULE.main(["--pdf-dir", str(pdf_dir), "--report", str(tmp_path / "r.json")]) == 2
    )


def test_default_extractor_reads_only_requested_pages_from_a_real_pdf(tmp_path: Path) -> None:
    """End-to-end check of the pdfminer path on a generated two-page PDF."""
    pdf = tmp_path / "two_pages.pdf"
    pdf.write_bytes(_two_page_pdf(["First page words", "Second page words"]))
    text = qc.pdfminer_page_extractor(pdf, frozenset({2}))
    assert set(text) == {2}
    assert "Second page words" in text[2]
    assert qc.pdfminer_page_extractor(pdf, frozenset()) == {}
    everything = qc.pdfminer_page_extractor(pdf, None)
    assert set(everything) == {1, 2}


def _two_page_pdf(page_texts: list[str]) -> bytes:
    """Build a minimal valid PDF with one Helvetica text line per page."""
    objects: list[bytes] = []
    count = len(page_texts)
    kids = " ".join(f"{3 + 2 * index} 0 R" for index in range(count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode())
    font_id = 3 + 2 * count
    for index, text in enumerate(page_texts):
        page_id = 3 + 2 * index
        content_id = page_id + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    out += trailer.encode()
    return bytes(out)
