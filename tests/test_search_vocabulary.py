"""BQ-S1: the search vocabulary register is well formed and its doc counts match it (A3 §5.8)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "config" / "search_vocabulary_v1.yml"
DOC = ROOT / "docs" / "SEARCH_VOCABULARY.md"

COLUMNS = {
    "term",
    "language",
    "concept",
    "group",
    "tier",
    "source",
    "anchor_required",
    "handling",
    "in_v31",
    "probe_count_and_date",
    "risk",
}
TIERS = {"A", "B", "C", "D", "never_standalone"}
GROUPS = {
    "pollution",
    "lifecycle_and_society",
    "lens_evidence",
    "pollution_health_toxicology",
    "analytical_methods",
    "particle_descriptors",
}
HANDLINGS = {"core", "qualified", "title_only", "co_term", "lens_evidence", "exclude"}


def _register() -> dict:
    with REGISTER.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _rows() -> list[dict]:
    return _register()["terms"]


def _doc_counts(heading: str) -> dict[str, int]:
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = lines.index(heading)
    counts: dict[str, int] = {}
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] in {"Tier", "Group"} or set(cells[0]) <= {"-", ":"}:
            continue
        counts[cells[0]] = int(cells[1])
    return counts


def test_register_header() -> None:
    data = _register()
    assert data["version"] == "search_vocabulary_v1"
    assert data["generated_from"] == "docs/add_on_spec_3.md §§5.1, 5.5, 5.7, 5.10"
    assert data["note"] == "registering a term changes no query"
    assert _rows(), "register must list at least one term"


def test_every_row_has_exactly_the_spec_columns() -> None:
    for row in _rows():
        assert set(row) == COLUMNS, row.get("term")


def test_enumerated_values_are_valid() -> None:
    for row in _rows():
        assert row["tier"] in TIERS, row["term"]
        assert row["group"] in GROUPS, row["term"]
        assert row["handling"] in HANDLINGS, row["term"]
        assert isinstance(row["language"], str) and len(row["language"]) == 2, row["term"]
        assert isinstance(row["anchor_required"], bool), row["term"]
        assert isinstance(row["in_v31"], bool), row["term"]
        assert row["probe_count_and_date"] is None or isinstance(
            row["probe_count_and_date"], str
        ), row["term"]
        assert row["risk"] is None or isinstance(row["risk"], str), row["term"]


def test_tier_handling_and_source_are_non_empty() -> None:
    for row in _rows():
        for field in ("term", "tier", "handling", "source"):
            assert isinstance(row[field], str) and row[field].strip(), (row["term"], field)


def test_never_standalone_rows_are_never_core() -> None:
    for row in _rows():
        if row["tier"] == "never_standalone":
            assert row["handling"] in {"exclude", "co_term"}, row["term"]


def test_tier_c_is_never_queried() -> None:
    for row in _rows():
        if row["tier"] == "C":
            assert row["handling"] not in {"core", "qualified", "title_only"}, row["term"]
            assert row["handling"] in {"lens_evidence", "exclude"}, row["term"]


def test_tier_d_is_probe_only() -> None:
    for row in _rows():
        if row["tier"] == "D":
            assert row["handling"] == "qualified", row["term"]


def test_core_handling_is_only_for_v31_terms() -> None:
    for row in _rows():
        if row["handling"] == "core":
            assert row["in_v31"] is True, row["term"]


def test_anchor_required_follows_the_rule() -> None:
    for row in _rows():
        expected = row["tier"] != "C" and row["handling"] not in {"core", "exclude"}
        assert row["anchor_required"] is expected, row["term"]


def test_term_and_language_are_unique() -> None:
    keys = [(row["term"], row["language"]) for row in _rows()]
    assert len(keys) == len(set(keys))


def _expected_counts(allowed: set[str], field: str) -> dict[str, int]:
    expected = {value: 0 for value in allowed}
    expected.update(Counter(row[field] for row in _rows()))
    return expected


def test_doc_tier_counts_match_register() -> None:
    counted = _doc_counts("## Counts by tier")
    assert counted.pop("Total") == len(_rows())
    assert counted == _expected_counts(TIERS, "tier")


def test_doc_group_counts_match_register() -> None:
    counted = _doc_counts("## Counts by group")
    assert counted.pop("Total") == len(_rows())
    assert counted == _expected_counts(GROUPS, "group")
