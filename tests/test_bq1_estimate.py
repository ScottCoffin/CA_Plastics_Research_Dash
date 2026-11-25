"""Tests for the BQ-1.1 corpus-quality estimators (atlas.nlp.quality and scripts/bq1_estimate.py).

Hand-computed values use small synthetic strata. Nothing under data/ or curation/ is changed; the
real-path test writes only under pytest tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from pathlib import Path

import pytest

from atlas.nlp import quality as q

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "bq1_estimate.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("bq1_estimate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules.setdefault("bq1_estimate", module)
    spec.loader.exec_module(module)
    return module


def test_wilson_interval_hand_values():
    lo, hi = q.wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-4)
    assert hi == pytest.approx(0.7634, abs=1e-4)
    lo0, hi0 = q.wilson_interval(0, 10)
    assert lo0 == 0.0
    assert hi0 == pytest.approx(0.2775, abs=1e-4)
    assert q.wilson_interval(0, 0) == (None, None)
    with pytest.raises(ValueError):
        q.wilson_interval(11, 10)


def test_zero_hit_bound_matches_p3_rule():
    assert q.zero_hit_upper_bound(100) == pytest.approx(0.0295, abs=5e-5)
    assert q.zero_hit_upper_bound(100) == pytest.approx(1 - 0.05 ** (1 / 100))
    assert q.clopper_pearson_upper(0, 100) == pytest.approx(q.zero_hit_upper_bound(100), abs=1e-9)
    assert q.zero_hit_upper_bound(0) is None


def test_clopper_pearson_hand_values():
    # Exact two-sided 95% interval for 5 of 100 (standard tables): (0.0164, 0.1128).
    lo, hi = q.clopper_pearson_interval(5, 100)
    assert lo == pytest.approx(0.01643, abs=1e-4)
    assert hi == pytest.approx(0.11283, abs=1e-4)
    assert q.clopper_pearson_upper(5, 100) == pytest.approx(0.10225, abs=1e-4)
    assert q.clopper_pearson_lower(5, 100) == pytest.approx(0.01991, abs=1e-4)
    assert q.clopper_pearson_upper(100, 100) == 1.0
    assert q.clopper_pearson_lower(0, 100) == 0.0


def test_p3_bound_low_band():
    zero = q.p3_bound(0, 100)
    assert zero["point"] == 0.0
    assert zero["upper_bound"] == pytest.approx(0.0295, abs=5e-5)
    hit = q.p3_bound(5, 100)
    assert hit["point"] == pytest.approx(0.05)
    assert hit["upper_bound"] == pytest.approx(0.10225, abs=1e-4)


def test_stratified_mean_and_variance_hand_values():
    # Stratum A: N=100, draws [1,1,0,1] -> p_A = 0.75, s_A^2 = 0.25.
    # Stratum B: N=300, draws [0,0,1,0,0,0] -> p_B = 1/6, s_B^2 = 1/6.
    # Point = (100 * 0.75 + 300 / 6) / 400 = 0.3125.
    # Variance = (100^2 * 0.96 * 0.25 / 4 + 300^2 * 0.98 * (1/6) / 6) / 400^2 = 3050 / 160000.
    res = q.stratified_ratio(
        [
            (100, [1, 1, 0, 1], [1, 1, 1, 1]),
            (300, [0, 0, 1, 0, 0, 0], [1, 1, 1, 1, 1, 1]),
        ]
    )
    assert res["point"] == pytest.approx(0.3125)
    assert res["variance"] == pytest.approx(3050 / 160000)
    assert res["se"] == pytest.approx(math.sqrt(3050 / 160000))
    assert res["n_units"] == 10


def test_stratified_single_draw_is_unestimable():
    res = q.stratified_ratio([(10, [1], [1]), (20, [0, 1, 1], [1, 1, 1])])
    assert res["point"] is not None
    assert res["variance"] is None


def test_psu_ratio_hand_values():
    # M = 4 strata, n = 2 drawn: (N=10, y=1), (N=30, y=0). p = 10 / 40 = 0.25.
    # t = [7.5, -7.5], s_t^2 = 112.5, f = 0.5, D = 40.
    # Var = (1 - f) * n * s_t^2 / D^2 = 0.5 * 2 * 112.5 / 1600 = 0.0703125.
    res = q.psu_ratio([(10, 1, 1), (30, 0, 1)], 4)
    assert res["point"] == pytest.approx(0.25)
    assert res["variance"] == pytest.approx(0.0703125)


def test_ht_inclusion_and_weights_for_pool():
    # 500 of 873 strata drawn, one work per drawn stratum: pi = (500/873)/N_h, weight = 1.746 * N_h.
    pi_one = q.ht_inclusion_probability(500, 873, 1)
    assert pi_one == pytest.approx(500 / 873)
    assert q.ht_weight(pi_one) == pytest.approx(1.746, abs=1e-3)
    assert q.ht_weight(q.ht_inclusion_probability(500, 873, 4)) == pytest.approx(
        4 * 1.746, abs=4e-3
    )
    with pytest.raises(ValueError):
        q.ht_inclusion_probability(900, 873, 1)


def test_kish_design_effect_and_design_effect_vs_srs():
    # weights [1, 1, 1, 3]: deff = 4 * 12 / 36 = 4/3, effective n = 3.
    kish = q.kish_design_effect([1, 1, 1, 3])
    assert kish["deff_weights"] == pytest.approx(4 / 3)
    assert kish["n_effective"] == pytest.approx(3.0)
    # variance 0.02 with p = 0.5 and n = 100 gives deff = 0.02 / (0.25 / 100) = 8.
    assert q.design_effect(0.02, 0.5, 100) == pytest.approx(8.0)
    assert q.design_effect(None, 0.5, 100) is None


def test_weighted_share_matches_weighted_ratio():
    # (weight, numerator, denominator): domain rows have denominator 1.
    share = q.weighted_share([(2.0, 1, 1), (1.0, 0, 1), (1.0, 1, 0)])
    assert share["point"] == pytest.approx(2 / 3)
    assert share["n"] == 2
    assert share["n_effective"] == pytest.approx(9 / 5)


def test_percentile_interval_hand_values():
    values = [float(i) for i in range(11)]  # 0..10
    lo, hi = q.percentile_interval(values)
    assert lo == pytest.approx(0.25)
    assert hi == pytest.approx(9.75)


def test_bootstrap_is_deterministic_and_uses_seed():
    rows = [("a", 1.0), ("a", 3.0), ("b", 0.0), ("c", 2.0), ("d", 4.0), ("d", 4.0)]

    def stat(sample):
        return sum(v for _, v in sample) / len(sample)

    first = q.cluster_bootstrap_replicates(rows, lambda r: r[0], stat, B=50, seed=7)
    again = q.cluster_bootstrap_replicates(rows, lambda r: r[0], stat, B=50, seed=7)
    other = q.cluster_bootstrap_replicates(rows, lambda r: r[0], stat, B=50, seed=8)
    assert first == again
    assert first != other
    assert len(first) == 50


def test_bootstrap_resamples_whole_clusters():
    # Clusters sorted by name: a, b, c. One replicate draws three clusters with replacement.
    rows = [("a", 1.0), ("a", 1.0), ("b", 0.0), ("c", 10.0)]
    rng = random.Random(3)
    picks = [rng.randrange(3) for _ in range(3)]
    expected_members = {"a": [1.0, 1.0], "b": [0.0], "c": [10.0]}
    keys = ["a", "b", "c"]
    expected_values = [v for k in (keys[i] for i in picks) for v in expected_members[k]]
    expected = sum(expected_values) / len(expected_values)
    reps = q.cluster_bootstrap_replicates(
        rows, lambda r: r[0], lambda s: sum(v for _, v in s) / len(s), B=1, seed=3
    )
    assert reps == [pytest.approx(expected)]


def test_bootstrap_degenerate_when_clusters_identical():
    rows = [("a", 0.5), ("b", 0.5), ("c", 0.5)]
    reps = q.cluster_bootstrap_replicates(
        rows, lambda r: r[0], lambda s: sum(v for _, v in s) / len(s), B=20, seed=1
    )
    assert q.percentile_interval(reps) == pytest.approx([0.5, 0.5])


def test_cohen_kappa_hand_value():
    # 40 rows; 15 gold positive, 15 predicted positive, agreement 0.85.
    # pe = 0.375^2 + 0.625^2 = 0.53125, kappa = (0.85 - 0.53125) / (1 - 0.53125) = 0.68.
    gold = [True] * 15 + [False] * 25
    pred = [True] * 12 + [False] * 3 + [True] * 3 + [False] * 22
    assert q.cohen_kappa(gold, pred) == pytest.approx(0.68)


def test_study_type_flags_thresholds():
    # 14 gold positives: below the 15-positive floor, so insufficient_data only.
    gold14 = ["review"] * 14 + ["other"] * 26
    res14 = q.study_type_metrics(gold14, gold14)["review"]
    assert res14["n_positive"] == 14
    assert res14["flags"] == ["insufficient_data", "below_target_40"]

    # 15 positives: F1 0.80 (>= 0.70) but kappa 0.68 (< 0.70) -> experimental on kappa only.
    gold = ["review"] * 15 + ["other"] * 25
    pred = ["review"] * 12 + ["other"] * 3 + ["review"] * 3 + ["other"] * 22
    res = q.study_type_metrics(gold, pred)["review"]
    assert res["n_positive"] == 15
    assert res["f1"] == pytest.approx(0.8)
    assert res["kappa"] == pytest.approx(0.68)
    assert res["flags"] == ["experimental_kappa", "below_target_40"]

    # Perfect agreement over 40 positives: no flags.
    perfect = ["review"] * 40 + ["other"] * 10
    clean = q.study_type_metrics(perfect, perfect)["review"]
    assert clean["flags"] == []


def test_tag_f1_flags():
    gold = [frozenset({"a"})] * 20 + [frozenset()] * 10
    pred = [frozenset({"a"})] * 16 + [frozenset()] * 14
    res = q.tag_f1(gold, pred, ["a", "b"])
    assert res["a"]["n_positive"] == 20
    # TP 16, FN 4, FP 0 -> F1 = 32 / 36.
    assert res["a"]["f1"] == pytest.approx(32 / 36)
    assert res["a"]["flags"] == []
    assert res["b"]["n_positive"] == 0
    assert res["b"]["flags"] == ["insufficient_data"]


def test_e3_refuses_training_and_dev_rows():
    train_row = {"split": "train", "gold_pr": True, "pred_pr": True}
    dev_row = {"split": "dev", "gold_pr": True, "pred_pr": True}
    with pytest.raises(ValueError):
        q.e3_current_model([train_row])
    with pytest.raises(ValueError):
        q.e3_current_model([{"split": "test", "gold_pr": True, "pred_pr": True}, dev_row])


def test_e3_uses_held_out_rows_only():
    rows = [
        {"split": "test", "gold_pr": True, "pred_pr": True},
        {"split": "test", "gold_pr": True, "pred_pr": False},
        {"split": "test", "gold_pr": False, "pred_pr": True},
        {"split": "test", "gold_pr": False, "pred_pr": False},
    ]
    res = q.e3_current_model(rows)
    assert res["n"] == 4
    assert res["precision"]["point"] == pytest.approx(0.5)
    assert res["recall"]["point"] == pytest.approx(0.5)
    assert res["f1"] == pytest.approx(0.5)


def test_e3_refuses_non_test_rows_even_when_mixed():
    with pytest.raises(ValueError):
        q.e3_current_model(
            [
                {"split": "test", "gold_pr": True, "pred_pr": True},
                {"split": "train", "gold_pr": True, "pred_pr": True},
            ]
        )


def test_synthetic_cli_report_schema_and_determinism(tmp_path):
    cli = _load_cli()
    out_a = tmp_path / "a.json"
    out_b = tmp_path / "b.json"
    assert cli.main(["--synthetic", "--out", str(out_a)]) == 0
    assert cli.main(["--synthetic", "--out", str(out_b)]) == 0
    a = json.loads(out_a.read_text(encoding="utf-8"))
    b = json.loads(out_b.read_text(encoding="utf-8"))
    assert a["schema"] == "bq1-v1"
    assert a["mode"] == "synthetic"
    assert a["bootstrap_B"] == 1000
    assert a["seed"] == q.BOOTSTRAP_SEED
    assert set(a["estimands"]) == set(cli.ESTIMANDS)
    assert a["estimands"]["E1"]["interval"] == b["estimands"]["E1"]["interval"]
    assert "adaptive_allocation_note" in a and "-1.18%" in a["adaptive_allocation_note"]
    assert a["estimands"]["E1"]["method"].startswith("two-stage HT ratio")
    assert 0.0 <= a["estimands"]["E1"]["point"] <= 1.0
    assert a["estimands"]["E1g"]["design_notes"][0] == cli.ADAPTIVE_NOTE


def test_real_path_without_labels_writes_no_gold_yet(tmp_path):
    cli = _load_cli()
    empty_sheet = tmp_path / "sheet.csv"
    empty_sheet.write_text(
        "work_id,split,sample_role,plastic_related,decision_status\nW1,test,pool,,\n",
        encoding="utf-8",
    )
    real = cli.load_gold_rows(
        ca_sheet=empty_sheet,
        global_sheet=tmp_path / "missing_global.csv",
        design=tmp_path / "missing_design.json",
        global_draws=tmp_path / "missing_draws.csv",
        predictions=None,
    )
    report = cli.build_report(synthetic=False, real=real, min_n=30, generated_at="T")
    assert report["status"] == "no_gold_yet"
    assert set(report["estimands"]) == set(cli.ESTIMANDS)
    assert all(v == {"status": "no_gold_yet"} for v in report["estimands"].values())


def test_real_path_labels_without_predictions_is_gated(tmp_path):
    cli = _load_cli()
    design = {
        "rows": [
            {
                "work_id": "W1",
                "sample_role": "pool",
                "split": "test",
                "design_weight": 1.746,
                "N_h": 1,
                "stratum": {"key": "s1"},
                "author_group": "g1",
            },
            {
                "work_id": "W2",
                "sample_role": "pool",
                "split": "train",
                "design_weight": 1.746,
                "N_h": 1,
                "stratum": {"key": "s2"},
                "author_group": "g2",
            },
        ],
        "strata_count": 873,
    }
    design_path = tmp_path / "design.json"
    design_path.write_text(json.dumps(design), encoding="utf-8")
    sheet = tmp_path / "sheet.csv"
    sheet.write_text(
        "work_id,split,sample_role,year,abstract,plastic_related,plastic_tier,decision_status\n"
        "W1,test,pool,2010,abs,true,core,complete\n"
        "W2,train,pool,2011,,,,\n",
        encoding="utf-8",
    )
    real = cli.load_gold_rows(
        ca_sheet=sheet,
        global_sheet=tmp_path / "none.csv",
        design=design_path,
        global_draws=tmp_path / "none_draws.csv",
        predictions=None,
    )
    assert real["coverage"]["ca_labelled"] == 1
    assert real["coverage"]["ca_designed"] == 2
    report = cli.build_report(synthetic=False, real=real, min_n=30, generated_at="T")
    assert report["status"] == "incomplete_gold"
    assert report["estimands"]["E1"]["status"] == "missing_predictions"
    assert report["estimands"]["E1g"]["status"] == "no_gold_yet"
