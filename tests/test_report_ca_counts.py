"""BQ-1.6: California count reconciliation reads the right fields and fails loudly on gaps."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "report_ca_counts.py"

TYPE_NAMES = (
    "article",
    "review",
    "conference-paper",
    "preprint",
    "book-chapter",
    "conference-abstract",
    "dataset",
    "dissertation",
    "report",
    "book",
)

TYPE_SUMMARY_JS = """# California

```js
function typeSummary(byType) {
  const names = {article: "articles", review: "reviews",
    "conference-paper": "conference papers", preprint: "preprints",
    "book-chapter": "book chapters", "conference-abstract": "conference abstracts",
    dataset: "datasets", dissertation: "theses and dissertations",
    report: "reports", book: "books"};
  return names;
}
```
"""

LABELS_QC = """# Provisional work-label QC

| Check | Count |
|---|---:|
| Normalized work rows | 10 |
| Label rows | 10 |
| Raw OpenAlex work rows | 12 |
| Plastic-related rows | 6 |
"""


def _runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("report_ca_counts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


report = _runner()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(root: Path, rel: str, doc: dict) -> None:
    _write(root, rel, json.dumps(doc))


def _tree(root: Path) -> Path:
    """A small, internally consistent fixture: 10 unique, 2 no-CA, 1 curated, 7 published."""
    _write_json(
        root,
        "site/data/build_metadata.json",
        {
            "counts": {"works": 7, "plastic_works": 5, "labeled_works": 7},
            "flow": {
                "unique_works": 10,
                "records_retrieved": 12,
                "duplicates_collapsed": 2,
                "no_ca_authorship": 2,
                "removed_by_curation": 1,
                "published": 7,
                "plastic_related": 5,
                "not_plastic_related": 2,
                "by_type": {"article": 4, "review": 2, "editorial": 1},
            },
            "curation": {"works_removed": 1, "works_excluded_listed": 1},
        },
    )
    _write_json(root, "site/data/global/explore.json", {"california": {"cells": [], "works": 7}})
    _write_json(
        root,
        "site/data/index.json",
        {
            "counts": {"works": 7},
            "works": [{"work_id": f"W{i}", "plastic_related": i < 5} for i in range(7)],
        },
    )
    _write(root, "docs/labels_qc.md", LABELS_QC)
    _write(root, "framework/src/california/index.md", TYPE_SUMMARY_JS)
    return root


def _rows(result: dict) -> dict[str, dict]:
    return {row["key"]: row for row in result["rows"]}


def _status(result: dict, name: str) -> str:
    return next(c["status"] for c in result["checks"] if c["check"] == name)


def _edit(root: Path, rel: str, mutate) -> None:
    path = root / rel
    if path.suffix == ".json":
        doc = json.loads(path.read_text(encoding="utf-8"))
        mutate(doc)
        path.write_text(json.dumps(doc), encoding="utf-8")
    else:
        path.write_text(mutate(path.read_text(encoding="utf-8")), encoding="utf-8")


def test_each_value_is_read_from_its_named_field(tmp_path: Path) -> None:
    rows = _rows(report.collect(_tree(tmp_path)))

    assert rows["explorer"]["value"] == 7
    assert rows["explorer"]["file"] == "site/data/global/explore.json"
    assert rows["explorer"]["field"] == "california.works"
    assert rows["plastic"]["value"] == 5
    assert rows["plastic"]["field"] == "counts.plastic_works"
    assert rows["type_summary"]["value"] == 6  # article 4 + review 2; editorial is not named
    assert rows["omitted"]["value"] == 1
    assert rows["labels_label"]["value"] == 10
    assert rows["labels_plastic"]["value"] == 6
    assert rows["labels_plastic"]["file"] == "docs/labels_qc.md"
    assert rows["unique"]["value"] == 10
    assert rows["removed"]["value"] == 1
    assert rows["curation_listed"]["field"] == "curation.works_excluded_listed"


def test_a3_snapshot_values_are_attached_to_the_five_headline_rows(tmp_path: Path) -> None:
    rows = _rows(report.collect(_tree(tmp_path)))

    assert rows["explorer"]["a3"] == 1918
    assert rows["plastic"]["a3"] == 1582
    assert rows["type_summary"]["a3"] == 1848
    assert rows["labels_label"]["a3"] == 2036
    assert rows["labels_plastic"]["a3"] == 1748
    assert rows["atlas_works"]["a3"] is None


def test_type_names_come_from_the_california_page_map(tmp_path: Path) -> None:
    assert report._type_names(_tree(tmp_path)) == TYPE_NAMES


def test_real_repo_type_map_matches_the_expected_names() -> None:
    assert report._type_names(ROOT) == TYPE_NAMES


def test_disagreeing_sources_are_reported_as_diff(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _edit(root, "site/data/global/explore.json", lambda d: d["california"].update(works=999))

    result = report.collect(root)

    assert _status(result, "Explorer California equals atlas works") == "DIFF"


def test_plastic_row_reads_counts_not_flow(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _edit(root, "site/data/build_metadata.json", lambda d: d["counts"].update(plastic_works=4))

    result = report.collect(root)

    assert _rows(result)["plastic"]["value"] == 4
    assert _status(result, "Plastic works equal flow.plastic_related") == "DIFF"


def test_unexplained_exclusions_are_flagged_as_possible_bug(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _edit(
        root,
        "site/data/build_metadata.json",
        lambda d: d["curation"].update(works_excluded_listed=10),
    )

    result = report.collect(root)

    assert _status(result, "Listed exclusions reach a counted work") == "BUG?"
    detail = next(c["detail"] for c in result["checks"] if c["check"].startswith("Listed"))
    assert "at least 7 listed exclusions" in detail


def test_plastic_gap_is_reported_as_a_range(tmp_path: Path) -> None:
    result = report.collect(_tree(tmp_path))

    detail = next(c["detail"] for c in result["checks"] if c["check"].startswith("Plastic gap"))
    # gap 6 - 5 = 1; non-published 10 - 7 = 3, so the net flip lies between -2 and 1.
    assert "between -2 and 1" in detail


def test_missing_file_is_a_clear_error(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _tree(tmp_path)
    (root / "site/data/global/explore.json").unlink()

    with pytest.raises(report.CountSourceError, match="site/data/global/explore.json"):
        report.collect(root)

    assert report.main(["--root", str(root)]) == 2
    assert "missing input file: site/data/global/explore.json" in capsys.readouterr().err


def test_missing_field_is_a_clear_error(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _edit(root, "site/data/build_metadata.json", lambda d: d["flow"].pop("published"))

    with pytest.raises(report.CountSourceError, match="missing field flow.published"):
        report.collect(root)


def test_missing_labels_row_is_a_clear_error(tmp_path: Path) -> None:
    root = _tree(tmp_path)
    _edit(
        root,
        "docs/labels_qc.md",
        lambda text: text.replace("| Plastic-related rows | 6 |\n", ""),
    )

    with pytest.raises(report.CountSourceError, match="no table row 'Plastic-related rows'"):
        report.collect(root)


def test_json_output_and_table_are_ascii(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    root = _tree(tmp_path)

    assert report.main(["--root", str(root), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"][0]["value"] == 7
    assert {"rows", "checks"} == set(payload)

    table = report.render(report.collect(root))
    table.encode("ascii")  # raises if the console-unsafe characters creep in
    assert "| California page: plastic-related works | 5 | 1,582 | -1,577 |" in table


PAGE = ROOT / "framework" / "src" / "california" / "index.md"

# The Now line is the California page's own typeSummary, run in a fresh VM with formatCount
# standing in for the atlas.js import. Prints one JSON string (or null) per input map.
NOW_LINE_CHECK = r"""
"use strict";
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2], "utf8");
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const context = { formatCount: (value) => new Intl.NumberFormat("en-US").format(value) };
const typeSummary = vm.runInNewContext(`${source}\ntypeSummary`, context);
console.log(JSON.stringify(cases.map((byType) => typeSummary(byType))));
"""


def _type_summary_source() -> str:
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("function typeSummary(byType) {")
    return text[start : text.index("\n}\n", start) + 3]


def test_now_line_sums_unnamed_types_into_a_last_remainder_entry(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not on PATH; install Node.js 20+ to run the Now-line check.")
    cases = [
        {"article": 4, "review": 2, "editorial": 1},
        {"editorial": 41, "other": 18, "review": 9, "letter": 5, "article": 4, "data-paper": 0},
        {"article": 1416, "editorial": 1},
        {"editorial": 1000, "letter": 0},
        {"editorial": 0, "other": 0},
        None,
    ]
    expected = [
        "Now, all published works: 4 articles · 2 reviews · 1 work of other types.",
        "Now, all published works: 9 reviews · 4 articles · 64 works of other types.",
        "Now, all published works: 1,416 articles · 1 work of other types.",
        "Now, all published works: 1,000 works of other types.",
        None,
        None,
    ]
    source = tmp_path / "typeSummary.js"
    source.write_text(_type_summary_source(), encoding="utf-8")
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(json.dumps(cases), encoding="utf-8")
    script = tmp_path / "now_line_check.cjs"
    script.write_text(NOW_LINE_CHECK, encoding="utf-8")

    out = subprocess.run(
        [node, str(script), str(source), str(cases_file)],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout

    assert json.loads(out) == expected
