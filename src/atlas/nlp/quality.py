"""Pure estimators for the BQ-1.1 corpus-quality module (A3 sections 4 and 7, Module 1).

Standard library only (no scipy, no numpy). Formulas, flags and limits are documented in
``docs/QUALITY_ESTIMATORS.md``. Gold-label loading and the CLI live in ``scripts/bq1_estimate.py``.
Per-tag and per-class F1 reuse ``atlas.nlp.eval``.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Hashable, Mapping, Sequence
from typing import Any

from atlas.nlp.eval import _class_metrics

Z95 = 1.959963984540054
CONFIDENCE = 0.95
BOOTSTRAP_B = 1000
BOOTSTRAP_SEED = 20261125
DEFAULT_MIN_N = 30
E4_MIN_POSITIVES = 15
E4_TARGET_POSITIVES = 40
E4_KAPPA_MIN = 0.70
E4_F1_MIN = 0.70
HELD_OUT_SPLIT = "test"


def _wilson(p: float, n: float, z: float = Z95) -> tuple[float, float]:
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def wilson_interval(k: int, n: int, z: float = Z95) -> tuple[float | None, float | None]:
    """Wilson score interval for k successes in n trials (None when n is 0)."""
    if n <= 0:
        return None, None
    if not 0 <= k <= n:
        raise ValueError(f"k={k} outside 0..n={n}")
    return _wilson(k / n, n, z)


def zero_hit_upper_bound(n: int, confidence: float = CONFIDENCE) -> float | None:
    """One-sided exact bound for zero hits in n: 1 - (1 - confidence)^(1/n) (P3)."""
    if n <= 0:
        return None
    return 1 - (1 - confidence) ** (1 / n)


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed in log space."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0
    log_p, log_q = math.log(p), math.log1p(-p)
    log_comb = math.lgamma(n + 1)
    total = 0.0
    for i in range(k + 1):
        log_term = (
            log_comb - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * log_p + (n - i) * log_q
        )
        total += math.exp(log_term)
    return min(1.0, total)


def _solve_decreasing(f: Callable[[float], float], target: float) -> float:
    """Bisection for p in [0, 1] with f(p) = target, where f is non-increasing in p."""
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def clopper_pearson_upper(k: int, n: int, confidence: float = CONFIDENCE) -> float | None:
    """One-sided exact (Clopper-Pearson) upper bound; equals ``zero_hit_upper_bound`` when k = 0."""
    if n <= 0:
        return None
    if not 0 <= k <= n:
        raise ValueError(f"k={k} outside 0..n={n}")
    if k >= n:
        return 1.0
    alpha = 1 - confidence
    return _solve_decreasing(lambda p: binom_cdf(k, n, p), alpha)


def clopper_pearson_lower(k: int, n: int, confidence: float = CONFIDENCE) -> float | None:
    """One-sided exact (Clopper-Pearson) lower bound."""
    if n <= 0:
        return None
    if not 0 <= k <= n:
        raise ValueError(f"k={k} outside 0..n={n}")
    if k <= 0:
        return 0.0
    alpha = 1 - confidence
    return _solve_decreasing(lambda p: binom_cdf(k - 1, n, p), 1 - alpha)


def clopper_pearson_interval(
    k: int, n: int, confidence: float = CONFIDENCE
) -> tuple[float | None, float | None]:
    """Two-sided exact interval with alpha/2 in each tail (unweighted counts)."""
    if n <= 0:
        return None, None
    alpha_side = (1 - confidence) / 2
    lower = 0.0 if k <= 0 else _solve_decreasing(lambda p: binom_cdf(k - 1, n, p), 1 - alpha_side)
    upper = 1.0 if k >= n else _solve_decreasing(lambda p: binom_cdf(k, n, p), alpha_side)
    return lower, upper


def p3_bound(k: int, n: int, confidence: float = CONFIDENCE) -> dict[str, Any]:
    """P3 for a low band: point rate and one-sided upper bound (zero-hit rule when k = 0)."""
    if n <= 0:
        return {"point": None, "upper_bound": None, "k": k, "n": n}
    return {
        "point": k / n,
        "upper_bound": zero_hit_upper_bound(n, confidence)
        if k == 0
        else clopper_pearson_upper(k, n, confidence),
        "k": k,
        "n": n,
    }


def ht_inclusion_probability(strata_sampled: int, strata_in_frame: int, stratum_size: int) -> float:
    """Inclusion probability of one work in a two-stage design: P(stratum drawn) / N_h.

    For the CA pool, 500 of 873 strata are drawn and one work is taken per drawn stratum, so a
    work in a stratum of size N_h has pi = (500 / 873) / N_h (ADR-GOLD-DESIGN-HT).
    """
    if strata_in_frame <= 0 or stratum_size <= 0 or not 0 < strata_sampled <= strata_in_frame:
        raise ValueError("need 0 < sampled <= frame strata and a positive stratum size")
    return strata_sampled / strata_in_frame / stratum_size


def ht_weight(inclusion_probability: float) -> float:
    """Horvitz-Thompson weight 1 / pi."""
    if inclusion_probability <= 0:
        raise ValueError("inclusion probability must be positive")
    return 1 / inclusion_probability


def kish_design_effect(weights: Sequence[float]) -> dict[str, float | None]:
    """Kish design effect of unequal weights: deff = n * sum(w^2) / (sum w)^2."""
    n = len(weights)
    total = sum(weights)
    if n == 0 or total <= 0:
        return {"n": n, "deff_weights": None, "n_effective": None}
    sq = sum(w * w for w in weights)
    deff = n * sq / (total * total)
    return {"n": n, "deff_weights": deff, "n_effective": n / deff}


def design_effect(variance: float | None, p: float, n: int) -> float | None:
    """Design effect against simple random sampling: var_design / (p (1 - p) / n)."""
    if variance is None or n <= 0 or not 0 < p < 1:
        return None
    return variance / (p * (1 - p) / n)


def weighted_share(triples: Sequence[tuple[float, float, float]]) -> dict[str, Any]:
    """Weighted ratio sum(w num) / sum(w den) with a Wilson interval on the Kish effective n.

    ``triples`` holds (weight, numerator, denominator) per work; numerator and denominator are
    0/1 indicators. Used for breakdowns (descriptive), not for headline estimands.
    """
    den_rows = [(w, a) for w, a, b in triples if b]
    n = len(den_rows)
    den_w = sum(w for w, _ in den_rows)
    if n == 0 or den_w <= 0:
        return {"point": None, "interval": None, "n": n, "n_effective": None}
    p = sum(w * a for w, a in den_rows) / den_w
    n_eff = den_w * den_w / sum(w * w for w, _ in den_rows)
    return {
        "point": p,
        "interval": list(_wilson(p, n_eff)),
        "n": n,
        "n_effective": n_eff,
    }


def psu_ratio(units: Sequence[tuple[float, float, float]], population_units: int) -> dict[str, Any]:
    """Two-stage design with one work per sampled stratum (A3 4.3; ADR-GOLD-DESIGN-HT).

    ``units`` holds (N_h, numerator, denominator) per sampled stratum; ``population_units`` is M,
    the number of strata in the frame. The estimator is the ratio sum(N num) / sum(N den). The
    variance is the linearised between-stratum variance with f = n / M:
    Var = (1 - f) * n * s_t^2 / D^2, where t_h = N_h (num_h - p den_h), D = sum(N_h den_h) and
    s_t^2 is the sample variance of t over the n sampled strata.
    """
    n = len(units)
    if n == 0:
        return {"point": None, "variance": None, "se": None, "interval": None, "n_units": 0}
    if population_units < n:
        raise ValueError("population_units must be at least the number of sampled units")
    denom = sum(big_n * den for big_n, _, den in units)
    if denom <= 0:
        return {"point": None, "variance": None, "se": None, "interval": None, "n_units": n}
    numer = sum(big_n * num for big_n, num, _ in units)
    p = numer / denom
    if n < 2:
        return {"point": p, "variance": None, "se": None, "interval": None, "n_units": n}
    t = [big_n * (num - p * den) for big_n, num, den in units]
    t_bar = sum(t) / n
    s2 = sum((x - t_bar) ** 2 for x in t) / (n - 1)
    fpc = 1 - n / population_units
    var = fpc * n * s2 / (denom * denom)
    return _normal_result(p, var, n)


def stratified_ratio(
    strata: Sequence[tuple[float, Sequence[float], Sequence[float]]],
) -> dict[str, Any]:
    """Stratified design with several draws per stratum (SRS without replacement inside strata).

    ``strata`` holds (N_h, numerators, denominators) per stratum, with one entry per drawn work.
    The point estimate is sum(N_h mean(num)) / sum(N_h mean(den)). The variance is
    sum_h N_h^2 (1 - n_h / N_h) s_h^2 / n_h over the residuals z = num - p den, divided by D^2.
    A stratum with one draw and a non-zero sampling fraction makes the variance unestimable.
    """
    denom = 0.0
    numer = 0.0
    for big_n, nums, dens in strata:
        if not nums:
            continue
        denom += big_n * sum(dens) / len(dens)
        numer += big_n * sum(nums) / len(nums)
    if denom <= 0:
        return {"point": None, "variance": None, "se": None, "interval": None, "n_units": 0}
    p = numer / denom
    total = 0.0
    unestimable = False
    n_units = 0
    for big_n, nums, dens in strata:
        n_h = len(nums)
        n_units += n_h
        if n_h == 0:
            continue
        fpc = 1 - n_h / big_n if big_n > 0 else 0.0
        if fpc <= 0:
            continue
        if n_h < 2:
            unestimable = True
            continue
        z = [a - p * b for a, b in zip(nums, dens, strict=True)]
        z_bar = sum(z) / n_h
        s2 = sum((v - z_bar) ** 2 for v in z) / (n_h - 1)
        total += big_n * big_n * fpc * s2 / n_h
    if unestimable:
        return _normal_result(p, None, n_units)
    return _normal_result(p, total / (denom * denom), n_units)


def _normal_result(p: float, var: float | None, n: int) -> dict[str, Any]:
    if var is None:
        return {"point": p, "variance": None, "se": None, "interval": None, "n_units": n}
    se = math.sqrt(max(var, 0.0))
    interval = [max(0.0, p - Z95 * se), min(1.0, p + Z95 * se)]
    return {"point": p, "variance": var, "se": se, "interval": interval, "n_units": n}


def cluster_bootstrap_replicates(
    rows: Sequence[Any],
    cluster_of: Callable[[Any], Hashable],
    stat: Callable[[list[Any]], float | None],
    *,
    B: int = BOOTSTRAP_B,
    seed: int = BOOTSTRAP_SEED,
) -> list[float]:
    """Resample clusters (author groups) with replacement B times; return the statistic replicates.

    Clusters are ordered by ``str(key)`` and drawn with ``random.Random(seed).randrange``, so the
    replicates are identical for identical inputs and seed.
    """
    groups: dict[Hashable, list[Any]] = {}
    for row in rows:
        groups.setdefault(cluster_of(row), []).append(row)
    keys = sorted(groups, key=str)
    m = len(keys)
    rng = random.Random(seed)
    out: list[float] = []
    if m == 0:
        return out
    for _ in range(B):
        sample: list[Any] = []
        for _ in range(m):
            sample.extend(groups[keys[rng.randrange(m)]])
        value = stat(sample)
        if value is not None:
            out.append(value)
    return out


def percentile_interval(
    values: Sequence[float], confidence: float = CONFIDENCE
) -> list[float] | None:
    """Percentile interval with linear interpolation between order statistics."""
    if not values:
        return None
    ordered = sorted(values)
    alpha = 1 - confidence

    def quantile(q: float) -> float:
        pos = q * (len(ordered) - 1)
        lo = math.floor(pos)
        hi = math.ceil(pos)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)

    return [quantile(alpha / 2), quantile(1 - alpha / 2)]


def cohen_kappa(gold: Sequence[bool], pred: Sequence[bool]) -> float | None:
    """Cohen's kappa for two binary label sequences (None when chance agreement is 1)."""
    n = len(gold)
    if n == 0:
        return None
    observed = sum(g == p for g, p in zip(gold, pred, strict=True)) / n
    pg = sum(gold) / n
    pp = sum(pred) / n
    expected = pg * pp + (1 - pg) * (1 - pp)
    if expected >= 1:
        return None
    return (observed - expected) / (1 - expected)


