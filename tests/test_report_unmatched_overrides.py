"""Tests for the read-only unmatched-override report and the CNT-1 carry-forward rule."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "report_unmatched_overrides.py"
AUDIT_REASON = "AT-1 owner audit label (QUERY_AUDIT_REVIEW_V3.csv): not_relevant"


def _runner():
    spec = importlib.util.spec_from_file_location("report_unmatched_overrides", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Dataclasses need the module registered before its body runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rep = _runner()


def _row(
    work_id: str,
    field: str = "exclude",
    value: str = "true",
    reason: str = AUDIT_REASON,
    line: int = 2,
):
    return rep.OverrideRow(
        line=line,
        work_id=work_id,
        field=field,
        value=value,
        reason=reason,
        reviewed_by="SC",
        reviewed_at="2026-11-10",
    )


def _norm(work_id: str, title: str = "Plastic Titles", ca: bool = True, dups=()) -> dict[str, Any]:
    return {
        "work_id": work_id,
        "title": title,
        "ca_any_author": ca,
        "duplicate_work_ids": list(dups),
    }


def _raw(openalex_id: str, title: str | None = None, key: str = "title") -> dict[str, Any]:
    record: dict[str, Any] = {}
    if title is not None:
        record[key] = title
    return {"openalex_id": openalex_id, "raw_json": json.dumps(record)}


def _corpus(works=(), raw=(), published=()):
    return rep.build_corpus(list(works), list(raw), list(published))


def _classify(rows, corpus):
    return {f.work_id: f for f in rep.classify_rows(rows, corpus)}


def test_applied_when_ca_work_is_removed_from_published() -> None:
    corpus = _corpus(works=[_norm("W1")], raw=[_raw("W1")], published=[])
    finding = _classify([_row("W1")], corpus)["W1"]
    assert finding.klass == "applied"
    assert finding.action == "keep"


def test_ca_still_published_when_exclusion_has_not_reached_export() -> None:
    corpus = _corpus(works=[_norm("W1")], raw=[_raw("W1")], published=["W1"])
    assert _classify([_row("W1")], corpus)["W1"].klass == "ca_still_published"


def test_non_ca_work_in_normalized_is_its_own_class() -> None:
    corpus = _corpus(works=[_norm("W2", ca=False)], raw=[_raw("W2")])
    assert _classify([_row("W2")], corpus)["W2"].klass == "non_ca"


def test_in_raw_only_when_not_normalized_and_not_a_duplicate() -> None:
    corpus = _corpus(raw=[_raw("W3")])
    assert _classify([_row("W3")], corpus)["W3"].klass == "in_raw_only"


def test_not_in_corpus_when_in_neither_store() -> None:
    corpus = _corpus(works=[_norm("W4")], raw=[_raw("W4")])
    assert _classify([_row("W5")], corpus)["W5"].klass == "not_in_corpus"


def test_ids_match_across_url_prefix_and_case() -> None:
    corpus = _corpus(works=[_norm("W6")], raw=[_raw("W6")], published=[])
    finding = _classify([_row("https://openalex.org/w6")], corpus)["w6"]
    assert finding.klass == "applied"
    assert finding.work_id == "w6"


def test_collapsed_duplicate_carries_when_keeper_published_and_title_matches() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="Microplastics: a review.", dups=["W9"])],
        raw=[_raw("W9", title="Microplastics A Review"), _raw("W10")],
        published=["W10"],
    )
    finding = _classify([_row("W9")], corpus)["W9"]
    assert finding.klass == "collapsed_duplicate"
    assert finding.keeper == "W10"
    assert finding.keeper_published is True
    assert finding.keeper_excluded is False
    assert finding.action == "carry"


def test_carry_row_text_follows_cnt1_format() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="Same title", dups=["W9"])],
        raw=[_raw("W9", title="Same title"), _raw("W10")],
        published=["W10"],
    )
    rows = rep.carry_rows(rep.classify_rows([_row("W9")], corpus))
    assert rows == [
        {
            "work_id": "W10",
            "field": "exclude",
            "value": "true",
            "reason": f"CNT-1: carried from W9 (collapsed duplicate); {AUDIT_REASON}",
            "reviewed_by": "agent-CNT-1",
            "reviewed_at": "2026-11-22",
        }
    ]


def test_title_difference_is_flagged_and_not_carried() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="A different paper", dups=["W9"])],
        raw=[_raw("W9", title="Original paper"), _raw("W10")],
        published=["W10"],
    )
    finding = _classify([_row("W9")], corpus)["W9"]
    assert finding.action == "flag_title"
    assert rep.carry_rows([finding]) == []


def test_missing_duplicate_title_is_flagged_not_carried() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="Some paper", dups=["W9"])],
        raw=[_raw("W9"), _raw("W10")],
        published=["W10"],
    )
    assert _classify([_row("W9")], corpus)["W9"].action == "flag_title_missing"


def test_keeper_with_existing_exclude_row_is_covered() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="Same title", dups=["W9"])],
        raw=[_raw("W9", title="Same title"), _raw("W10")],
        published=[],
    )
    rows = [_row("W9"), _row("W10", reason="already excluded", line=3)]
    finding = _classify(rows, corpus)["W9"]
    assert finding.keeper_excluded is True
    assert finding.action == "covered"
    assert rep.carry_rows(rep.classify_rows(rows, corpus)) == []


def test_unpublished_keeper_without_exclude_is_skipped() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="Same title", dups=["W9"])],
        raw=[_raw("W9", title="Same title"), _raw("W10")],
        published=[],
    )
    finding = _classify([_row("W9")], corpus)["W9"]
    assert finding.keeper_published is False
    assert finding.action == "skip_unpublished"


def test_collapsed_duplicate_of_other_field_is_report_only() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="Same title", dups=["W9"])],
        raw=[_raw("W9", title="Same title"), _raw("W10")],
        published=["W10"],
    )
    rows = [_row("W9", field="plastic_related", value="true", reason="reason")]
    finding = _classify(rows, corpus)["W9"]
    assert finding.klass == "collapsed_duplicate"
    assert finding.action == "report_only"
    assert rep.carry_rows(rep.classify_rows(rows, corpus)) == []


def test_two_duplicates_of_one_keeper_produce_one_carry_row() -> None:
    corpus = _corpus(
        works=[_norm("W10", title="Same title", dups=["W8", "W9"])],
        raw=[_raw("W8", title="Same title"), _raw("W9", title="Same title"), _raw("W10")],
        published=["W10"],
    )
    rows = rep.carry_rows(rep.classify_rows([_row("W8"), _row("W9")], corpus))
    assert [row["work_id"] for row in rows] == ["W10"]


def test_duplicate_rows_are_reported_and_identical_flagged() -> None:
    rows = [_row("W1", line=2), _row("W1", line=3), _row("W1", field="plastic_related", line=4)]
    groups = rep.duplicate_groups(rows)
    assert len(groups) == 1
    assert groups[0]["field"] == "exclude"
    assert groups[0]["lines"] == [2, 3]
    assert groups[0]["identical"] is True


def test_report_counts_exclude_and_other_fields_separately() -> None:
    corpus = _corpus(
        works=[_norm("W1"), _norm("W2", ca=False)],
        raw=[_raw("W1"), _raw("W2")],
        published=["W1"],
    )
    rows = [_row("W1", line=2), _row("W2", line=3), _row("W1", field="plastic_related", line=4)]
    report = rep.build_report(rows, corpus)
    assert report["exclude_rows"] == 2
    assert report["other_rows"] == 1
    assert report["classes"]["exclude"]["ca_still_published"] == 1
    assert report["classes"]["exclude"]["non_ca"] == 1
    assert report["classes"]["other"]["applied"] == 1
    assert report["newly_excluded"] == 1


def test_title_key_ignores_case_punctuation_and_spacing() -> None:
    assert rep.title_key("Plastics: A  Review!") == rep.title_key("plastics a review")
    assert rep.title_key("Plastics: A Review") != rep.title_key("Plastics: A Study")


def test_insert_carry_rows_goes_before_audit_rows_and_keeps_original_lines() -> None:
    header = ",".join(rep.HEADER) + "\n"
    audit = f"W1,exclude,true,{AUDIT_REASON},SC,2026-11-10\n"
    text = header + audit
    new = [
        {
            "work_id": "W10",
            "field": "exclude",
            "value": "true",
            "reason": "CNT-1: carried from W9 (collapsed duplicate); x",
            "reviewed_by": "agent-CNT-1",
            "reviewed_at": "2026-11-22",
        }
    ]
    updated = rep.insert_carry_rows(text, new)
    lines = updated.splitlines(keepends=True)
    assert lines[0] == header
    assert lines[1].startswith("W10,exclude,true,CNT-1: carried from W9")
    assert lines[2] == audit
    assert "\r" not in updated


def test_insert_carry_rows_appends_when_no_audit_rows() -> None:
    text = ",".join(rep.HEADER) + "\n" + "W1,plastic_related,true,manual,SC,2026-11-10\n"
    new = [
        {
            "work_id": "W2",
            "field": "exclude",
            "value": "true",
            "reason": "r",
            "reviewed_by": "agent-CNT-1",
            "reviewed_at": "2026-11-22",
        }
    ]
    updated = rep.insert_carry_rows(text, new)
    assert updated.endswith("W2,exclude,true,r,agent-CNT-1,2026-11-22\n")
    assert updated.startswith(text)


def test_read_override_rows_keeps_physical_line_numbers(tmp_path: Path) -> None:
    path = tmp_path / "overrides.csv"
    path.write_text(
        ",".join(rep.HEADER) + "\n" + f"W1,exclude,true,{AUDIT_REASON},SC,2026-11-10\n",
        encoding="utf-8",
    )
    rows = rep.read_override_rows(path)
    assert [(row.line, row.work_id, row.field) for row in rows] == [(2, "W1", "exclude")]


def test_load_corpus_reads_tables_and_index(tmp_path: Path) -> None:
    normalized = tmp_path / "works.parquet"
    raw = tmp_path / "raw.parquet"
    index = tmp_path / "index.json"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "work_id": "W10",
                    "title": "Keeper",
                    "ca_any_author": True,
                    "duplicate_work_ids": ["W9"],
                }
            ]
        ),
        normalized,
    )
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"openalex_id": "W9", "raw_json": json.dumps({"title": "Keeper"})},
                {"openalex_id": "W10", "raw_json": "{}"},
            ]
        ),
        raw,
    )
    index.write_text(json.dumps({"works": [{"work_id": "W10"}]}), encoding="utf-8")
    corpus = rep.load_corpus(normalized, raw, index)
    assert corpus.published == frozenset({"W10"})
    assert _classify([_row("W9")], corpus)["W9"].action == "carry"


def test_main_is_read_only_and_emits_json(tmp_path: Path, capsys) -> None:
    overrides = tmp_path / "overrides.csv"
    overrides.write_text(
        ",".join(rep.HEADER) + "\n" + f"W1,exclude,true,{AUDIT_REASON},SC,2026-11-10\n",
        encoding="utf-8",
    )
    normalized = tmp_path / "works.parquet"
    raw = tmp_path / "raw.parquet"
    index = tmp_path / "index.json"
    pq.write_table(
        pa.Table.from_pylist(
            [{"work_id": "W1", "title": "T", "ca_any_author": True, "duplicate_work_ids": []}]
        ),
        normalized,
    )
    pq.write_table(pa.Table.from_pylist([{"openalex_id": "W1", "raw_json": "{}"}]), raw)
    index.write_text(json.dumps({"works": []}), encoding="utf-8")
    before = hashlib.sha256(overrides.read_bytes()).hexdigest()

    code = rep.main(
        [
            "--overrides",
            str(overrides),
            "--normalized",
            str(normalized),
            "--raw",
            str(raw),
            "--index",
            str(index),
            "--json",
        ]
    )

    assert code == 0
    assert hashlib.sha256(overrides.read_bytes()).hexdigest() == before
    report = json.loads(capsys.readouterr().out)
    assert report["classes"]["exclude"]["applied"] == 1
    assert report["carry_forward"] == []
