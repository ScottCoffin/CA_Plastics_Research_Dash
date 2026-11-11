from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from atlas.query_audit_review import REVIEW_CSV, load_review, save_review, set_label


@pytest.fixture()
def review_copy(tmp_path: Path) -> Path:
    # Work on a copy with labels cleared: the real CSV holds the owner's labels in progress.
    target = tmp_path / "review.csv"
    shutil.copyfile(REVIEW_CSV, target)
    table = load_review(target)
    for row in table.rows:
        row.update(review_label="", reviewer="", noise_terms="")
    save_review(table, target)
    return target


def test_unchanged_save_is_byte_identical(review_copy: Path) -> None:
    before = review_copy.read_bytes()
    save_review(load_review(review_copy), review_copy)
    assert review_copy.read_bytes() == before


def test_label_applies_to_every_row_of_a_duplicated_work(review_copy: Path) -> None:
    table = load_review(review_copy)
    ids = [row["work_id"] for row in table.rows]
    duplicate = next(work_id for work_id in ids if ids.count(work_id) > 1)
    changed = set_label(table, duplicate, "not_relevant", "SC", "plasticity")
    assert changed == ids.count(duplicate) > 1
    save_review(table, review_copy)
    reloaded = load_review(review_copy)
    rows = [row for row in reloaded.rows if row["work_id"] == duplicate]
    assert {(r["review_label"], r["reviewer"], r["noise_terms"]) for r in rows} == {
        ("not_relevant", "SC", "plasticity")
    }
    others = [row for row in reloaded.rows if row["work_id"] != duplicate]
    assert all(row["review_label"] == "" for row in others)
    assert reloaded.label_counts()["not_relevant"] == 1


def test_clearing_and_validation(review_copy: Path) -> None:
    table = load_review(review_copy)
    work_id = table.rows[0]["work_id"]
    with pytest.raises(ValueError, match="initials"):
        set_label(table, work_id, "relevant", " ")
    with pytest.raises(ValueError, match="label must be"):
        set_label(table, work_id, "maybe", "SC")
    with pytest.raises(KeyError):
        set_label(table, "W0", "relevant", "SC")
    set_label(table, work_id, "relevant", "SC", "x")
    set_label(table, work_id, "", "")
    assert all(
        row["review_label"] == row["reviewer"] == row["noise_terms"] == "" for row in table.rows
    )
