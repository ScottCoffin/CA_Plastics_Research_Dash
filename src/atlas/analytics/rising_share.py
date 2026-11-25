"""Rising-share flag (BQ-4.2).

Flags a reported topic tag whose share of CA plastic-related works is rising. The test is a
Cochran-Armitage trend test on (count, denominator) by complete year, with the normal approximation
(scipy is not a dependency). A tag is flagged only when every check below passes:

- trend: two-sided p < ``ALPHA`` with a positive trend statistic, over all complete years;
- volume: at least ``MIN_WINDOW_WORKS`` works with the tag in the last ``WINDOW_YEARS`` complete
  years;
- label-source sensitivity: the same trend test passes for every NON-EMPTY label-source variant
  (a variant with no works for the tag is ``not_testable`` and does not block);
- leave-one-institution-out: the trend test still passes after dropping, one at a time, the works
  of each institution that has a tagged work in the window (dropped from numerator and denominator).

Experimental tags are never flagged. Reads the frozen labels snapshot (BQ-4.1) and the authorship
links only; nothing here reads the network or writes under ``site/``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from atlas.analytics.topic_series import SENSITIVITY_VARIANTS, CaWork, reported_tags
from atlas.ingest.normalize import compact_id

SCHEMA = "bq4-rising-v1"
TEST_NAME = "cochran-armitage-normal-approximation"
ALPHA = 0.05
MIN_WINDOW_WORKS = 10
WINDOW_YEARS = 3
PASS = "pass"
FAIL = "fail"
NOT_TESTABLE = "not_testable"
REASON_VOLUME = "volume"
REASON_TREND = "trend"
REASON_SENSITIVITY = "sensitivity:{variant}"
REASON_LOIO = "leave_one_institution_out"
REASON_LOIO_NOT_TESTABLE = "leave_one_institution_out_not_testable"
EXPERIMENTAL = "experimental"


@dataclass(frozen=True)
class TrendResult:
    """Cochran-Armitage outcome: ``z > 0`` means the share is rising; ``p`` is two-sided."""

    z: float
    p: float

    @property
    def passes(self) -> bool:
        return self.p < ALPHA and self.z > 0


NO_TREND = TrendResult(z=0.0, p=1.0)


def cochran_armitage(
    counts: Sequence[int], denominators: Sequence[int], scores: Sequence[float]
) -> TrendResult:
    """Cochran-Armitage trend test for proportions ``counts[i] / denominators[i]`` at ``scores[i]``.

    ``T = sum t_i (r_i - n_i p)`` and ``Var = p (1 - p) (sum n_i t_i^2 - (sum n_i t_i)^2 / N)``,
    with ``p = R / N``. Two-sided p from the normal approximation ``erfc(|z| / sqrt 2)``. Returns
    ``NO_TREND`` when the test is undefined (no works, no variation in the share, or equal scores),
    so an undefined case never passes.
    """

    total_n = sum(denominators)
    total_r = sum(counts)
    if total_n == 0 or total_r == 0 or total_r == total_n:
        return NO_TREND
    pbar = total_r / total_n
    stat = sum(t * (r - n * pbar) for t, r, n in zip(scores, counts, denominators, strict=True))
    sum_nt = sum(n * t for t, n in zip(scores, denominators, strict=True))
    sum_nt2 = sum(n * t * t for t, n in zip(scores, denominators, strict=True))
    variance = pbar * (1.0 - pbar) * (sum_nt2 - sum_nt * sum_nt / total_n)
    if variance <= 0:
        return NO_TREND
    z = stat / math.sqrt(variance)
    return TrendResult(z=z, p=math.erfc(abs(z) / math.sqrt(2.0)))


def window_years(last_complete: int) -> list[int]:
    """The last ``WINDOW_YEARS`` complete calendar years (the volume window)."""

    return list(range(last_complete - WINDOW_YEARS + 1, last_complete + 1))


def complete_years(works: Sequence[CaWork], last_complete: int) -> list[int]:
    """Complete years from the first plastic-related year in the corpus to ``last_complete``."""

    years = [w.year for w in works if w.plastic_related and w.year is not None]
    if not years or min(years) > last_complete:
        return []
    return list(range(min(years), last_complete + 1))


def _denominators(works: Sequence[CaWork], years: Sequence[int]) -> list[int]:
    index = {year: i for i, year in enumerate(years)}
    out = [0] * len(years)
    for work in works:
        if work.plastic_related and work.year in index:
            out[index[work.year]] += 1  # type: ignore[index]
    return out


def _variant_counts(
    works: Sequence[CaWork], tag: str, years: Sequence[int]
) -> dict[str, list[int]]:
    """Per label-source variant: plastic-related works carrying ``tag`` in each complete year."""

    index = {year: i for i, year in enumerate(years)}
    out = {variant: [0] * len(years) for variant in SENSITIVITY_VARIANTS}
    for work in works:
        if not work.plastic_related or work.year not in index:
            continue
        source = work.topic_sources.get(tag)
        if source is None:
            continue
        i = index[work.year]  # type: ignore[index]
        out["all_sources"][i] += 1
        if source in {"owner", "model"}:
            out["owner_model_only"][i] += 1
        if source == "rule":
            out["rule_only"][i] += 1
    return out


def _trend(counts: Sequence[int], denominators: Sequence[int], years: Sequence[int]) -> TrendResult:
    if not years:
        return NO_TREND
    return cochran_armitage(counts, denominators, [float(y) for y in years])


def _slope_sign(result: TrendResult) -> str:
    if result.z > 0:
        return "positive"
    if result.z < 0:
        return "negative"
    return "zero"


def institutions_by_work(
    rows: Iterable[tuple[object, Iterable[object] | None]],
) -> dict[str, frozenset[str]]:
    """Map compact work IDs to the compact institution IDs of their authorships."""

    out: dict[str, set[str]] = {}
    for work_id, institution_ids in rows:
        work = compact_id(work_id)
        if not work:
            continue
        bucket = out.setdefault(work, set())
        for institution in institution_ids or []:
            text = compact_id(institution)
            if text:
                bucket.add(text)
    return {work: frozenset(values) for work, values in out.items()}


def _leave_one_institution_out(
    works: Sequence[CaWork],
    tag: str,
    years: Sequence[int],
    window: Sequence[int],
    institutions: Mapping[str, frozenset[str]],
) -> dict[str, Any]:
    """Drop each window-contributing institution's works in turn; report the worst-case p-value.

    The worst case is the largest p-value among the reruns, where a rerun with a non-positive trend
    counts as p = 1. ``pass`` requires every rerun to pass the trend test.
    """

    window_set = set(window)
    tagged_in_window = [
        w for w in works if w.plastic_related and w.year in window_set and tag in w.topic_sources
    ]
    names = sorted({i for w in tagged_in_window for i in institutions.get(w.work_id, ())})
    if not names:
        return {
            "worst_p": None,
            "worst_institution": None,
            "pass": False,
            "institutions_tested": 0,
            "reason": REASON_LOIO_NOT_TESTABLE,
        }
    worst_p = -1.0
    worst_name = None
    all_pass = True
    for name in names:
        kept = [w for w in works if name not in institutions.get(w.work_id, ())]
        counts = _variant_counts(kept, tag, years)["all_sources"]
        result = _trend(counts, _denominators(kept, years), years)
        all_pass = all_pass and result.passes
        effective = result.p if result.z > 0 else 1.0
        if effective > worst_p:
            worst_p, worst_name = effective, name
    return {
        "worst_p": round(worst_p, 6),
        "worst_institution": worst_name,
        "pass": all_pass,
        "institutions_tested": len(names),
        "reason": None,
    }


def evaluate_tag(
    works: Sequence[CaWork],
    tag: str,
    *,
    last_complete: int,
    institutions: Mapping[str, frozenset[str]],
) -> dict[str, Any]:
    """Run every check for one reported tag and return its per-tag record (without the label)."""

    years = complete_years(works, last_complete)
    window = window_years(last_complete)
    denominators = _denominators(works, years)
    variants = _variant_counts(works, tag, years)
    trend = _trend(variants["all_sources"], denominators, years)
    window_count = sum(
        count for year, count in zip(years, variants["all_sources"], strict=True) if year in window
    )

    reasons: list[str] = []
    if window_count < MIN_WINDOW_WORKS:
        reasons.append(REASON_VOLUME)
    if not trend.passes:
        reasons.append(REASON_TREND)

    sensitivity: dict[str, str] = {}
    for variant in SENSITIVITY_VARIANTS:
        counts = variants[variant]
        if sum(counts) == 0:
            sensitivity[variant] = NOT_TESTABLE
            continue
        passed = _trend(counts, denominators, years).passes
        sensitivity[variant] = PASS if passed else FAIL
        if not passed:
            reasons.append(REASON_SENSITIVITY.format(variant=variant))

    loio = _leave_one_institution_out(works, tag, years, window, institutions)
    if loio.pop("reason") is not None:
        reasons.append(REASON_LOIO_NOT_TESTABLE)
    elif not loio["pass"]:
        reasons.append(REASON_LOIO)

    return {
        "flag": not reasons,
        "reasons_failed": reasons,
        "trend": {"z": round(trend.z, 4), "p": round(trend.p, 6), "slope_sign": _slope_sign(trend)},
        "window_years": window,
        "window_count": window_count,
        "total_complete_years": sum(variants["all_sources"]),
        "sensitivity": sensitivity,
        "loio": loio,
    }


def evaluate_tags(
    works: Sequence[CaWork],
    taxonomy: Mapping[str, Any],
    *,
    last_complete: int,
    institutions: Mapping[str, frozenset[str]],
) -> dict[str, Any]:
    """Per-tag records for reported (non-experimental) tags; experimental tags are excluded."""

    reported, excluded = reported_tags(taxonomy)
    tags = [
        {
            "tag": spec["tag"],
            "label": spec["label"],
            **evaluate_tag(
                works, spec["tag"], last_complete=last_complete, institutions=institutions
            ),
        }
        for spec in reported
    ]
    return {
        "last_complete_year": last_complete,
        "window_years": window_years(last_complete),
        "alpha": ALPHA,
        "min_window_works": MIN_WINDOW_WORKS,
        "test": TEST_NAME,
        "tags": tags,
        "flagged": [t["tag"] for t in tags if t["flag"]],
        "tags_excluded": [{"tag": e["tag"], "reason": EXPERIMENTAL} for e in excluded],
    }


def rising_payload(
    *,
    works: Sequence[CaWork],
    taxonomy: Mapping[str, Any],
    institutions: Mapping[str, frozenset[str]],
    as_of: date,
    snapshot: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the bq4-rising-v1 payload from the frozen CA works."""

    body = evaluate_tags(works, taxonomy, last_complete=as_of.year - 1, institutions=institutions)
    return {
        "schema": SCHEMA,
        "as_of": as_of.isoformat(),
        "labels_snapshot": dict(snapshot),
        "inputs": dict(inputs),
        **body,
    }