def _binary_scores(gold: Sequence[bool], pred: Sequence[bool]) -> dict[str, Any]:
    labels_g = ["1" if g else "0" for g in gold]
    labels_p = ["1" if p else "0" for p in pred]
    scores = _class_metrics(labels_g, labels_p, ("1",))["1"]
    return {
        "precision": scores["precision"],
        "recall": scores["recall"],
        "f1": scores["f1"],
        "n_positive": scores["support"],
        "tp": scores["tp"],
        "fp": scores["fp"],
        "fn": scores["fn"],
    }


def tag_f1(
    gold_tags: Sequence[frozenset[str]],
    pred_tags: Sequence[frozenset[str]],
    tags: Sequence[str],
    *,
    min_positives: int = E4_MIN_POSITIVES,
) -> dict[str, dict[str, Any]]:
    """Per-tag binary F1 (gold has tag vs predicted has tag) with n_positive and flags."""
    out: dict[str, dict[str, Any]] = {}
    for tag in tags:
        gold = [tag in g for g in gold_tags]
        pred = [tag in p for p in pred_tags]
        entry = _binary_scores(gold, pred)
        entry["flags"] = _e4_flags(entry["n_positive"], entry["f1"], min_positives)
        out[tag] = entry
    return out


def study_type_metrics(
    gold: Sequence[str | None],
    pred: Sequence[str | None],
    *,
    values: Sequence[str] | None = None,
    min_positives: int = E4_MIN_POSITIVES,
    target_positives: int = E4_TARGET_POSITIVES,
) -> dict[str, dict[str, Any]]:
    """Per study_type value: one-vs-rest F1 and kappa, n_positive and flags (E4).

    The rows are gold-labelled works (study_type is labelled for plastic-relevant works only).
    """
    observed = sorted({g for g in gold if g}) if values is None else list(values)
    out: dict[str, dict[str, Any]] = {}
    for value in observed:
        g_bool = [x == value for x in gold]
        p_bool = [x == value for x in pred]
        entry = _binary_scores(g_bool, p_bool)
        entry["kappa"] = cohen_kappa(g_bool, p_bool)
        entry["flags"] = _e4_flags(
            entry["n_positive"],
            entry["f1"],
            min_positives,
            kappa=entry["kappa"],
            check_kappa=True,
        )
        if entry["n_positive"] < target_positives:
            entry["flags"].append("below_target_40")
        out[value] = entry
    return out


