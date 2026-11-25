"""Report override rows that match no work, and plan the CNT-1 carry-forward.

Read-only and offline. Every row of ``curation/overrides_works.csv`` is placed against:

* ``data/processed/normalized/works.parquet``: unique works after duplicate collapse;
  ``duplicate_work_ids`` lists the OpenAlex IDs folded into each keeper.
* ``data/interim/works_raw.parquet``: the raw OpenAlex pull (``openalex_id``, ``raw_json``).
* ``site/data/california/index.json``: the published works.

Classes for ``exclude`` rows:

* ``applied``: in normalized, California, and not published (the exclusion took effect).
* ``ca_still_published``: in normalized, California, still published (export not rebuilt).
* ``non_ca``: in normalized but not California (dropped before curation).
* ``collapsed_duplicate``: the ID is folded into a keeper's ``duplicate_work_ids``.
* ``in_raw_only``: in the raw pull, but neither normalized nor a collapsed duplicate.
* ``not_in_corpus``: in neither the raw pull nor the normalized table.

Other fields use the same placement classes, without the published check, and are
reported separately.

CNT-1 carry-forward (planned here; written only by a separate, explicit step): a
collapsed duplicate whose keeper is published and has no exclude row gets an exclude row
for the keeper, unless the keeper's title differs from the duplicate's title. Such rows
are flagged for the owner instead.

Usage: py -3.14 scripts/report_unmatched_overrides.py [--json]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "curation" / "overrides_works.csv"
NORMALIZED = ROOT / "data" / "processed" / "normalized" / "works.parquet"
RAW = ROOT / "data" / "interim" / "works_raw.parquet"
INDEX = ROOT / "site" / "data" / "california" / "index.json"

HEADER = ["work_id", "field", "value", "reason", "reviewed_by", "reviewed_at"]
OPENALEX_PREFIX = "https://openalex.org/"
AUDIT_MARKER = "AT-1 owner audit label"
CARRY_REVIEWER = "agent-CNT-1"
CARRY_DATE = "2026-11-22"
CANONICAL_ID = re.compile(r"W\d+")

CLASSES = (
    "applied",
    "ca_still_published",
    "non_ca",
    "collapsed_duplicate",
    "in_raw_only",
    "not_in_corpus",
)
FLAG_ACTIONS = ("flag_title", "flag_title_missing", "flag_multiple_keepers")


@dataclass(frozen=True)
class OverrideRow:
    line: int
    work_id: str
    field: str
    value: str
    reason: str
    reviewed_by: str
    reviewed_at: str


@dataclass(frozen=True)
class Finding:
    line: int
    work_id: str
    field: str
    reason: str
    klass: str
    keeper: str = ""
    keeper_published: bool | None = None
    keeper_excluded: bool | None = None
    title_old: str = ""
    title_keeper: str = ""
    action: str = "keep"


@dataclass(frozen=True)
class Corpus:
    works: Mapping[str, Mapping[str, Any]]
    keepers: Mapping[str, tuple[str, ...]]
    raw_json: Mapping[str, str]
    published: frozenset[str]


def compact_id(value: object) -> str:
    """Strip whitespace and the OpenAlex URL prefix (any case)."""
    text = str(value or "").strip()
    if text[: len(OPENALEX_PREFIX)].lower() == OPENALEX_PREFIX:
        text = text[len(OPENALEX_PREFIX) :]
    return text


def match_key(value: object) -> str:
    """Key used for matching: compact form, upper case."""
    return compact_id(value).upper()


def title_key(text: str) -> str:
    """Lower case, punctuation removed, whitespace collapsed."""
    return " ".join(re.sub(r"[^\w\s]", "", text.casefold()).split())


def read_override_rows(path: Path) -> list[OverrideRow]:
    rows: list[OverrideRow] = []
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != HEADER:
            raise ValueError(f"{path}: header must be {','.join(HEADER)}")
        for record in reader:
            rows.append(
                OverrideRow(
                    line=reader.line_num,
                    work_id=record["work_id"] or "",
                    field=record["field"] or "",
                    value=record["value"] or "",
                    reason=record["reason"] or "",
                    reviewed_by=record["reviewed_by"] or "",
                    reviewed_at=record["reviewed_at"] or "",
                )
            )
    return rows


def build_corpus(
    normalized: Sequence[Mapping[str, Any]],
    raw: Sequence[Mapping[str, Any]],
    published_ids: Sequence[object],
) -> Corpus:
    works: dict[str, dict[str, Any]] = {}
    keepers: dict[str, list[str]] = {}
    for row in normalized:
        key = match_key(row.get("work_id"))
        works[key] = {
            "work_id": compact_id(row.get("work_id")),
            "title": str(row.get("title") or ""),
            "ca": bool(row.get("ca_any_author")),
        }
        for duplicate in row.get("duplicate_work_ids") or []:
            keepers.setdefault(match_key(duplicate), []).append(key)
    raw_json = {match_key(row.get("openalex_id")): str(row.get("raw_json") or "") for row in raw}
    return Corpus(
        works=works,
        keepers={key: tuple(values) for key, values in keepers.items()},
        raw_json=raw_json,
        published=frozenset(match_key(work_id) for work_id in published_ids),
    )


def load_corpus(normalized: Path, raw: Path, index: Path) -> Corpus:
    works_rows = pq.read_table(
        normalized, columns=["work_id", "title", "ca_any_author", "duplicate_work_ids"]
    ).to_pylist()
    raw_rows = pq.read_table(raw, columns=["openalex_id", "raw_json"]).to_pylist()
    published = [work["work_id"] for work in json.loads(index.read_text(encoding="utf-8"))["works"]]
    return build_corpus(works_rows, raw_rows, published)


def raw_title(corpus: Corpus, key: str) -> str:
    text = corpus.raw_json.get(key, "")
    if not text:
        return ""
    try:
        record = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(record, dict):
        return ""
    title = record.get("title") or record.get("display_name")
    return title.strip() if isinstance(title, str) else ""


def _collapsed(
    row: OverrideRow,
    key: str,
    keepers: Sequence[str],
    corpus: Corpus,
    excluded_keys: frozenset[str],
    base: Mapping[str, Any],
) -> Finding:
    keeper_key = sorted(keepers)[0]
    keeper = corpus.works[keeper_key]
    published = keeper_key in corpus.published
    has_exclude = keeper_key in excluded_keys
    old_title = raw_title(corpus, key)
    fields: dict[str, Any] = {
        **base,
        "klass": "collapsed_duplicate",
        "keeper": keeper["work_id"],
        "keeper_published": published,
        "keeper_excluded": has_exclude,
        "title_old": old_title,
        "title_keeper": keeper["title"],
    }
    if row.field != "exclude":
        return Finding(**fields, action="report_only")
    if len(keepers) > 1:
        return Finding(**fields, action="flag_multiple_keepers")
    if has_exclude:
        return Finding(**fields, action="covered")
    if not published:
        return Finding(**fields, action="skip_unpublished")
    if not old_title:
        return Finding(**fields, action="flag_title_missing")
    if title_key(old_title) != title_key(keeper["title"]):
        return Finding(**fields, action="flag_title")
    return Finding(**fields, action="carry")


def classify_rows(rows: Sequence[OverrideRow], corpus: Corpus) -> list[Finding]:
    excluded_keys = frozenset(match_key(row.work_id) for row in rows if row.field == "exclude")
    findings: list[Finding] = []
    for row in rows:
        key = match_key(row.work_id)
        base = {
            "line": row.line,
            "work_id": compact_id(row.work_id),
            "field": row.field,
            "reason": row.reason,
        }
        work = corpus.works.get(key)
        if work is not None:
            if not work["ca"]:
                klass = "non_ca"
            elif row.field == "exclude" and key in corpus.published:
                klass = "ca_still_published"
            else:
                klass = "applied"
            findings.append(Finding(**base, klass=klass))
            continue
        keepers = corpus.keepers.get(key)
        if keepers:
            findings.append(_collapsed(row, key, keepers, corpus, excluded_keys, base))
            continue
        klass = "in_raw_only" if key in corpus.raw_json else "not_in_corpus"
        findings.append(Finding(**base, klass=klass))
    return findings


def carry_rows(findings: Sequence[Finding]) -> list[dict[str, str]]:
    """New exclude rows for keepers of collapsed duplicates that qualify for CNT-1."""
    planned: set[str] = set()
    rows: list[dict[str, str]] = []
    for finding in findings:
        if finding.action != "carry":
            continue
        keeper_key = match_key(finding.keeper)
        if keeper_key in planned:
            continue
        planned.add(keeper_key)
        rows.append(
            {
                "work_id": finding.keeper,
                "field": "exclude",
                "value": "true",
                "reason": f"CNT-1: carried from {finding.work_id} (collapsed duplicate); "
                f"{finding.reason}",
                "reviewed_by": CARRY_REVIEWER,
                "reviewed_at": CARRY_DATE,
            }
        )
    return rows


def insert_carry_rows(text: str, rows: Sequence[Mapping[str, str]]) -> str:
    """Insert rows where ``build_audit_overrides.render`` keeps them: before the audit rows.

    Keeping that order means the generator's ``--check`` still passes after the insert.
    Existing lines are copied unchanged.
    """
    lines = text.splitlines(keepends=True)
    records = list(csv.DictReader(io.StringIO(text)))
    position = next(
        (
            index
            for index, record in enumerate(records)
            if record["reason"].startswith(AUDIT_MARKER)
        ),
        len(records),
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=HEADER, lineterminator="\n")
    writer.writerows(rows)
    new_lines = buffer.getvalue().splitlines(keepends=True)
    at = 1 + position
    return "".join(lines[:at] + new_lines + lines[at:])


def duplicate_groups(rows: Sequence[OverrideRow]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[OverrideRow]] = {}
    for row in rows:
        groups.setdefault((match_key(row.work_id), row.field), []).append(row)
    out: list[dict[str, Any]] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        identical = (
            len(
                {
                    (m.work_id, m.field, m.value, m.reason, m.reviewed_by, m.reviewed_at)
                    for m in members
                }
            )
            == 1
        )
        out.append(
            {
                "work_id": compact_id(members[0].work_id),
                "field": members[0].field,
                "lines": [m.line for m in members],
                "identical": identical,
            }
        )
    return out


def _tally(findings: Sequence[Finding]) -> dict[str, int]:
    counts = Counter(finding.klass for finding in findings)
    return {klass: counts.get(klass, 0) for klass in CLASSES}


def build_report(rows: Sequence[OverrideRow], corpus: Corpus) -> dict[str, Any]:
    findings = classify_rows(rows, corpus)
    exclude = [f for f in findings if f.field == "exclude"]
    other = [f for f in findings if f.field != "exclude"]
    carry = carry_rows(findings)
    exclude_counts = _tally(exclude)
    return {
        "rows": len(rows),
        "exclude_rows": len(exclude),
        "other_rows": len(other),
        "classes": {"exclude": exclude_counts, "other": _tally(other)},
        "duplicates": duplicate_groups(rows),
        "non_true_exclude": sum(
            1 for row in rows if row.field == "exclude" and row.value.strip().lower() != "true"
        ),
        "non_canonical_ids": [
            compact_id(row.work_id)
            for row in rows
            if not CANONICAL_ID.fullmatch(compact_id(row.work_id))
        ],
        "newly_excluded": exclude_counts["ca_still_published"] + len(carry),
        "carry_forward": carry,
        "flags": [asdict(f) for f in findings if f.action in FLAG_ACTIONS],
        "findings": [asdict(f) for f in findings],
    }


def _safe(text: object) -> str:
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


def _table(findings: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = [
        f"  {'line':>4}  {'work_id':<12}  {'class':<20}  {'keeper':<12}  {'kept_pub':<8}"
        f"  {'action':<14}  reason"
    ]
    for item in findings:
        keeper_pub = "-" if item["keeper_published"] is None else str(item["keeper_published"])
        lines.append(
            f"  {item['line']:>4}  {item['work_id']:<12}  {item['klass']:<20}"
            f"  {item['keeper'] or '-':<12}  {keeper_pub:<8}  {item['action']:<14}"
            f"  {_safe(item['reason'])[:60]}"
        )
    return lines


def render_text(report: Mapping[str, Any]) -> str:
    out: list[str] = [
        f"Override rows: {report['rows']} (exclude {report['exclude_rows']}, "
        f"other {report['other_rows']})",
        "Exclude rows by class:",
    ]
    out += [f"  {klass:<20}{n:>5}" for klass, n in report["classes"]["exclude"].items()]
    out.append("Other fields by class (no published check):")
    out += [f"  {klass:<20}{n:>5}" for klass, n in report["classes"]["other"].items()]
    duplicates = report["duplicates"]
    out.append(
        f"Duplicate work_id+field groups: {len(duplicates)} "
        f"(identical copies: {sum(1 for d in duplicates if d['identical'])})"
    )
    out.append(f"Exclude rows whose value is not true: {report['non_true_exclude']}")
    out.append(f"IDs not in W<number> form: {len(report['non_canonical_ids'])}")
    findings = report["findings"]
    exclude_gap = [f for f in findings if f["field"] == "exclude" and f["klass"] != "applied"]
    out.append(f"Exclude rows not applied ({len(exclude_gap)}):")
    out += _table(exclude_gap)
    other_gap = [f for f in findings if f["field"] != "exclude" and f["klass"] != "applied"]
    out.append(f"Other-field rows not applied ({len(other_gap)}):")
    out += _table(other_gap)
    out.append(f"Carry-forward rows to add: {len(report['carry_forward'])}")
    for row in report["carry_forward"]:
        out.append(f"  + {row['work_id']} exclude: {_safe(row['reason'])}")
    out.append(f"Flagged for owner review ({len(report['flags'])}):")
    for flag in report["flags"]:
        out.append(
            f"  {flag['work_id']} -> {flag['keeper']}: {flag['action']}; "
            f"old title {_safe(flag['title_old'])!r}; keeper title {_safe(flag['title_keeper'])!r}"
        )
    out.append(
        f"Published works a rebuild would newly exclude: {report['newly_excluded']} "
        f"(ca_still_published {report['classes']['exclude']['ca_still_published']}, "
        f"carry-forward {len(report['carry_forward'])})"
    )
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report unmatched override rows (read-only).")
    parser.add_argument("--overrides", type=Path, default=OVERRIDES)
    parser.add_argument("--normalized", type=Path, default=NORMALIZED)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    rows = read_override_rows(args.overrides)
    corpus = load_corpus(args.normalized, args.raw, args.index)
    report = build_report(rows, corpus)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
