"""Add-on A2 Need Ledger: load the companion XLSX, validate it, and render CSV and QC text.

The XLSX is the source of record and is never modified. Validation raises ValueError for
hard contract violations and returns non-blocking findings for the QC report.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import openpyxl
import yaml

SHEET_NAME = "Sheet1"
COLUMNS: tuple[str, ...] = (
    "need_id",
    "block",
    "policy_driver",
    "title",
    "paraphrase",
    "source_doc",
    "source_item",
    "pdf_page",
    "printed_label",
    "quote",
    "quote_verification",
    "statement_type",
    "cell_rule",
    "evidence_cols",
    "rule_confidence",
    "dtsc_tier",
    "aliases",
    "link_out_ids",
    "notes",
    "group_id",
)
BLOCKS: tuple[str, ...] = ("1", "2", "3", "4", "M", "X", "D", "DI", "DC")
POLICY_DRIVERS: tuple[str, ...] = ("OPC-2022", "MON-2026", "DTSC-SCP", "LEG")
SOURCE_DOCS: tuple[str, ...] = (
    "OPC2022",
    "MON2026",
    "DTSC_WP",
    "DTSC_BG2025",
    "DTSC_2023",
    "DTSC_LIST",
    "DTSC_RES",
)
QUOTE_VERIFICATIONS: tuple[str, ...] = ("direct_page_text", "analyst_transcribed")
STATEMENT_TYPES: tuple[str, ...] = (
    "management_question",
    "stated_gap",
    "recommended_activity",
    "dtsc_information_request",
    "dtsc_screening_statement",
    "listing_criterion",
    "extension_not_in_source",
)
RULE_CONFIDENCES: tuple[str, ...] = ("medium", "low")
DTSC_TIERS: tuple[str, ...] = ("narrowed", "initial_list", "footnote_evaluated")
GROUP_IDS: tuple[str, ...] = ("D3", "D6")
EVIDENCE_REQUIRED_BLOCKS: frozenset[str] = frozenset({"D", "DI"})
MAX_QUOTE_WORDS = 30

_BLOCK_IDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("1", tuple(f"N1.{n}" for n in range(1, 12))),
    ("2", tuple(f"N2.{n}" for n in range(1, 11))),
    ("3", tuple(f"N3.{n}" for n in range(1, 4))),
    ("4", tuple(f"N4.{n}" for n in range(1, 7))),
    ("M", tuple(f"M{n}" for n in range(1, 6))),
    ("X", ("X1", "X2")),
    (
        "D",
        (
            "D1",
            "D2",
            "D3a",
            "D3b",
            "D3c",
            "D4",
            "D5",
            "D6a",
            "D6b",
            "D6c",
            "D6d",
            "D6e",
            "D6f",
            "D7",
        ),
    ),
    ("DI", tuple(f"DI{n}" for n in range(1, 17))),
    ("DC", ("DC1", "DC2", "DC3")),
)
ROSTER_ORDER: tuple[str, ...] = tuple(rid for _, ids in _BLOCK_IDS for rid in ids)
ROSTER_BLOCK: dict[str, str] = {rid: block for block, ids in _BLOCK_IDS for rid in ids}
EXPECTED_ROW_COUNT = len(ROSTER_ORDER)
_ROSTER_INDEX: dict[str, int] = {rid: index for index, rid in enumerate(ROSTER_ORDER)}
_OPC_IDS = frozenset({"N1.8", "N2.1", "N2.4", "N3.3"})


def expected_drivers(need_id: str) -> frozenset[str]:
    """Return the policy drivers the roster notes assign to a roster ID."""
    block = ROSTER_BLOCK[need_id]
    if block == "X":
        return frozenset({"LEG"})
    if block in {"D", "DI", "DC"}:
        return frozenset({"DTSC-SCP"})
    if need_id in _OPC_IDS:
        return frozenset({"MON-2026", "OPC-2022"})
    return frozenset({"MON-2026"})


def expected_group_id(need_id: str) -> str:
    """Return the group_id the roster requires: D3a-D3c -> D3, D6a-D6f -> D6, else empty."""
    if re.fullmatch(r"D3[abc]", need_id):
        return "D3"
    if re.fullmatch(r"D6[a-f]", need_id):
        return "D6"
    return ""


_LITERAL = re.compile(r"'([^']*)'")
_KW_FLAG = re.compile(r"\bkw_[a-z0-9_]+\b")


def cell_rule_identifiers(rule: str) -> tuple[set[str], set[str]]:
    """Return (quoted literals, kw_ flag identifiers) used in a rule or evidence string."""
    return set(_LITERAL.findall(rule)), set(_KW_FLAG.findall(rule))


def _collect_list_strings(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        for value in node.values():
            found |= _collect_list_strings(value)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, str):
                found.add(item)
            else:
                found |= _collect_list_strings(item)
    return found


def taxonomy_vocabulary(taxonomy: Mapping[str, Any]) -> set[str]:
    """Union of every string inside a list in the add_on_a2 taxonomy section."""
    section = taxonomy.get("add_on_a2")
    if not isinstance(section, Mapping):
        raise ValueError("taxonomy has no add_on_a2 section")
    return _collect_list_strings(section)


def _normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return "" if text == "None" else text


def _split_list(value: str, separators: str = "|") -> list[str]:
    pattern = "[" + re.escape(separators) + "]"
    return [part.strip() for part in re.split(pattern, value) if part.strip()]


def load_need_ledger(xlsx_path: str | Path) -> list[dict[str, str]]:
    """Read the companion XLSX into normalized row dicts keyed by header name, in file order.

    Blank spreadsheet rows are skipped. Cell values are normalized: surrounding whitespace is
    stripped and None or the literal "None" becomes an empty string.
    """
    workbook = openpyxl.load_workbook(Path(xlsx_path), read_only=True, data_only=True)
    try:
        if SHEET_NAME not in workbook.sheetnames:
            raise ValueError(f"workbook has no sheet named {SHEET_NAME!r}")
        sheet_rows = workbook[SHEET_NAME].iter_rows(values_only=True)
        header_row = next(sheet_rows, None)
        if header_row is None:
            raise ValueError("workbook sheet is empty")
        header = [_normalize_cell(cell) for cell in header_row]
        rows: list[dict[str, str]] = []
        for raw in sheet_rows:
            values = [_normalize_cell(cell) for cell in raw]
            if not any(values):
                continue
            values += [""] * (len(header) - len(values))
            rows.append({name: values[index] for index, name in enumerate(header)})
        return rows
    finally:
        workbook.close()


def load_taxonomy(path: str | Path) -> dict[str, Any]:
    """Load taxonomy.yml as a dict (read-only use)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"taxonomy file is not a mapping: {path}")
    return data


