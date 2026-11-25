"""Tests for the tag co-occurrence layer (BQ-4.3). Synthetic inputs only.

Hand-computed toy (as of 2026-11-25, so complete years end at 2025 and the default recent period is
2021-2025). Six works carry tags as {tag: source}; work 6 is not plastic-related:

    w1 2024 plastic {A rule, B rule, X rule (experimental)}
    w2 2024 plastic {A rule, B rule}
    w3 2024 plastic {A rule, C owner}
    w4 2024 plastic {B rule}
    w5 2024 plastic {A rule}
    w6 2024 NOT plastic {A, B, C}

Complete years: N = 5, n_A = 4, n_B = 3, n_C = 1, n_AB = 2, n_AC = 1, n_BC = 0.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from atlas.analytics.tag_cooccurrence import (
    MIN_PAIR_N,
    SCHEMA,
    build_cooccurrence,
    pair_statistics,
)
from atlas.analytics.topic_series import CaWork, snapshot_rows, write_snapshot

AS_OF = date(2026, 11, 25)
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_tag_cooccurrence.py"
TAXONOMY = {
    "domain_tags": [
        {"id": "A", "label": "Alpha", "status": "approved", "seed_concepts": ["a"]},
        {"id": "B", "label": "Beta", "status": "approved"},
        {"id": "C", "label": "Gamma", "status": "approved"},
        {"id": "D", "label": "Delta", "status": "approved"},
        {"id": "X", "label": "Experimental", "status": "approved", "experimental": True},
    ]
}


def _work(work_id: str, year: int | None, tags: dict[str, str], plastic: bool = True) -> CaWork:
    return CaWork(work_id=work_id, year=year, plastic_related=plastic, topic_sources=dict(tags))


def _toy() -> list[CaWork]:
    return [
        _work("w1", 2024, {"A": "rule", "B": "rule", "X": "rule"}),
        _work("w2", 2024, {"A": "rule", "B": "rule"}),
        _work("w3", 2024, {"A": "rule", "C": "owner"}),
        _work("w4", 2024, {"B": "rule"}),
        _work("w5", 2024, {"A": "rule"}),
        _work("w6", 2024, {"A": "rule", "B": "rule", "C": "rule"}, plastic=False),
    ]


def _build(works: list[CaWork], **kwargs) -> dict:
    options = {
        "works": works,
        "taxonomy": TAXONOMY,
        "as_of": AS_OF,
        "snapshot_path": "snap.parquet",
        "snapshot_sha256": "abc",
        "taxonomy_path": "tax.yml",
        "taxonomy_sha256": "def",
    }
    options.update(kwargs)
    return build_cooccurrence(**options)


def _pair(window: dict, a: str, b: str) -> dict:
    return next(p for p in window["pairs"] if (p["a"], p["b"]) == (a, b))


def test_toy_pair_counts_match_hand_computation() -> None:
    payload = _build(_toy())
    assert payload["schema"] == SCHEMA
    window = payload["variants"]["all_sources"]["windows"]["complete_years"]
    assert window["N"] == 5
    ab = _pair(window, "A", "B")
    assert (ab["n_ab"], ab["n_a"], ab["n_b"], ab["N"]) == (2, 4, 3, 5)
    assert ab["jaccard"] == 0.4  # 2 / (4 + 3 - 2)
    assert ab["lift"] == 0.8333  # 2 * 5 / (4 * 3)
    assert ab["phi"] == -0.4082  # (2*5 - 4*3) / sqrt(4*1*3*2)
    ac = _pair(window, "A", "C")
    assert (ac["n_ab"], ac["n_a"], ac["n_b"]) == (1, 4, 1)
    assert ac["jaccard"] == 0.25
    assert ac["lift"] == 1.25
    assert ac["phi"] == 0.25
    bc = _pair(window, "B", "C")
    assert (bc["n_ab"], bc["n_a"], bc["n_b"]) == (0, 3, 1)
    assert bc["jaccard"] == 0.0
    assert bc["lift"] == 0.0
    assert bc["phi"] == -0.6124


def test_experimental_and_non_plastic_works_are_excluded() -> None:
    payload = _build(_toy())
    assert [t["tag"] for t in payload["tags"]] == ["A", "B", "C", "D"]
    assert payload["tags_excluded"] == [{"tag": "X", "reason": "experimental"}]
    window = payload["variants"]["all_sources"]["windows"]["complete_years"]
    assert all("X" not in (p["a"], p["b"]) for p in window["pairs"])
    assert window["N"] == 5  # work 6 is not plastic-related


def test_partial_year_only_in_all_years_total() -> None:
    works = _toy() + [_work("w7", 2026, {"A": "rule", "B": "rule"})]
    payload = _build(works)
    complete = _pair(payload["variants"]["all_sources"]["windows"]["complete_years"], "A", "B")
    total = _pair(payload["variants"]["all_sources"]["windows"]["all_years"], "A", "B")
    assert (complete["n_ab"], complete["N"]) == (2, 5)
    assert (total["n_ab"], total["n_a"], total["n_b"], total["N"]) == (3, 5, 4, 6)
    assert total["jaccard"] == 0.5
    assert total["lift"] == 0.9


def test_periods_split_at_fixed_year() -> None:
    works = _toy() + [_work("old", 2019, {"A": "rule", "B": "rule"})]
    default = _build(works)["variants"]["all_sources"]["windows"]
    assert default["earlier"]["N"] == 1  # default split: last 5 complete years start in 2021
    assert default["recent"]["N"] == 5
    explicit = _build(works, split_year=2025)["variants"]["all_sources"]["windows"]
    assert explicit["earlier"]["N"] == 6
    assert explicit["recent"]["N"] == 0
    assert _build(works)["split_year"] == 2021


def test_insufficient_data_flag_at_boundary() -> None:
    assert MIN_PAIR_N == 5
    works = [_work(f"ab{i}", 2024, {"A": "rule", "B": "rule"}) for i in range(4)]
    works += [_work(f"cd{i}", 2024, {"C": "rule", "D": "rule"}) for i in range(5)]
    window = _build(works)["variants"]["all_sources"]["windows"]["complete_years"]
    ab = _pair(window, "A", "B")
    cd = _pair(window, "C", "D")
    assert (ab["n_ab"], ab["status"]) == (4, "insufficient_data")
    assert (cd["n_ab"], cd["status"]) == (5, "sufficient")
    assert ab["jaccard"] == 1.0  # shown, not hidden


def test_owner_variant_and_null_denominators() -> None:
    payload = _build(_toy())
    assert payload["variants"]["owner_model_only"]["status"] == "testable"
    window = payload["variants"]["owner_model_only"]["windows"]["complete_years"]
    ac = _pair(window, "A", "C")
    assert (ac["n_ab"], ac["n_a"], ac["n_b"]) == (0, 0, 1)
    assert ac["lift"] is None  # n_a is zero
    assert ac["jaccard"] == 0.0


def test_empty_variant_is_not_testable() -> None:
    works = [_work("r1", 2024, {"A": "rule", "B": "rule"})]
    payload = _build(works)
    empty = payload["variants"]["owner_model_only"]
    assert empty == {
        "status": "not_testable",
        "message": "no labels from this source in any year",
    }
    assert payload["variants"]["rule_only"]["status"] == "testable"


def test_pair_statistics_sorted_and_complete() -> None:
    sets = [frozenset({"A", "B"}), frozenset(), frozenset({"B"})]
    stats = pair_statistics(sets, ["A", "B", "C"])
    assert stats["N"] == 3
    assert [(p["a"], p["b"]) for p in stats["pairs"]] == [("A", "B"), ("A", "C"), ("B", "C")]
    assert stats["pairs"][1]["lift"] is None  # C never occurs


def test_build_is_deterministic_and_order_independent() -> None:
    first = json.dumps(_build(_toy()), sort_keys=True)
    second = json.dumps(_build(_toy()), sort_keys=True)
    reordered = json.dumps(_build(list(reversed(_toy()))), sort_keys=True)
    assert first == second == reordered


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_tag_cooccurrence", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cli_paths(tmp_path: Path) -> dict[str, Path]:
    snapshot = tmp_path / "labels_snapshot_v1.parquet"
    write_snapshot(snapshot, snapshot_rows(_toy()))
    taxonomy = tmp_path / "taxonomy.yml"
    taxonomy.write_text(yaml.safe_dump(TAXONOMY), encoding="utf-8")
    return {
        "snapshot": snapshot,
        "taxonomy": taxonomy,
        "output": tmp_path / "tag_cooccurrence.json",
    }


def _argv(paths: dict[str, Path], *extra: str) -> list[str]:
    return [
        "--snapshot",
        str(paths["snapshot"]),
        "--taxonomy",
        str(paths["taxonomy"]),
        "--output",
        str(paths["output"]),
        "--as-of",
        "2026-11-25",
        *extra,
    ]


def test_cli_build_is_byte_identical_and_check_detects_staleness(
    cli_paths: dict[str, Path],
) -> None:
    script = _load_script()
    assert script.main(_argv(cli_paths)) == 0
    first = cli_paths["output"].read_bytes()
    assert script.main(_argv(cli_paths)) == 0
    assert cli_paths["output"].read_bytes() == first
    assert script.main(_argv(cli_paths, "--check")) == 0

    cli_paths["output"].write_bytes(first.replace(b'"N": 5', b'"N": 6', 1))
    assert script.main(_argv(cli_paths, "--check")) == 1


def test_cli_check_fails_when_missing_and_skips_without_inputs(
    cli_paths: dict[str, Path], tmp_path: Path
) -> None:
    script = _load_script()
    assert script.main(_argv(cli_paths, "--check")) == 1
    absent = dict(cli_paths, snapshot=tmp_path / "missing.parquet")
    assert script.main(_argv(absent, "--check")) == 0
    assert script.main(_argv(absent)) == 1
