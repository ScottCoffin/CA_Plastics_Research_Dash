"""Trend metrics on the global-denominator series (BQ-2.3; A3 section 7 Module 2).

Reads the payload that ``atlas.analytics.denominators.build_series`` returns and adds a ``metrics``
block: per series, counts over the complete years of the analysis window, an index against a base
year, and a log-linear CAGR with a 95% interval; per allowed ratio, the share and its trend. No I/O
and no network calls.

- Complete years only. The as-of year and later are excluded (``last_complete_year``).
- Shares divide only the ratio pairs that the config allows (``ratio_pairs``). The numerator of each
  share is declared in ``SHARE_NUMERATORS``. Series D is beside-only and is never divided.
- Retractions. C and D counts exclude retracted-flagged records. A and B cannot exclude them (the
  OpenAlex group_by has no retraction split), so their counts include them. A share keeps the unit
  of the denominator on both sides (retracted-flagged records included), so C/A stays like for like.
- The 95% interval reflects year-to-year scatter around a log-linear trend, not sampling error.

The Student t quantile is computed here from the regularized incomplete beta function, because
scipy is not a dependency of this project.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from atlas.analytics.denominators import DEFAULT_CONFIG

METRICS_SCHEMA = "denominator_metrics.v1"
DEFAULT_WINDOW_START = 2006
CI_LEVEL = 0.95
# Numerator of each share the config allows: numerator -> denominator. The pair must also be listed
# in the payload's ratio_pairs (the config's ratio guard). Series D is absent on purpose.
SHARE_NUMERATORS: dict[str, str] = {
    "B": "A",
    "C": "A",
    "B-article_review": "A-article_review",
}
METHOD: dict[str, str] = {
    "unit": (
        "Series A, B and C: OpenAlex records by publication year (duplicates not collapsed). "
        "Series D: curated works, one row per work. A ratio is taken only between the pairs "
        "listed in ratio_pairs, which share a counting unit and a type sensitivity. "
        "D is shown beside them and is never divided."
    ),
    "window": (
        "Complete years only, from window.start to window.end (last_complete_year). The as-of "
        "year and later are excluded and listed in partial_years_excluded. window.start is the "
        "requested start, or the first year in the series when that is later."
    ),
    "retractions": (
        "C and D: counts exclude retracted-flagged records (count = records minus retracted). "
        "A and B: the OpenAlex group_by cannot split retractions, so counts include them. "
        "Shares use both sides with retracted-flagged records included (the unit of A), so C/A "
        "stays like for like. No share uses a retraction-excluded count."
    ),
    "zero_counts": (
        "A zero count is skipped in the log-linear fit (ln 0 is undefined) and listed in "
        "zero_years_skipped. n_years counts the years used. A zero share (zero numerator) is "
        "skipped the same way, and a year with a zero denominator has no share."
    ),
    "index": "index = value / value in window.base_year (value is a count or a share).",
    "cagr": (
        "Ordinary least squares of ln(value) on calendar year over the used years, slope b. "
        "CAGR = exp(b) - 1. A CAGR needs at least 2 used years; the 95% interval needs at least "
        "3. Interval = exp(b -/+ t * SE(b)) - 1, with SE(b) from the residual scatter and t the "
        "two-sided 95% Student t quantile at df = n - 2."
    ),
    "shares": (
        "The share trend is the same fit on ln(share), so it is the growth of the numerator "
        "relative to the denominator."
    ),
    "uncertainty": (
        "The CI reflects year-to-year scatter around a log-linear trend, not sampling error."
    ),
}
_ROUND = 10


def _r(value: float | None) -> float | None:
    """Round for stable output text across platforms; None stays None."""

    return None if value is None else round(float(value), _ROUND)


# --- Student t quantile without scipy ------------------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz method)."""

    eps, fpmin, max_iter = 3e-16, 1e-300, 500
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > fpmin else fpmin)
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > fpmin else fpmin)
        c = 1.0 + aa / c
        c = c if abs(c) > fpmin else fpmin
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > fpmin else fpmin)
        c = 1.0 + aa / c
        c = c if abs(c) > fpmin else fpmin
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b) for 0 <= x <= 1."""

    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _t_upper_tail(t: float, df: float) -> float:
    """P(T > t) for Student's t with ``df`` degrees of freedom, t >= 0."""

    return 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))