def _label(row: Mapping[str, Any], index: int) -> str:
    need_id = _normalize_cell(row.get("need_id"))
    return need_id if need_id else f"row {index + 1}"


def _check_row(
    row: Mapping[str, Any],
    index: int,
    vocab: set[str],
    errors: list[str],
    findings: list[str],
) -> None:
    label = _label(row, index)
    cell = {name: _normalize_cell(row.get(name)) for name in COLUMNS}
    need_id = cell["need_id"]
    block = cell["block"]
    in_roster = need_id in ROSTER_BLOCK

    def hard(message: str) -> None:
        errors.append(f"{label}: {message}")

    if block not in BLOCKS:
        hard(f"block {block!r} is not one of {BLOCKS}")
    elif in_roster and block != ROSTER_BLOCK[need_id]:
        hard(f"block {block!r} does not match roster block {ROSTER_BLOCK[need_id]!r}")

    drivers = _split_list(cell["policy_driver"])
    if not drivers:
        hard("policy_driver is empty")
    for driver in drivers:
        if driver not in POLICY_DRIVERS:
            hard(f"policy_driver {driver!r} is not allowed")
    if drivers and in_roster and set(drivers) != expected_drivers(need_id):
        expected = "|".join(sorted(expected_drivers(need_id)))
        findings.append(
            f"driver_deviation: {label} has {'|'.join(drivers)}; roster note {expected}"
        )

    docs = _split_list(cell["source_doc"], "|;")
    if not docs:
        hard("source_doc is empty")
    for doc in docs:
        if doc not in SOURCE_DOCS:
            hard(f"source_doc {doc!r} is not allowed")
    if len(docs) > 1:
        findings.append(f"source_doc_list: {label} lists {len(docs)} source documents")

    if cell["quote_verification"] not in QUOTE_VERIFICATIONS:
        hard(f"quote_verification {cell['quote_verification']!r} is not allowed")
    if cell["statement_type"] not in STATEMENT_TYPES:
        hard(f"statement_type {cell['statement_type']!r} is not allowed")
    if cell["rule_confidence"] not in RULE_CONFIDENCES:
        hard(f"rule_confidence {cell['rule_confidence']!r} is not allowed")
    if cell["dtsc_tier"] not in ("", *DTSC_TIERS):
        hard(f"dtsc_tier {cell['dtsc_tier']!r} is not allowed")

    if cell["group_id"] not in ("", *GROUP_IDS):
        hard(f"group_id {cell['group_id']!r} is not allowed")
    elif cell["group_id"] != expected_group_id(need_id):
        hard(
            f"group_id {cell['group_id']!r} does not match roster rule "
            f"{expected_group_id(need_id)!r}"
        )

    if not cell["cell_rule"]:
        hard("cell_rule is empty")
    if block in EVIDENCE_REQUIRED_BLOCKS and not cell["evidence_cols"]:
        hard(f"evidence_cols is required for block {block}")

    for column in ("cell_rule", "evidence_cols"):
        literals, flags = cell_rule_identifiers(cell[column])
        for literal in sorted(literals):
            if literal not in vocab:
                hard(f"{column} literal {literal!r} is not in the add_on_a2 taxonomy")
        for flag in sorted(flags):
            if flag not in vocab:
                hard(f"{column} keyword flag {flag!r} is not in the add_on_a2 taxonomy")

    word_count = len(cell["quote"].split())
    if word_count > MAX_QUOTE_WORDS:
        findings.append(f"quote_length: {label} quote has {word_count} words")
    if not cell["pdf_page"] and block != "X":
        findings.append(f"pdf_page_empty: {label} has no pdf_page")
    if block == "X" and cell["link_out_ids"]:
        findings.append(f"link_out_on_x: {label} is an X row with link_out_ids")


