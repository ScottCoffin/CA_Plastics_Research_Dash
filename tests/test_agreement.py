"""Hand-checked examples for the generic agreement statistics (Add-on A4, CG-7a)."""

from __future__ import annotations

import pytest

from atlas.agreement import (
    bootstrap_interval,
    gwet_ac1,
    observed_agreement,
    pabak,
    prevalence,
    weighted_kappa,
)
from atlas.nlp import quality

# Raters A and B on five items over three nominal categories a, b, c.
A5 = ["a", "a", "b", "c", "c"]
B5 = ["a", "b", "b", "c", "a"]
CATS3 = ["a", "b", "c"]


def test_perfect_agreement_gives_one_for_every_statistic() -> None:
    labels = ["x", "y", "z"]
    assert observed_agreement(labels, labels) == 1.0
    assert weighted_kappa(labels, labels, labels) == pytest.approx(1.0)
    assert pabak(labels, labels, labels) == pytest.approx(1.0)
    assert gwet_ac1(labels, labels, labels) == pytest.approx(1.0)
    # Two of six labels per category: the most frequent share is 1/3.
    assert prevalence(labels, labels) == pytest.approx(1 / 3)


def test_weighted_kappa_two_by_two_table_matches_cohen_kappa() -> None:
    # 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no: p_o = 0.7, p_e = 0.5, kappa = 0.4.
    a = ["y"] * 25 + ["n"] * 25
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert weighted_kappa(a, b, ["y", "n"]) == pytest.approx(0.4)
    assert weighted_kappa(a, b, ["y", "n"], weights="linear") == pytest.approx(0.4)


def test_quadratic_weighted_kappa_on_ordinal_three_category_example() -> None:
    # Observed cells (a, b): (0,0) (0,1) (1,1) (1,2) (2,2) (2,0); expected cell 2/3 each.
    # Weighted disagreement: 1.5 observed against 2.0 expected, so kappa = 1 - 1.5 / 2.0.
    a = [0, 0, 1, 1, 2, 2]
    b = [0, 1, 1, 2, 2, 0]
    assert weighted_kappa(a, b, [0, 1, 2]) == pytest.approx(0.25)


def test_pabak_follows_k_p_o_minus_one_over_k_minus_one() -> None:
    # p_o = 3/5 with k = 3 gives (3 * 0.6 - 1) / 2 = 0.4.
    assert observed_agreement(A5, B5) == pytest.approx(0.6)
    assert pabak(A5, B5, CATS3) == pytest.approx(0.4)


def test_gwet_ac1_hand_value() -> None:
    # pi = (0.4, 0.3, 0.3) over 2n labels, p_e = (0.24 + 0.21 + 0.21) / 2 = 0.33,
    # so AC1 = (0.6 - 0.33) / (1 - 0.33) = 0.27 / 0.67.
    assert gwet_ac1(A5, B5, CATS3) == pytest.approx(0.27 / 0.67)


def test_prevalence_is_the_most_frequent_share_over_both_raters() -> None:
    # Category a appears four times among ten labels.
    assert prevalence(A5, B5) == pytest.approx(0.4)


def test_undefined_statistics_return_none() -> None:
    assert weighted_kappa([], [], CATS3) is None
    assert pabak([], [], CATS3) is None
    assert gwet_ac1([], [], CATS3) is None
    assert observed_agreement([], []) is None
    assert prevalence([], []) is None
    # One category only: weights and chance agreement are undefined.
    assert pabak(["x", "x"], ["x", "x"], ["x"]) is None
    assert weighted_kappa(["x", "x"], ["x", "x"], ["x"]) is None
    # Expected disagreement is zero when both raters always give the same single category.
    assert weighted_kappa(["x", "x"], ["x", "x"], ["x", "y"]) is None


def test_invalid_inputs_raise() -> None:
    with pytest.raises(ValueError):
        observed_agreement(["a"], ["a", "b"])
    with pytest.raises(ValueError):
        weighted_kappa(["a"], ["z"], CATS3)
    with pytest.raises(ValueError):
        weighted_kappa(A5, B5, CATS3, weights="cubic")


def test_wilson_interval_is_reused_from_the_quality_module() -> None:
    from atlas.agreement import wilson_interval

    assert wilson_interval is quality.wilson_interval


def test_bootstrap_is_deterministic_for_a_seed() -> None:
    a = A5 * 4
    b = B5 * 4

    def stat(x, y):
        return observed_agreement(x, y)

    first = bootstrap_interval(stat, a, b)
    second = bootstrap_interval(stat, a, b)
    assert first == second
    lo, hi = first
    assert 0.0 <= lo <= hi <= 1.0


def test_bootstrap_of_perfect_agreement_is_a_point() -> None:
    labels = ["a", "b", "c"] * 4

    def kappa(x, y):
        return weighted_kappa(x, y, CATS3)

    assert bootstrap_interval(kappa, labels, labels) == (pytest.approx(1.0), pytest.approx(1.0))


def test_bootstrap_skips_none_and_returns_none_pair_when_undefined() -> None:
    assert bootstrap_interval(lambda x, y: None, A5, B5) == (None, None)
    assert bootstrap_interval(lambda x, y: 1.0, [], []) == (None, None)
