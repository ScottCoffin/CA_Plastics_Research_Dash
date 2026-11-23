"""Offline checks for the BQ-G2 label-blind gold design freeze and the guide-example exclusion."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

from atlas.nlp.sampling import build_split_rows
from scripts.build_gold_design import inclusion_probabilities, round_robin_plan
from scripts.check_s4_2 import (
    GUIDE_EXAMPLES,
    assert_guide_examples_excluded,
    check_guide_examples,
    normalize_doi,
)

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "curation" / "gold_design_v1.json"
SPLITS = ROOT / "curation" / "splits_v2.csv"
MANIFEST = ROOT / "curation" / "splits_v2_manifest.json"
BUILDER = ROOT / "scripts" / "build_gold_design.py"
TOP_KEYS = {
    "estimator_note",
    "expected_sample_size",
    "frozen_at_commit",
    "gazetteer_hits",
    "generated_at",
    "gold_labels_note",
    "guide_examples",
    "label_blind",
    "manifest",
    "pipeline_snapshots",
    "pool_population",
    "rows",
    "schema",
    "selection_reproduced",
    "sampled_strata_count",
    "source_snapshot",
    "splits_file",
    "splits_reproduced",
    "strata_count",
    "weighting",
}
ROW_KEYS = {
    "author_group",
    "design",
    "design_weight",
    "incl_prob",
    "incl_prob_within_stratum",
    "n_h",
    "N_h",
    "pipeline_at_first_labels",
    "pipeline_at_freeze",
    "sample_role",
    "split",
    "stratum",
    "weight_within_stratum",
    "work_id",
}
PIPELINE_KEYS = {
    "confidence",
    "domain_tags",
    "label_source",
    "model_version",
    "plastic_related",
    "plastic_score",
    "plastic_tier",
    "query_version",
    "relevance_assist",
}
RELEVANCE_KEYS = {
    "assist_plastic_related",
    "confidence",
    "owner_review",
    "plastic_related",
    "reviewer",
}
LEAK_NULL_FIELDS = (
    "N_h",
    "n_h",
    "incl_prob",
    "design_weight",
    "incl_prob_within_stratum",
    "weight_within_stratum",
)


def _design() -> dict:
    return json.loads(DESIGN.read_text(encoding="utf-8"))


def _split_rows() -> list[dict]:
    with SPLITS.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _sha256(path: Path) -> str:
    import hashlib

    # CRLF folded to LF: a Windows working copy and a CI checkout must hash the same.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _guide_rows() -> list[dict]:
    with GUIDE_EXAMPLES.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_committed_json_schema() -> None:
    design = _design()
    assert set(design) == TOP_KEYS
    assert design["schema"] == "gold-design-v1"
    assert re.fullmatch(r"[0-9a-f]{40}", design["frozen_at_commit"])
    assert isinstance(design["pool_population"], int) and design["pool_population"] > 0
    assert isinstance(design["strata_count"], int) and design["strata_count"] > 0
    assert 0 < design["sampled_strata_count"] <= design["strata_count"]
    for row in design["rows"]:
        assert set(row) == ROW_KEYS
        assert set(row["pipeline_at_freeze"]) == PIPELINE_KEYS
        assert set(row["pipeline_at_first_labels"]) == PIPELINE_KEYS
        if row["pipeline_at_freeze"]["relevance_assist"] is not None:
            assert set(row["pipeline_at_freeze"]["relevance_assist"]) == RELEVANCE_KEYS


def test_provenance_hashes_and_flags() -> None:
    design = _design()
    assert design["label_blind"] is True
    assert design["selection_reproduced"] is True
    assert design["splits_reproduced"] is True
    assert design["splits_file"] == {"path": "curation/splits_v2.csv", "sha256": _sha256(SPLITS)}
    assert design["manifest"]["sha256"] == _sha256(MANIFEST)
    assert design["manifest"]["seed"] == 42042
    assert design["source_snapshot"]["hashes_verified"] is True
    assert re.fullmatch(r"[0-9a-f]{40}", design["source_snapshot"]["commit"])
    assert "were never merged into exports" in design["gold_labels_note"]
    for name in ("at_freeze", "at_first_labels"):
        state = design["pipeline_snapshots"][name]
        for key in ("work_labels_parquet_sha256", "work_relevance_csv_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", state[key])
        assert state["query_version"] == "plastic-v3.1"


def test_every_split_row_is_present_once() -> None:
    design = _design()
    split_rows = _split_rows()
    ids = [row["work_id"] for row in design["rows"]]
    assert len(ids) == len(set(ids)) == len(split_rows)
    by_id = {row["work_id"]: row for row in design["rows"]}
    for split in split_rows:
        row = by_id[split["work_id"]]
        assert row["sample_role"] == split["sample_role"]
        assert row["split"] == split["split"]
        assert row["author_group"] == split["author_group"]


def test_pool_weights_are_consistent() -> None:
    pool = [row for row in _design()["rows"] if row["sample_role"] == "pool"]
    assert len(pool) == 500
    prob_by_stratum: dict[str, set[float]] = {}
    for row in pool:
        size, taken = row["N_h"], row["n_h"]
        assert isinstance(size, int) and isinstance(taken, int) and 1 <= taken <= size
        assert row["incl_prob_within_stratum"] == pytest.approx(taken / size, rel=1e-12)
        assert row["weight_within_stratum"] == pytest.approx(size / taken, rel=1e-12)
        assert 0 < row["incl_prob"] <= 1
        assert row["design_weight"] == pytest.approx(1 / row["incl_prob"], rel=1e-12)
        key = row["stratum"]["key"]
        assert key == "|".join(row["stratum"]["values"])
        prob_by_stratum.setdefault(key, set()).add(round(row["incl_prob"], 12))
    # Equal inclusion probability for every work within a stratum.
    assert all(len(values) == 1 for values in prob_by_stratum.values())


def test_pool_counts_match_the_frame() -> None:
    design = _design()
    pool = [row for row in design["rows"] if row["sample_role"] == "pool"]
    strata = {row["stratum"]["key"]: (row["N_h"], row["n_h"]) for row in pool}
    assert design["sampled_strata_count"] == len(strata)
    assert sum(taken for _, taken in strata.values()) == len(pool)
    assert sum(size for size, _ in strata.values()) <= design["pool_population"]
    assert design["expected_sample_size"] == pytest.approx(len(pool), abs=1e-6)


def test_design_weights_expand_each_stratum_by_strata_over_sample_size() -> None:
    # With no full rounds, every stratum has the same chance of being drawn, so
    # design_weight = (strata / sample size) * N_h. This is the expansion the design uses.
    design = _design()
    assert design["weighting"]["full_rounds"] == 0
    pool = [row for row in design["rows"] if row["sample_role"] == "pool"]
    factor = design["strata_count"] / len(pool)
    for row in pool:
        assert row["design_weight"] == pytest.approx(factor * row["N_h"], rel=1e-9)


def test_leak_rows_are_purposive_without_weights() -> None:
    leak = [row for row in _design()["rows"] if row["sample_role"] == "leak_test"]
    assert len(leak) == 80
    for row in leak:
        assert row["design"] == "purposive"
        assert row["stratum"] == {"key": "leak_test", "values": None}
        assert row["split"] == "test"
        for field in LEAK_NULL_FIELDS:
            assert row[field] is None


def test_builder_refuses_to_overwrite_without_force(tmp_path, monkeypatch) -> None:
    from scripts import build_gold_design

    existing = tmp_path / "gold_design_v1.json"
    existing.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_gold_design.py", "--out", str(existing)])
    with pytest.raises(SystemExit, match="--force"):
        build_gold_design.main()
    assert existing.read_text(encoding="utf-8") == "{}\n"


def test_builder_source_is_label_blind() -> None:
    text = BUILDER.read_text(encoding="utf-8").lower()
    assert "annotation" not in text
    assert "gold_works" not in text and "gold_grants" not in text


def test_round_robin_plan_small_cases() -> None:
    assert round_robin_plan([1, 2, 3, 4], 4) == (1, 0)
    assert round_robin_plan([1, 2, 3, 4], 5) == (1, 1)
    assert round_robin_plan([2, 2], 4) == (2, 0)
    assert round_robin_plan([1, 1, 2], 10) == (2, 0)
    assert round_robin_plan([3] * 10, 12) == (1, 2)


@pytest.mark.parametrize(
    ("frame", "sample"),
    [([1, 2, 3, 4], 4), ([1, 2, 3, 4], 5), ([5, 1, 1, 3, 8], 7), ([3] * 10, 12), ([1] * 9, 4)],
)
def test_inclusion_probabilities_sum_to_sample_size(frame: list[int], sample: int) -> None:
    sizes = dict(enumerate(frame))
    probs = inclusion_probabilities(sizes, sample)
    assert sum(sizes[key] * probs[key] for key in sizes) == pytest.approx(sample, abs=1e-9)
    assert all(0 < prob <= 1 for prob in probs.values())


def test_inclusion_probabilities_match_simulated_selection() -> None:
    # Strata of sizes 1, 2, 3, 4 keyed by journal type; five picks per draw; fixed seeds.
    sizes = [1, 2, 3, 4]
    records = []
    for stratum, size in enumerate(sizes):
        for index in range(size):
            records.append(
                {
                    "work_id": f"W{stratum}{index}",
                    "ca_any_author": True,
                    "year": 2021,
                    "type": f"type{stratum}",
                    "oa_status": "closed",
                    "institution_type": "uc",
                    "title": "t",
                    "abstract": "",
                    "author_ids": [f"A{stratum}{index}"],
                }
            )
    probs = inclusion_probabilities(dict(enumerate(sizes)), 5)
    trials = 400
    hits: Counter[str] = Counter()
    for seed in range(trials):
        for row in build_split_rows(records, seed=seed, sample_size=5, leak_test_size=0):
            hits[row["work_id"]] += 1
    for record in records:
        stratum = int(record["work_id"][1])
        assert hits[record["work_id"]] / trials == pytest.approx(probs[stratum], abs=0.08)


def test_guide_example_exclusion_holds_on_real_files(monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    note = check_guide_examples()
    assert "absent from splits_v1 and splits_v2" in note


def test_guide_example_exclusion_fails_on_work_id_fixture() -> None:
    guides = _guide_rows()
    guide_id = next(row["work_id"] for row in guides if row["work_id"].strip())
    frames = {"splits_v2": [{"work_id": "W1"}, {"work_id": guide_id}]}
    with pytest.raises(AssertionError, match="appears in splits_v2"):
        assert_guide_examples_excluded(guides, frames, {})


def test_guide_example_exclusion_fails_on_doi_fixture() -> None:
    guides = _guide_rows()
    doi = next(normalize_doi(row["doi"]) for row in guides if row["doi"].strip())
    frames = {"splits_v2": [{"work_id": "W1"}]}
    with pytest.raises(AssertionError, match="DOI"):
        assert_guide_examples_excluded(guides, frames, {"W1": f"https://doi.org/{doi.upper()}"})


def test_guide_example_exclusion_passes_on_clean_fixture() -> None:
    guides = _guide_rows()
    frames = {"splits_v2": [{"work_id": "W1"}, {"work_id": "W2", "doi": "https://doi.org/10.1/x"}]}
    expected = sum(bool(row["work_id"].strip() or row["doi"].strip()) for row in guides)
    assert assert_guide_examples_excluded(guides, frames, {"W1": ""}) == expected


def test_guide_example_check_requires_guide_rows() -> None:
    with pytest.raises(AssertionError, match="vacuous"):
        assert_guide_examples_excluded([{"role": "other", "work_id": "W9", "doi": ""}], {}, {})