def validate_need_ledger(
    rows: Sequence[Mapping[str, Any]], taxonomy: Mapping[str, Any]
) -> list[str]:
    """Validate ledger rows against the A2 contract.

    Raises ValueError listing every hard error. Returns non-blocking findings (strings of the
    form ``kind: detail``) for the QC report.
    """
    errors: list[str] = []
    findings: list[str] = []
    vocab = taxonomy_vocabulary(taxonomy)

    if not rows:
        errors.append("ledger has no rows")
    for index, row in enumerate(rows):
        if tuple(row.keys()) != COLUMNS:
            errors.append(f"row {index + 1}: columns differ from the 20-column contract order")
    if len(rows) != EXPECTED_ROW_COUNT:
        errors.append(f"row count is {len(rows)}; expected {EXPECTED_ROW_COUNT}")

    ids = [_normalize_cell(row.get("need_id")) for row in rows]
    counts = Counter(ids)
    for need_id in sorted(rid for rid, count in counts.items() if rid and count > 1):
        errors.append(f"duplicate need_id {need_id} appears {counts[need_id]} times")
    if counts[""]:
        errors.append(f"{counts['']} row(s) have an empty need_id")
    missing = sorted(set(ROSTER_ORDER) - set(counts))
    if missing:
        errors.append(f"roster IDs missing from ledger: {', '.join(missing)}")
    extra = sorted(set(counts) - set(ROSTER_ORDER) - {""})
    if extra:
        errors.append(f"IDs not in roster: {', '.join(extra)}")

    for index, row in enumerate(rows):
        _check_row(row, index, vocab, errors, findings)

    if errors:
        raise ValueError("Need Ledger failed validation:\n- " + "\n- ".join(errors))
    return findings


