"""Offline tests for the S4.2 v2 builder, leak fetch helpers and acceptance validator."""

from __future__ import annotations

import copy

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.nlp.sampling import build_split_rows
from atlas.query import load_query_config
from scripts.build_gold_sample import _leak_records
from scripts.check_s4_2 import validate_v2
from scripts.fetch_leak_candidates import (
    candidate_ngrams,
    place_filter,
    reconstruct_abstract,
    works_url,
)


def _records(count: int) -> list[dict]:
    return [
        {
            "work_id": f"W{i:04d}",
            "year": 2010 + i % 12,
            "type": "article" if i % 3 else "review",
            "title": "Microplastics in estuaries",
            "oa_status": "gold" if i % 2 else "closed",
            "institution_type": "uc",
            "ca_any_author": True,
            "author_ids": [f"A{i:04d}"],
        }
        for i in range(count)
    ]


def _manifest_for(rows: list[dict]) -> dict:
    pool = [r for r in rows if r["sample_role"] == "pool"]
    dims = ("year_bin", "journal_type", "matrix", "oa_status", "institution_type")
    strata = {}
    for dim in dims:
        counts: dict[str, int] = {}
        for row in pool:
            counts[row[dim]] = counts.get(row[dim], 0) + 1
        strata[dim] = dict(sorted(counts.items()))
    return {
        "version": "splits_v2",
        "snapshot_status": "v3.1_corpus",
        "author_group_overlap_across_splits": 0,
        "pool_rows": len(pool),
        "leak_test_rows": len(rows) - len(pool),
        "split_counts": {n: sum(r["split"] == n for r in pool) for n in ("train", "dev", "test")},
        "split_counts_all_roles": {
            n: sum(r["split"] == n for r in rows) for n in ("train", "dev", "test")
        },
        "stratum_counts": strata,
    }


def _v2_fixture() -> tuple[list[dict], dict, set[str]]:
    records = _records(450)
    leaks = [
        {**_records(1)[0], "work_id": f"W9{i:03d}", "ca_any_author": False, "gazetteer_hit": True}
        | {"author_ids": [f"L{i}"]}
        for i in range(10)
    ]
    rows = build_split_rows([*records, *leaks], sample_size=420, leak_test_size=8)
    return (
        rows,
        _manifest_for(rows),
        {r["work_id"] for r in rows if r["sample_role"] == "leak_test"},
    )


def test_validator_accepts_consistent_v2() -> None:
    rows, manifest, hits = _v2_fixture()
    validate_v2(rows, manifest, hits)


def test_validator_rejects_leak_outside_test_and_author_group_spanning() -> None:
    rows, manifest, hits = _v2_fixture()
    bad = copy.deepcopy(rows)
    next(r for r in bad if r["sample_role"] == "leak_test")["split"] = "dev"
    with pytest.raises(AssertionError):
        validate_v2(bad, manifest, hits)
    bad = copy.deepcopy(rows)
    pool = [r for r in bad if r["sample_role"] == "pool"]
    pool[1]["author_group"] = pool[0]["author_group"]
    pool[0]["split"], pool[1]["split"] = "train", "dev"
    with pytest.raises(AssertionError):
        validate_v2(bad, manifest, hits)


def test_validator_rejects_pool_outside_range() -> None:
    records = _records(450)
    rows = build_split_rows(records, sample_size=100, leak_test_size=0)
    with pytest.raises(AssertionError):
        validate_v2(rows, _manifest_for(rows), set())


def test_giant_author_component_does_not_swallow_test_split() -> None:
    records = _records(100)
    for record in records[:40]:
        record["author_ids"] = ["mega"]
    rows = build_split_rows(records, sample_size=100, leak_test_size=0)
    counts = {n: sum(r["split"] == n for r in rows) for n in ("train", "dev", "test")}
    assert counts["test"] <= 20 and counts["dev"] > 0
    assert len({r["split"] for r in rows if r["author_group"] == rows[0]["author_group"]}) == 1


def test_leak_selection_prefers_candidates_without_pool_authors() -> None:
    records = _records(20)
    records[0]["author_ids"] = ["shared"]
    leaks = [
        {**_records(1)[0], "work_id": "WL1", "ca_any_author": False, "author_ids": ["shared"]},
        {**_records(1)[0], "work_id": "WL2", "ca_any_author": False, "author_ids": ["other"]},
    ]
    for leak in leaks:
        leak["gazetteer_hit"] = True
    rows = build_split_rows([*records, *leaks], sample_size=20, leak_test_size=1)
    assert [r["work_id"] for r in rows if r["sample_role"] == "leak_test"] == ["WL2"]


def test_leak_records_are_minimal_and_filtered(tmp_path) -> None:
    path = tmp_path / "leak.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "work_id": "W1",
                    "title": "t",
                    "abstract": "a",
                    "year": 2020,
                    "type": "article",
                    "oa_status": "gold",
                    "author_ids": ["A2", "A1"],
                },
                {
                    "work_id": "W2",
                    "title": "x",
                    "abstract": "",
                    "year": 2019,
                    "type": "article",
                    "oa_status": "closed",
                    "author_ids": [],
                },
                {
                    "work_id": "W3",
                    "title": "y",
                    "abstract": "",
                    "year": 2019,
                    "type": "article",
                    "oa_status": "closed",
                    "author_ids": [],
                },
            ]
        ),
        path,
    )
    records = _leak_records(path, {"W1", "W3"}, {"W3"})
    assert [r["work_id"] for r in records] == ["W1"]
    assert records[0]["ca_any_author"] is False and records[0]["gazetteer_hit"] is True
    assert records[0]["author_ids"] == ["A1", "A2"]


def test_fetch_helpers_are_offline_and_deterministic() -> None:
    assert reconstruct_abstract({"b": [1], "a": [0]}) == "a b"
    assert reconstruct_abstract(None) == ""
    grams = candidate_ngrams("Samples from San Francisco Bay and Berkeley were collected.")
    assert {"San Francisco Bay", "San Francisco", "Berkeley"} <= grams
    assert "Samples" in grams and "from" not in grams
    assert place_filter().startswith("title_and_abstract.search:(California OR")
    url = works_url(load_query_config("config/queries.yml"), per_page=1)
    assert "per-page=1" in url and "San+Francisco+Bay" in url
