"""Deterministic sampling and frozen-split hygiene tests."""

from __future__ import annotations

from atlas.nlp.sampling import build_split_rows, sampling_strata


def _record(index: int, **overrides: object) -> dict:
    record = {
        "work_id": f"W{index:04d}",
        "year": 2000 + index,
        "type": "article" if index % 2 else "review",
        "title": "Microplastics in estuaries" if index % 2 else "Plastic in soil",
        "abstract": "",
        "oa_status": "gold" if index % 2 else "closed",
        "institution_type": "education" if index % 2 else "government",
        "ca_any_author": True,
        "gazetteer_hit": False,
        "author_ids": [f"A{index:04d}"],
    }
    record.update(overrides)
    return record


def test_sampling_is_deterministic_and_stratified_across_dimensions() -> None:
    records = [_record(index) for index in range(24)]
    first = build_split_rows(records, seed=9, sample_size=12)
    second = build_split_rows(reversed(records), seed=9, sample_size=12)
    assert first == second
    pool = [row for row in first if row["sample_role"] == "pool"]
    assert len(pool) == 12
    assert {row["year_bin"] for row in pool} >= {"2000-2004", "2005-2009"}
    assert {row["matrix"] for row in pool} == {"marine", "soil"}
    assert {row["oa_status"] for row in pool} == {"gold", "closed"}
    assert {row["institution_type"] for row in pool} == {"education", "government"}


def test_frozen_splits_have_no_work_or_author_group_overlap() -> None:
    records = [_record(index) for index in range(30)]
    records[1]["author_ids"] = ["shared-author"]
    records[2]["author_ids"] = ["shared-author"]
    rows = build_split_rows(records, seed=21, sample_size=24)
    pool = [row for row in rows if row["sample_role"] == "pool"]
    assert len({row["work_id"] for row in pool}) == len(pool)
    split_by_group: dict[str, set[str]] = {}
    for row in pool:
        split_by_group.setdefault(row["author_group"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in split_by_group.values())
    assert {row["split"] for row in pool} == {"train", "dev", "test"}


def test_leak_sample_is_out_of_pool_and_always_held_out() -> None:
    records = [_record(index) for index in range(12)]
    records.extend(
        [
            _record(100, ca_any_author=False, gazetteer_hit=True),
            _record(101, ca_any_author=False, gazetteer_hit=False),
            _record(102, ca_any_author=True, gazetteer_hit=True),
        ]
    )
    rows = build_split_rows(records, sample_size=8, leak_test_size=10)
    leak = [row for row in rows if row["sample_role"] == "leak_test"]
    assert [row["work_id"] for row in leak] == ["W0100"]
    assert all(row["split"] == "test" for row in leak)
    assert "W0100" not in {row["work_id"] for row in rows if row["sample_role"] == "pool"}


def test_leak_author_group_cannot_cross_into_development() -> None:
    records = [_record(index) for index in range(12)]
    records[0]["author_ids"] = ["shared-author"]
    records.append(
        _record(100, ca_any_author=False, gazetteer_hit=True, author_ids=["shared-author"])
    )
    rows = build_split_rows(records, sample_size=12, leak_test_size=1)
    by_id = {row["work_id"]: row for row in rows}
    assert by_id["W0100"]["split"] == "test"
    assert by_id["W0000"]["split"] == "test"
    assert by_id["W0000"]["author_group"] == by_id["W0100"]["author_group"]


def test_absent_matrix_and_year_are_explicitly_unknown() -> None:
    assert sampling_strata({"work_id": "W1"}) == (
        "unknown",
        "unknown",
        "unknown",
        "unknown",
        "unknown",
    )