def render_need_ledger_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    """Render rows as CSV text in roster order with LF line endings and minimal quoting."""
    ids = [_normalize_cell(row.get("need_id")) for row in rows]
    unknown = sorted({rid for rid in ids if rid not in _ROSTER_INDEX})
    if unknown:
        raise ValueError(f"cannot order rows outside the roster: {unknown}")
    ordered = sorted(rows, key=lambda row: _ROSTER_INDEX[_normalize_cell(row.get("need_id"))])
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COLUMNS)
    for row in ordered:
        writer.writerow([_normalize_cell(row.get(name)) for name in COLUMNS])
    return buffer.getvalue()


def write_need_ledger_csv(rows: Sequence[Mapping[str, Any]], path: str | Path) -> None:
    """Write the rendered CSV as UTF-8 without a BOM and without platform newline translation."""
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        handle.write(render_need_ledger_csv(rows))


def render_need_ledger_qc(
    rows: Sequence[Mapping[str, Any]],
    findings: Sequence[str],
    source_label: str,
    source_sha256: str,
    generator: str,
) -> str:
    """Render the aggregate QC report. It contains no quote or paraphrase text."""
    lines: list[str] = [
        "# Need Ledger QC report (Add-on A2, EM-1)",
        "",
        f"Generator: `{generator}` (module `atlas.evidence.need_ledger`).",
        "Regenerate with `py -3.14 scripts/build_need_ledger.py`; do not edit by hand.",
        "",
        "## Input",
        "",
        f"- File: `{source_label}`",
        f"- SHA-256: `{source_sha256}`",
        f"- Rows: {len(rows)} (roster {EXPECTED_ROW_COUNT})",
        "- Hard validation errors: 0 (a failing run writes no output)",
        "",
        "## Row counts per block",
        "",
        "| Block | Rows |",
        "| --- | ---: |",
    ]
    block_counts = Counter(_normalize_cell(row.get("block")) for row in rows)
    for block in BLOCKS:
        lines.append(f"| {block} | {block_counts.get(block, 0)} |")

    def tally(column: str, allowed: Sequence[str]) -> None:
        counts = Counter(_normalize_cell(row.get(column)) for row in rows)
        lines.extend(["", f"### {column}", "", "| Value | Rows |", "| --- | ---: |"])
        for value in allowed:
            lines.append(f"| {value} | {counts.get(value, 0)} |")
        other = sum(count for value, count in counts.items() if value not in allowed)
        if other:
            lines.append(f"| (other) | {other} |")

    lines.extend(["", "## Enum tallies"])
    tally("statement_type", STATEMENT_TYPES)
    tally("quote_verification", QUOTE_VERIFICATIONS)
    tally("rule_confidence", RULE_CONFIDENCES)
    tally("source_doc", SOURCE_DOCS)

    lines.extend(["", "## Findings (non-blocking)", ""])
    if not findings:
        lines.append("None.")
    else:
        kinds = Counter(finding.split(":", 1)[0] for finding in findings)
        lines.extend(f"- {kind}: {kinds[kind]}" for kind in sorted(kinds))
        lines.extend(["", "Details:", ""])
        lines.extend(f"- {finding}" for finding in findings)

    lines.extend(
        [
            "",
            "## Documented source discrepancy",
            "",
            "The 2022 Strategy's Executive Summary states 22 recommended early actions and 13 "
            "research priorities (PDF 5). The Strategy has exactly 22 distinct early-action "
            "codes (PDF 22–24) and 14 distinct research-priority codes (Chapter 2B; PDF 30, "
            'repeated PDF 33–34). The atlas records "13" as a documented source discrepancy, '
            "hard-codes neither total in UI text, and does not speculate about the reason.",
            "",
        ]
    )
    return "\n".join(lines)