def t_quantile(p: float, df: float) -> float:
    """Inverse CDF of Student's t: the value t with P(T <= t) = p.

    Computed by bisection on the tail probability, which uses the regularized incomplete beta
    function. Accurate to about 1e-10 for df >= 1.
    """

    if not 0.0 < p < 1.0:
        raise ValueError(f"p must be strictly between 0 and 1, not {p}")
    if not df > 0:
        raise ValueError(f"df must be positive, not {df}")
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -t_quantile(1.0 - p, df)
    target = 1.0 - p
    lo, hi = 0.0, 1.0
    while _t_upper_tail(hi, df) > target:
        lo, hi = hi, hi * 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _t_upper_tail(mid, df) > target:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * max(1.0, hi):
            break
    return (lo + hi) / 2.0


# --- log-linear trend ---------------------------------------------------------------------------


def log_linear_trend(points: Sequence[tuple[int, float]]) -> dict[str, Any]:
    """OLS of ln(value) on year over the points with a positive value.

    ``points`` are (year, value) pairs with value >= 0. Zero values are skipped and listed in
    ``zero_years_skipped``. The slope, CAGR and the 95% interval are None when there are too few
    years (see METHOD["cagr"]).
    """

    used: list[tuple[float, float]] = []
    zeros: list[int] = []
    for year, value in points:
        if value < 0:
            raise ValueError(f"value for {year} must be non-negative, not {value}")
        if value == 0:
            zeros.append(int(year))
        else:
            used.append((float(year), math.log(value)))
    n = len(used)
    result: dict[str, Any] = {
        "n_years": n,
        "zero_years_skipped": zeros,
        "slope": None,
        "slope_se": None,
        "df": None,
        "t_crit": None,
        "cagr": None,
        "ci95": None,
        "note": None,
    }
    if n < 2:
        result["note"] = "fewer than 2 non-zero years; no trend"
        return result
    mean_x = sum(x for x, _ in used) / n
    mean_y = sum(y for _, y in used) / n
    sxx = sum((x - mean_x) ** 2 for x, _ in used)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in used)
    slope = sxy / sxx
    result["slope"] = _r(slope)
    result["cagr"] = _r(math.expm1(slope))
    if n < 3:
        result["note"] = "two non-zero years: slope and CAGR only, no interval"
        return result
    sse = sum((y - (mean_y + slope * (x - mean_x))) ** 2 for x, y in used)
    df = n - 2
    se = math.sqrt(sse / df / sxx)
    t_crit = t_quantile((1.0 + CI_LEVEL) / 2.0, df)
    result.update(
        {
            "slope_se": _r(se),
            "df": df,
            "t_crit": _r(t_crit),
            "ci95": [
                _r(math.expm1(slope - t_crit * se)),
                _r(math.expm1(slope + t_crit * se)),
            ],
        }
    )
    return result


# --- options and the metrics block --------------------------------------------------------------


