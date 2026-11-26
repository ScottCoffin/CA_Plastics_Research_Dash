"""Inter-rater agreement statistics for paired categorical labels (Add-on A4, CG-7a).

Pure Python and generic: each function takes two equal-length sequences of labels (one per rater,
paired by position) and returns a float, or None when the statistic is undefined (no pairs, or
expected disagreement of zero). Rounding is left to the caller. Wilson intervals come from
``atlas.nlp.quality``; ``bootstrap_interval`` gives percentile intervals over paired resamples.

Formulas (n pairs, k categories):

* observed agreement p_o = share of pairs where the two labels are identical;
* weighted kappa = 1 - sum(d_ij O_ij) / sum(d_ij E_ij), with disagreement weights
  d_ij = ((i - j) / (k - 1)) ** 2 ("quadratic") or |i - j| / (k - 1) ("linear");
* PABAK = (k p_o - 1) / (k - 1);
* Gwet's AC1 = (p_o - p_e) / (1 - p_e), with p_e = sum_q pi_q (1 - pi_q) / (k - 1) and pi_q the
  share of all 2n labels that are category q.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable, Hashable, Sequence

from atlas.nlp.quality import wilson_interval  # re-exported for convenience of callers

__all__ = [
    "bootstrap_interval",
    "gwet_ac1",
    "observed_agreement",
    "pabak",
    "prevalence",
    "weighted_kappa",
    "wilson_interval",
]

BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 20261126


def _check_pairs(
    a: Sequence[Hashable], b: Sequence[Hashable], categories: Sequence[Hashable]
) -> None:
    if len(a) != len(b):
        raise ValueError(f"rater label lists differ in length: {len(a)} and {len(b)}")
    allowed = set(categories)
    for label in (*a, *b):
        if label not in allowed:
            raise ValueError(f"label {label!r} is not in the category list")


def observed_agreement(a: Sequence[Hashable], b: Sequence[Hashable]) -> float | None:
    """Share of pairs where both raters gave the same label (None when there are no pairs)."""
    if len(a) != len(b):
        raise ValueError(f"rater label lists differ in length: {len(a)} and {len(b)}")
    if not a:
        return None
    return sum(1 for x, y in zip(a, b, strict=True) if x == y) / len(a)


def prevalence(a: Sequence[Hashable], b: Sequence[Hashable]) -> float | None:
    """Share of the most frequent category over both raters' 2n labels (None when no pairs)."""
    if len(a) != len(b):
        raise ValueError(f"rater label lists differ in length: {len(a)} and {len(b)}")
    if not a:
        return None
    counts = Counter([*a, *b])
    return max(counts.values()) / (2 * len(a))


def weighted_kappa(
    a: Sequence[Hashable],
    b: Sequence[Hashable],
    categories: Sequence[Hashable],
    weights: str = "quadratic",
) -> float | None:
    """Cohen's weighted kappa for ordinal categories given in order (None when undefined)."""
    if weights not in ("quadratic", "linear"):
        raise ValueError(f"unknown weighting {weights!r}")
    _check_pairs(a, b, categories)
    n = len(a)
    k = len(categories)
    if n == 0 or k < 2:
        return None
    index = {category: position for position, category in enumerate(categories)}
    observed = [[0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        observed[index[x]][index[y]] += 1
    rows = [sum(observed[i]) for i in range(k)]
    cols = [sum(observed[i][j] for i in range(k)) for j in range(k)]

    def disagreement(i: int, j: int) -> float:
        distance = abs(i - j) / (k - 1)
        return distance * distance if weights == "quadratic" else distance

    numerator = sum(disagreement(i, j) * observed[i][j] for i in range(k) for j in range(k))
    denominator = sum(
        disagreement(i, j) * rows[i] * cols[j] / n for i in range(k) for j in range(k)
    )
    if denominator == 0:
        return None
    return 1 - numerator / denominator


def pabak(
    a: Sequence[Hashable], b: Sequence[Hashable], categories: Sequence[Hashable]
) -> float | None:
    """Prevalence-adjusted bias-adjusted kappa: (k p_o - 1) / (k - 1) (None when undefined)."""
    _check_pairs(a, b, categories)
    k = len(categories)
    p_o = observed_agreement(a, b)
    if p_o is None or k < 2:
        return None
    return (k * p_o - 1) / (k - 1)


def gwet_ac1(
    a: Sequence[Hashable], b: Sequence[Hashable], categories: Sequence[Hashable]
) -> float | None:
    """Gwet's first-order agreement coefficient (AC1) for nominal labels (None when undefined)."""
    _check_pairs(a, b, categories)
    k = len(categories)
    p_o = observed_agreement(a, b)
    if p_o is None or k < 2:
        return None
    counts = Counter([*a, *b])
    total = 2 * len(a)
    p_e = sum((counts[c] / total) * (1 - counts[c] / total) for c in categories) / (k - 1)
    if p_e == 1:
        return None
    return (p_o - p_e) / (1 - p_e)


def bootstrap_interval(
    stat_fn: Callable[[list[Hashable], list[Hashable]], float | None],
    a: Sequence[Hashable],
    b: Sequence[Hashable],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    level: float = 0.95,
) -> tuple[float | None, float | None]:
    """Percentile bootstrap interval over paired resamples; resamples giving None are skipped.

    Deterministic for a given seed. Returns (None, None) when no resample gives a value.
    """
    if len(a) != len(b):
        raise ValueError(f"rater label lists differ in length: {len(a)} and {len(b)}")
    n = len(a)
    if n == 0:
        return None, None
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(resamples):
        picks = [rng.randrange(n) for _ in range(n)]
        value = stat_fn([a[i] for i in picks], [b[i] for i in picks])
        if value is not None and not math.isnan(value):
            values.append(float(value))
    if not values:
        return None, None
    values.sort()
    tail = (1 - level) / 2
    return _percentile(values, tail), _percentile(values, 1 - tail)


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated percentile of an ascending list, q in [0, 1]."""
    position = q * (len(sorted_values) - 1)
    low = math.floor(position)
    high = min(low + 1, len(sorted_values) - 1)
    fraction = position - low
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * fraction
