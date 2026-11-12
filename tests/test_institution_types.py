from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_institution_types import (
    Inputs,
    Paths,
    build,
    load_inputs,
    main,
    rank_california,
    render_csv,
    resolve_type,
    roll_up_parent,
    work_counts,
)


def _inputs(**overrides) -> Inputs:
    base = {
        "registry": {
            "I1": {"display_name": "Alpha", "atlas_type": "private", "lineage": ["I1"]},
            "I2": {
                "display_name": "Beta Institute",
                "atlas_type": "nonprofit/NGO",
                "lineage": ["I2", "I1"],
            },
            "I3": {"display_name": "Gamma Agency", "atlas_type": "federal", "lineage": ["I3"]},
            "I4": {"display_name": "Out of State", "atlas_type": "company", "lineage": ["I4"]},
        },
        "corpus": {
            "I1": {"ca_flag": True},
            "I2": {"ca_flag": True},
            "I3": {"ca_flag": True},
            "I4": {"ca_flag": False},
        },
        "authorships": [
            ("W1", ["I1"]),
            ("W1", ["I1"]),  # duplicate authorship row counts once
            ("W2", ["I1", "I2"]),
            ("W3", ["I2"]),
            ("W4", ["I3"]),
            ("W5", ["I4"]),
        ],
        "excluded_works": frozenset(),
        "overrides": {},
        "old_top100": {},
        "site": [
            {"inst_id": "I1", "ca_flag": True, "work_count": 2},
            {"inst_id": "I2", "ca_flag": True, "work_count": 2},
            {"inst_id": "I3", "ca_flag": True, "work_count": 1},
            {"inst_id": "I4", "ca_flag": False, "work_count": 1},
        ],
    }
    base.update(overrides)
    return Inputs(**base)


def test_work_counts_are_distinct_and_skip_excluded_works():
    counts = work_counts(
        [("W1", ["I1"]), ("W1", ["I1"]), ("W2", ["I1", "I2"]), ("W3", ["I2"])],
        frozenset({"W3"}),
    )
    assert counts == {"I1": 2, "I2": 1}


@pytest.mark.parametrize(
    ("inst_id", "lineage", "expected"),
    [
        ("I1", ["I1"], ""),
        ("I2", ["I2", "I1"], "I1"),
        ("I2", ["I1", "I2"], "I1"),
        ("I3", ["I2", "I3", "I9"], "I9"),
        ("I4", [], ""),
        ("I5", None, ""),
    ],
)
def test_roll_up_parent_is_last_lineage_entry_other_than_self(inst_id, lineage, expected):
    assert roll_up_parent(inst_id, lineage) == expected


def test_rank_orders_by_count_then_inst_id_and_skips_non_ca_and_zero():
    corpus = {
        "I1": {"ca_flag": True},
        "I2": {"ca_flag": True},
        "I3": {"ca_flag": True},
        "I9": {"ca_flag": False},
    }
    counts = {"I1": 2, "I2": 5, "I3": 2, "I9": 99}
    assert rank_california(counts, corpus) == ["I2", "I1", "I3"]


def test_type_precedence_override_then_owner_review_then_rule():
    inputs = _inputs(
        overrides={"I1": "UC"},
        old_top100={
            "I2": {"proposed_atlas_type": "nonprofit/NGO", "owner_atlas_type": ""},
            "I3": {"proposed_atlas_type": "federal", "owner_atlas_type": "state-agency"},
        },
    )
    assert resolve_type("I1", inputs) == ("UC", "owner_override")
    assert resolve_type("I2", inputs) == ("nonprofit/NGO", "owner_reviewed")
    assert resolve_type("I3", inputs) == ("state-agency", "owner_reviewed")
    assert resolve_type("I4", inputs) == ("company", "rule")


def test_needs_review_only_for_rule_typed_new_top_entrants():
    inputs = _inputs(
        overrides={"I1": "private"},
        old_top100={"I2": {"proposed_atlas_type": "nonprofit/NGO", "owner_atlas_type": ""}},
    )
    result = build(inputs)
    by_id = {row["inst_id"]: row for row in result.config_rows}
    assert [row["inst_id"] for row in result.config_rows] == ["I1", "I2", "I3"]
    assert by_id["I1"]["type_source"] == "owner_override" and by_id["I1"]["needs_review"] == "false"
    assert by_id["I2"]["type_source"] == "owner_reviewed" and by_id["I2"]["needs_review"] == "false"
    assert by_id["I3"]["type_source"] == "rule" and by_id["I3"]["needs_review"] == "true"
    assert [row["openalex_id"] for row in result.review_rows] == ["I1", "I3"]
    assert by_id["I2"]["parent_id"] == "I1"
    assert by_id["I1"]["v31_rank"] == "1" and by_id["I1"]["v31_work_count"] == "2"


def test_review_rows_have_blank_owner_fields_and_no_relevance_notes():
    result = build(_inputs())
    assert result.review_rows
    for row in result.review_rows:
        assert row["owner_atlas_type"] == "" and row["owner_reviewed_at"] == ""
        assert row["owner_notes"] == ""
        assert "relevance" not in " ".join(row.values()).lower()


def test_rebuild_keeps_owner_review_fields():
    from dataclasses import replace

    owner = {"owner_atlas_type": "JPA", "owner_reviewed_at": "2026-11-12", "owner_notes": "n"}
    result = build(replace(_inputs(), previous_review={"I3": {"openalex_id": "I3", **owner}}))
    by_id = {row["openalex_id"]: row for row in result.review_rows}
    assert {key: by_id["I3"][key] for key in owner} == owner
    assert all(row["owner_atlas_type"] == "" for key, row in by_id.items() if key != "I3")


def test_resolved_type_must_match_registry():
    inputs = _inputs(overrides={"I3": "UC"})
    with pytest.raises(ValueError, match="rebuild the registry"):
        build(inputs)


def test_render_csv_is_lf_and_deterministic():
    rows = [{"a": "x,y", "b": "2"}]
    first = render_csv(("a", "b"), rows)
    assert first == render_csv(("a", "b"), rows)
    assert b"\r" not in first
    assert first == b'a,b\n"x,y",2\n'


def test_invalid_atlas_type_override_is_rejected(tmp_path: Path):
    bad = tmp_path / "overrides.csv"
    bad.write_text(
        "inst_id,field,value,reason,reviewed_by,reviewed_at\nI1,atlas_type,unknown,,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid atlas_type"):
        load_inputs(Paths(type_overrides=bad))


def test_committed_outputs_match_inputs():
    assert main(["--check"]) == 0