def load_metrics_options(path: str | Path = DEFAULT_CONFIG) -> dict[str, int | None]:
    """Optional ``metrics`` block of the series config: ``window_start`` and ``base_year``.

    Returns keyword arguments for ``build_metrics``. An absent block gives the defaults (window
    from 2006, base year = the first year of the window).
    """

    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    block = payload.get("metrics") if isinstance(payload, Mapping) else None
    if block is None:
        return {"window_start": DEFAULT_WINDOW_START, "base_year": None}
    if not isinstance(block, Mapping) or set(block) - {"window_start", "base_year"}:
        raise ValueError(f"{path}: metrics must be a mapping with window_start and base_year only")
    window_start = block.get("window_start")
    if window_start is None:
        window_start = DEFAULT_WINDOW_START
    base_year = block.get("base_year")
    for key, value in (("window_start", window_start), ("base_year", base_year)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValueError(f"{path}: metrics.{key} must be a year")
    return {"window_start": window_start, "base_year": base_year}


def _index(value: int | float, base_value: int | float | None) -> float | None:
    if base_value is None or base_value == 0:
        return None
    return _r(value / base_value)


def _series_counts(
    series_id: str, entry: Mapping[str, Any], years: Sequence[int]
) -> tuple[dict[int, int], dict[int, int] | None]:
    """Records in each year: (including retracted, excluding retracted or None when unknown)."""

    rows = {row["year"]: row for row in entry["years"]}
    missing = [year for year in years if year not in rows]
    if missing:
        raise ValueError(f"{series_id}: no row for window year {missing[0]}")
    including = {year: int(rows[year]["count"]) for year in years}
    if any(rows[year]["retracted"] is None for year in years):
        return including, None
    excluding: dict[int, int] = {}
    for year in years:
        retracted = int(rows[year]["retracted"])
        if not 0 <= retracted <= including[year]:
            raise ValueError(f"{series_id}: retracted count for {year} is out of range")
        excluding[year] = including[year] - retracted
    return including, excluding


def _series_block(
    series_id: str, entry: Mapping[str, Any], years: Sequence[int], base_year: int
) -> dict[str, Any]:
    including, excluding = _series_counts(series_id, entry, years)
    counted = excluding if excluding is not None else including
    rows = {row["year"]: row for row in entry["years"]}
    basis = (
        "retracted-flagged records excluded (count = records minus retracted)"
        if excluding is not None
        else (
            "retracted-flagged records included; cannot be excluded (OpenAlex group_by has no "
            "retraction split)"
        )
    )
    return {
        "basis": basis,
        "beside_only": bool(entry.get("beside_only")),
        "years": [
            {
                "year": year,
                "count": counted[year],
                "retracted": rows[year]["retracted"],
                "index": _index(counted[year], counted[base_year]),
            }
            for year in years
        ],
        "trend": log_linear_trend([(year, counted[year]) for year in years]),
    }


def _share_pairs(
    ratio_pairs: Sequence[Sequence[str]], series: Mapping[str, Any]
) -> list[tuple[str, str]]:
    """(numerator, denominator) for each allowed pair. Raises for an undeclared pair."""

    pairs: list[tuple[str, str]] = []
    for first, second in ratio_pairs:
        if SHARE_NUMERATORS.get(first) == second:
            numerator, denominator = first, second
        elif SHARE_NUMERATORS.get(second) == first:
            numerator, denominator = second, first
        else:
            raise ValueError(
                f"allowed ratio {first}/{second} has no declared numerator in SHARE_NUMERATORS"
            )
        if series[numerator].get("beside_only") or series[denominator].get("beside_only"):
            raise ValueError(f"{numerator}/{denominator}: a beside-only series is never divided")
        pairs.append((numerator, denominator))
    return pairs


def _share_block(
    numerator: str,
    denominator: str,
    series: Mapping[str, Any],
    years: Sequence[int],
    base_year: int,
) -> dict[str, Any]:
    num_incl, _ = _series_counts(numerator, series[numerator], years)
    den_incl, _ = _series_counts(denominator, series[denominator], years)
    shares: dict[int, float | None] = {}
    for year in years:
        denominator_count = den_incl[year]
        shares[year] = None if denominator_count == 0 else num_incl[year] / denominator_count
    points = [(year, share) for year, share in shares.items() if share is not None]
    base_share = shares[base_year]
    rows = []
    for year in years:
        share = shares[year]
        index = _r(share / base_share) if share is not None and base_share else None
        rows.append({"year": year, "share": _r(share), "index": index})
    return {
        "numerator": numerator,
        "denominator": denominator,
        "basis": (
            "both sides include retracted-flagged records, the counting unit of the denominator; "
            "the pair stays like for like"
        ),
        "years": rows,
        "trend": log_linear_trend(points),
    }


def build_metrics(
    payload: Mapping[str, Any],
    *,
    window_start: int = DEFAULT_WINDOW_START,
    base_year: int | None = None,
) -> dict[str, Any]:
    """The ``metrics`` block for a built denominator payload. No I/O.

    The window runs from ``window_start`` (or the first year in the series, if later) to
    ``last_complete_year``. ``base_year`` defaults to the first year of the window. Raises
    ValueError when the window has no complete year, when the base year is outside the window,
    or for a ratio pair with no declared numerator.
    """

    series: Mapping[str, Any] = payload["series"]
    end = int(payload["last_complete_year"])
    all_years = sorted({int(row["year"]) for entry in series.values() for row in entry["years"]})
    if not all_years:
        raise ValueError("no series years to measure")
    start = max(int(window_start), all_years[0])
    if start > end:
        raise ValueError(f"no complete years in the window {window_start} to {end}")
    years = list(range(start, end + 1))
    base = start if base_year is None else int(base_year)
    if not start <= base <= end:
        raise ValueError(f"base_year {base} is outside the window {start} to {end}")
    ratio_pairs = [list(pair) for pair in payload.get("ratio_pairs", [])]
    return {
        "schema_version": METRICS_SCHEMA,
        "as_of": payload.get("as_of"),
        "window": {
            "requested_start": int(window_start),
            "start": start,
            "end": end,
            "base_year": base,
            "years": len(years),
        },
        "partial_years_excluded": [year for year in all_years if year > end],
        "ci_level": CI_LEVEL,
        "method": dict(METHOD),
        "series": {
            series_id: _series_block(series_id, entry, years, base)
            for series_id, entry in series.items()
        },
        "shares": {
            f"{numerator}/{denominator}": _share_block(numerator, denominator, series, years, base)
            for numerator, denominator in _share_pairs(ratio_pairs, series)
        },
    }