def _e4_flags(
    n_positive: int,
    f1: float | None,
    min_positives: int,
    kappa: float | None = None,
    check_kappa: bool = False,
) -> list[str]:
    """insufficient_data below ``min_positives``; experimental if F1 < 0.70 or kappa < 0.70.

    An undefined kappa (chance agreement of 1) is flagged experimental when ``check_kappa``.
    """
    if n_positive < min_positives:
        return ["insufficient_data"]
    flags: list[str] = []
    if f1 is None or f1 < E4_F1_MIN:
        flags.append("experimental_f1")
    if check_kappa and (kappa is None or kappa < E4_KAPPA_MIN):
        flags.append("experimental_kappa")
    return flags


def e3_current_model(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """E3 current-model plastic_related metrics from held-out rows only (unweighted).

    Raises ``ValueError`` when any row is not in the held-out split (training and dev rows are
    refused, so E3 can never be computed on data the model was fitted or tuned on).
    """
    offending = [r for r in rows if r.get("split") != HELD_OUT_SPLIT]
    if offending:
        raise ValueError(
            f"E3 accepts held-out '{HELD_OUT_SPLIT}' rows only; got {len(offending)} other rows"
        )
    usable = [r for r in rows if r.get("gold_pr") is not None and r.get("pred_pr") is not None]
    gold = [bool(r["gold_pr"]) for r in usable]
    pred = [bool(r["pred_pr"]) for r in usable]
    scores = _binary_scores(gold, pred)
    n_pred_pos = scores["tp"] + scores["fp"]
    n_gold_pos = scores["tp"] + scores["fn"]
    return {
        "n": len(usable),
        "precision": {
            "point": scores["precision"],
            "interval": list(wilson_interval(scores["tp"], n_pred_pos)) if n_pred_pos else None,
            "n": n_pred_pos,
        },
        "recall": {
            "point": scores["recall"],
            "interval": list(wilson_interval(scores["tp"], n_gold_pos)) if n_gold_pos else None,
            "n": n_gold_pos,
        },
        "f1": scores["f1"],
    }
