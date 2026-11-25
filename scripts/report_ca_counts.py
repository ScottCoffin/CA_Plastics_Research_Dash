"""Reconcile the California work counts shown on the site and in the labels QC report (BQ-1.6).

Reads committed files only: no network, no builds, nothing under ``data/``. Every number comes
from one named JSON field or one labels_qc.md table row, so each value traces to a script and
field. The report also runs agreement checks. Differences that the committed counts cannot
explain are marked ``BUG?`` so they can be filed as possible bugs.

Usage: py -3.14 scripts/report_ca_counts.py [--json] [--root PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

METADATA = "site/data/california/build_metadata.json"
EXPLORE = "site/data/global/explore.json"
INDEX = "site/data/california/index.json"
TYPE_SUMMARY = "framework/src/california/index.md"
LABELS_QC = "docs/labels_qc.md"

# Values quoted in A3 section 2 (written 2026-11-18). They match the committed build of
# 2026-11-17 (commit 06b84555); the 2026-11-18 build (commit 67133b55) is one higher on each.
A3_VALUES = {
    "explorer": 1918,
    "plastic": 1582,
    "type_summary": 1848,
    "labels_label": 2036,
    "labels_plastic": 1748,
}

_NAMES_BLOCK = re.compile(r"const names = \{(.*?)\};", re.DOTALL)
_TYPE_KEY = re.compile(r'(?:"([\w-]+)"|\b([A-Za-z][\w-]*))\s*:\s*"')
_QC_ROW = re.compile(r"^\|\s*([^|\n]+?)\s*\|\s*([\d,]+)\s*\|\s*$", re.MULTILINE)


class CountSourceError(ValueError):
    """A committed input is missing, unreadable, or lacks a field this report reads."""


def _load_json(root: Path, rel: str) -> Any:
    path = root / rel
    if not path.is_file():
        raise CountSourceError(f"missing input file: {rel}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CountSourceError(f"unreadable JSON in {rel}: {exc}") from exc


def _node(doc: Any, rel: str, dotted: str) -> Any:
    node = doc
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise CountSourceError(f"{rel}: missing field {dotted}")
        node = node[part]
    return node


def _int(doc: Any, rel: str, dotted: str) -> int:
    node = _node(doc, rel, dotted)
    if isinstance(node, bool) or not isinstance(node, int):
        raise CountSourceError(f"{rel}: field {dotted} is not an integer")
    return node


def _type_names(root: Path) -> tuple[str, ...]:
    """Type keys named in the Now line (``const names`` in typeSummary on the California page)."""
    path = root / TYPE_SUMMARY
    if not path.is_file():
        raise CountSourceError(f"missing input file: {TYPE_SUMMARY}")
    block = _NAMES_BLOCK.search(path.read_text(encoding="utf-8"))
    if block is None:
        raise CountSourceError(f"{TYPE_SUMMARY}: no 'const names = {{...}}' map for typeSummary")
    names = tuple(quoted or bare for quoted, bare in _TYPE_KEY.findall(block.group(1)))
    if not names:
        raise CountSourceError(f"{TYPE_SUMMARY}: typeSummary names map is empty")
    return names


def _qc_counts(root: Path) -> dict[str, int]:
    path = root / LABELS_QC
    if not path.is_file():
        raise CountSourceError(f"missing input file: {LABELS_QC}")
    text = path.read_text(encoding="utf-8")
    return {label: int(value.replace(",", "")) for label, value in _QC_ROW.findall(text)}


def _qc_value(counts: dict[str, int], label: str) -> int:
    if label not in counts:
        raise CountSourceError(f"{LABELS_QC}: no table row '{label}'")
    return counts[label]


def _row(
    key: str, label: str, value: int, file: str, field: str, definition: str
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "a3": A3_VALUES.get(key),
        "file": file,
        "field": field,
        "definition": definition,
    }


def _check(name: str, status: str, detail: str) -> dict[str, str]:
    return {"check": name, "status": status, "detail": detail}


def collect(root: Path = ROOT) -> dict[str, Any]:
    """Read every count from its committed source and run the agreement checks."""
    root = Path(root)
    metadata = _load_json(root, METADATA)
    explore = _load_json(root, EXPLORE)
    index = _load_json(root, INDEX)
    qc = _qc_counts(root)
    type_names = _type_names(root)

    by_type = _node(metadata, METADATA, "flow.by_type")
    if not isinstance(by_type, dict) or not all(isinstance(n, int) for n in by_type.values()):
        raise CountSourceError(f"{METADATA}: flow.by_type is not a map of integers")
    works = index.get("works") if isinstance(index, dict) else None
    if not isinstance(works, list):
        raise CountSourceError(f"{INDEX}: field works is not a list")

    total_by_type = sum(by_type.values())
    shown = sum(n for t, n in by_type.items() if t in type_names)
    omitted = total_by_type - shown
    v = {
        "explorer": _int(explore, EXPLORE, "california.works"),
        "atlas_works": _int(metadata, METADATA, "counts.works"),
        "plastic": _int(metadata, METADATA, "counts.plastic_works"),
        "labeled": _int(metadata, METADATA, "counts.labeled_works"),
        "published": _int(metadata, METADATA, "flow.published"),
        "unique": _int(metadata, METADATA, "flow.unique_works"),
        "records": _int(metadata, METADATA, "flow.records_retrieved"),
        "no_ca": _int(metadata, METADATA, "flow.no_ca_authorship"),
        "removed": _int(metadata, METADATA, "flow.removed_by_curation"),
        "flow_plastic": _int(metadata, METADATA, "flow.plastic_related"),
        "not_plastic": _int(metadata, METADATA, "flow.not_plastic_related"),
        "curation_removed": _int(metadata, METADATA, "curation.works_removed"),
        "curation_listed": _int(metadata, METADATA, "curation.works_excluded_listed"),
        "index_works": _int(index, INDEX, "counts.works"),
        "index_rows": len(works),
        "index_plastic": sum(
            1 for w in works if isinstance(w, dict) and w.get("plastic_related") is True
        ),
        "qc_label": _qc_value(qc, "Label rows"),
        "qc_normalized": _qc_value(qc, "Normalized work rows"),
        "qc_raw": _qc_value(qc, "Raw OpenAlex work rows"),
        "qc_plastic": _qc_value(qc, "Plastic-related rows"),
    }

    rows = [
        _row(
            "explorer",
            "Explorer: California works",
            v["explorer"],
            EXPLORE,
            "california.works",
            "Published California works (all types, plastic-related or not), copied from "
            "counts.works when the explorer was built.",
        ),
        _row(
            "atlas_works",
            "California atlas: works",
            v["atlas_works"],
            METADATA,
            "counts.works",
            "Published works with a California author, after the California filter and curation.",
        ),
        _row(
            "plastic",
            "California page: plastic-related works",
            v["plastic"],
            METADATA,
            "counts.plastic_works",
            "Published California works whose final plastic_related flag is true.",
        ),
        _row(
            "type_summary",
            "California page: type breakdown (Now line)",
            shown,
            METADATA,
            "flow.by_type (types named in typeSummary)",
            "Published works of the ten named types, all plastic-related or not; the other "
            "types are summed in the line's last entry (CNT-2).",
        ),
        _row(
            "labels_label",
            "labels_qc: label rows",
            v["qc_label"],
            LABELS_QC,
            "Label rows",
            "One rule label row per unique work, California or not, before the California "
            "filter and curation.",
        ),
        _row(
            "labels_plastic",
            "labels_qc: plastic-related rows",
            v["qc_plastic"],
            LABELS_QC,
            "Plastic-related rows",
            "Unique works, California or not, that the keyword rule calls plastic-related, "
            "before owner review, model labels and overrides.",
        ),
        _row(
            "unique",
            "Unique works (normalized table)",
            v["unique"],
            METADATA,
            "flow.unique_works",
            "Works after OpenAlex duplicates are collapsed, before the California filter.",
        ),
        _row(
            "records",
            "Raw OpenAlex records",
            v["records"],
            METADATA,
            "flow.records_retrieved",
            "Raw records retrieved: unique works plus duplicates collapsed into them.",
        ),
        _row(
            "no_ca",
            "Dropped: no California author",
            v["no_ca"],
            METADATA,
            "flow.no_ca_authorship",
            "Unique works with no California authorship on any basis; not published.",
        ),
        _row(
            "removed",
            "Dropped: removed by curation",
            v["removed"],
            METADATA,
            "flow.removed_by_curation",
            "California works removed by curation; computed as unique minus no-CA minus published.",
        ),
        _row(
            "not_plastic",
            "Published, not plastic-related",
            v["not_plastic"],
            METADATA,
            "flow.not_plastic_related",
            "Published California works whose final plastic flag is not true.",
        ),
        _row(
            "omitted",
            "Now line: works of other types",
            omitted,
            METADATA,
            "flow.by_type (types not named)",
            "Published works of the types the Now line does not name, summed in its last "
            "entry (editorial, other, letter, and so on).",
        ),
        _row(
            "curation_listed",
            "Curation exclusions listed",
            v["curation_listed"],
            METADATA,
            "curation.works_excluded_listed",
            "Work overrides with exclude set to true; not every one removes a work.",
        ),
    ]

    non_published = v["unique"] - v["published"]
    plastic_gap = v["qc_plastic"] - v["plastic"]
    unmatched = v["curation_listed"] - v["curation_removed"] - v["no_ca"]
    checks = [
        _check(
            "Explorer California equals atlas works",
            "OK" if v["explorer"] == v["atlas_works"] else "DIFF",
            f"explore {v['explorer']} vs counts.works {v['atlas_works']}",
        ),
        _check(
            "Index works equal counts.works",
            "OK" if v["index_rows"] == v["index_works"] == v["atlas_works"] else "DIFF",
            f"index works list {v['index_rows']}, index counts.works {v['index_works']}, "
            f"counts.works {v['atlas_works']}",
        ),
        _check(
            "flow.published equals counts.works",
            "OK" if v["published"] == v["atlas_works"] else "DIFF",
            f"flow.published {v['published']} vs counts.works {v['atlas_works']}",
        ),
        _check(
            "Plastic works equal flow.plastic_related",
            "OK" if v["plastic"] == v["flow_plastic"] else "DIFF",
            f"counts.plastic_works {v['plastic']} vs flow.plastic_related {v['flow_plastic']}",
        ),
        _check(
            "Plastic works equal index plastic flags",
            "OK" if v["plastic"] == v["index_plastic"] else "DIFF",
            f"counts.plastic_works {v['plastic']} vs index works with plastic_related true "
            f"{v['index_plastic']}",
        ),
        _check(
            "Labeled works equal counts.works",
            "OK" if v["labeled"] == v["atlas_works"] else "DIFF",
            f"counts.labeled_works {v['labeled']} vs counts.works {v['atlas_works']}",
        ),
        _check(
            "By-type counts add to published",
            "OK" if total_by_type == v["published"] else "DIFF",
            f"sum of flow.by_type {total_by_type} vs flow.published {v['published']}",
        ),
        _check(
            "Flow adds up (unique - no-CA - curation = published)",
            "OK" if v["unique"] - v["no_ca"] - v["removed"] == v["published"] else "DIFF",
            f"{v['unique']} - {v['no_ca']} - {v['removed']} vs {v['published']}",
        ),
        _check(
            "Curation removals equal flow residual",
            "OK" if v["curation_removed"] == v["removed"] else "DIFF",
            f"curation.works_removed {v['curation_removed']} vs flow.removed_by_curation "
            f"{v['removed']}",
        ),
        _check(
            "Unique works equal labels_qc normalized rows",
            "OK" if v["unique"] == v["qc_normalized"] else "DIFF",
            f"flow.unique_works {v['unique']} vs labels_qc {v['qc_normalized']}",
        ),
        _check(
            "Raw records equal labels_qc raw rows",
            "OK" if v["records"] == v["qc_raw"] else "DIFF",
            f"flow.records_retrieved {v['records']} vs labels_qc {v['qc_raw']}",
        ),
        _check(
            "Label rows equal unique works",
            "OK" if v["qc_label"] == v["unique"] else "DIFF",
            f"labels_qc label rows {v['qc_label']} vs flow.unique_works {v['unique']}",
        ),
        _check(
            "Now line sums to the published total",
            "OK",
            f"{shown} named + {omitted} works of other types = {total_by_type} (CNT-2 remainder)",
        ),
        _check(
            "Plastic gap, labels_qc to published",
            "NOTE",
            f"gap {plastic_gap} ({v['qc_plastic']} - {v['plastic']}); net published works "
            f"flipped from rule to final not-plastic lie between {plastic_gap - non_published} "
            f"and {plastic_gap} (non-published works {non_published}); needs a per-work join",
        ),
        _check(
            "Listed exclusions reach a counted work",
            "BUG?" if unmatched > 0 else "OK",
            f"{v['curation_listed']} listed, {v['curation_removed']} removed, {v['no_ca']} "
            f"non-CA; at least {max(unmatched, 0)} listed exclusions match no work in the "
            "unique table",
        ),
    ]
    return {"rows": rows, "checks": checks}


def render(result: dict[str, Any]) -> str:
    """Markdown tables (ASCII only), suitable for pasting into docs."""
    lines = [
        "| Number | Today | A3 (2026-11-18) | Change | Source (file: field) | Definition |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in result["rows"]:
        a3 = "" if row["a3"] is None else f"{row['a3']:,}"
        change = "" if row["a3"] is None else f"{row['value'] - row['a3']:+,}"
        lines.append(
            f"| {row['label']} | {row['value']:,} | {a3} | {change} | "
            f"{row['file']}: {row['field']} | {row['definition']} |"
        )
    lines += ["", "| Status | Check | Detail |", "|---|---|---|"]
    for check in result["checks"]:
        lines.append(f"| {check['status']} | {check['check']} | {check['detail']} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print JSON instead of tables")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to read")
    args = parser.parse_args(argv)
    try:
        result = collect(args.root)
    except CountSourceError as exc:
        print(f"report_ca_counts: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
