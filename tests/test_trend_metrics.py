"""Trend metrics on the denominator series (BQ-2.3): t quantile, CAGR, shares, windows."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlas.analytics.denominators import (
    build_series,
    cache_key,
    fetch_series_filters,
    filter_digest,
    load_series_config,
)
from atlas.analytics.trend_metrics import (
    METHOD,
    build_metrics,
    load_metrics_options,
    log_linear_trend,
    t_quantile,
)
from atlas.query import load_query_config

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_denominator_series.py"
CONFIG = ROOT / "config" / "denominator_series.yml"
QUERIES = ROOT / "config" / "queries.yml"
AS_OF = date(2026, 11, 22)
CORPUS_ROUTE = "openalex-works-20261110T010203Z"


def _years(start: int, end: int) -> range:
    return range(start, end + 1)


# --- t quantile ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("df", "expected"),
    [
        (5, 2.570582),  # standard two-sided 95% table value
        (10, 2.228139),
        (18, 2.100922),
    ],
)
def test_t_quantile_matches_the_table_values(df, expected):
    assert t_quantile(0.975, df) == pytest.approx(expected, abs=1e-3)


def test_t_quantile_matches_closed_forms_for_one_and_two_degrees_of_freedom():
    # df = 1 is the Cauchy distribution: t = tan(pi (p - 1/2)).
    assert t_quantile(0.975, 1) == pytest.approx(math.tan(0.475 * math.pi), abs=1e-9)
    # df = 2: P(T <= t) = 1/2 + t / (2 sqrt(2 + t^2)), so with u = 2p - 1,
    # t = sqrt(2) u / sqrt(1 - u^2).
    assert t_quantile(0.975, 2) == pytest.approx(4.302653, abs=1e-6)


def test_t_quantile_is_symmetric_and_rejects_bad_arguments():
    assert t_quantile(0.025, 5) == pytest.approx(-t_quantile(0.975, 5), abs=1e-12)
    assert t_quantile(0.5, 7) == 0.0
    with pytest.raises(ValueError):
        t_quantile(1.0, 5)
    with pytest.raises(ValueError):
        t_quantile(0.975, 0)


# --- log-linear trend ------------------------------------------------------------------------


def test_exact_exponential_growth_gives_the_growth_rate_with_zero_width_interval():
    points = [(2006 + k, 1000 * 1.1**k) for k in range(20)]
    trend = log_linear_trend(points)

    assert trend["n_years"] == 20
    assert trend["cagr"] == pytest.approx(0.10, abs=1e-9)
    assert trend["slope"] == pytest.approx(math.log(1.1), abs=1e-9)
    low, high = trend["ci95"]
    assert high - low == pytest.approx(0.0, abs=1e-9)
    assert low == pytest.approx(0.10, abs=1e-9)


def test_interval_matches_a_hand_computed_example():
    # Years 2000-2003, counts 10, 20, 20, 40. With x = year - 2001.5, Sxx = 5 and ln(count) =
    # ln 10 + k ln 2 where k = 0, 1, 1, 2. Then slope = 0.6 ln 2 = 0.4158883 and the residuals in
    # units of ln 2 are -0.1, +0.3, -0.3, +0.1, so SSE = 0.2 (ln 2)^2 and
    # SE(slope) = ln 2 * sqrt(0.2 / 2 / 5) = ln 2 * sqrt(0.02) = 0.0980258.
    # df = 2, so t(0.975) = 4.302653, the half-width is 0.421771 on the ln scale, and
    # CAGR = 2^0.6 - 1 = 0.5157166 with interval [exp(-0.0058827) - 1, exp(0.8376593) - 1].
    trend = log_linear_trend([(2000, 10), (2001, 20), (2002, 20), (2003, 40)])

    assert trend["n_years"] == 4
    assert trend["df"] == 2
    assert trend["slope"] == pytest.approx(0.4158883, abs=1e-6)
    assert trend["slope_se"] == pytest.approx(0.0980258, abs=1e-6)
    assert trend["t_crit"] == pytest.approx(4.302653, abs=1e-6)
    assert trend["cagr"] == pytest.approx(0.5157166, abs=1e-6)
    low, high = trend["ci95"]
    assert low == pytest.approx(-0.0058654, abs=2e-6)
    assert high == pytest.approx(1.3109515, abs=2e-6)


def test_zero_count_years_are_skipped_and_listed():
    # ln(count) on the non-zero years is ln 10, ln 40, ln 80 at 2000, 2002, 2003: slope = ln 2,
    # so the CAGR is exactly 1.0 (doubling each year).
    trend = log_linear_trend([(2000, 10), (2001, 0), (2002, 40), (2003, 80)])

    assert trend["n_years"] == 3
    assert trend["zero_years_skipped"] == [2001]
    assert trend["slope"] == pytest.approx(math.log(2), abs=1e-9)
    assert trend["cagr"] == pytest.approx(1.0, abs=1e-9)
    assert trend["df"] == 1
    assert trend["t_crit"] == pytest.approx(12.706205, abs=1e-5)


def test_two_years_give_a_cagr_but_no_interval():
    trend = log_linear_trend([(2000, 100), (2002, 121)])

    assert trend["n_years"] == 2
    assert trend["cagr"] == pytest.approx(0.10, abs=1e-9)
    assert trend["ci95"] is None
    assert trend["slope_se"] is None
    assert "no interval" in trend["note"]


def test_fewer_than_two_non_zero_years_give_no_trend_and_negatives_raise():
    empty = log_linear_trend([(2000, 0), (2001, 5)])
    assert empty["cagr"] is None and empty["n_years"] == 1
    assert empty["zero_years_skipped"] == [2000]
    with pytest.raises(ValueError):
        log_linear_trend([(2000, 5), (2001, -1)])


# --- the metrics block on built payloads -----------------------------------------------------


def _entry(by_year: dict[int, int]) -> dict[str, Any]:
    return {
        "query_version": "plastic-v3.1",
        "filter_digest": "test",
        "fetched_at": "2026-11-22T10:00:00+00:00",
        "by_year": {str(year): count for year, count in by_year.items()},
        "stale": False,
        "stale_reason": None,
    }


def _c_records(by_year: dict[int, int], retracted: dict[int, int] | None = None) -> list[dict]:
    """Corpus records for series C: California records on the query route, some retracted."""

    retracted = retracted or {}
    records: list[dict] = []
    for year, count in by_year.items():
        for index in range(count):
            records.append(
                {
                    "route": CORPUS_ROUTE,
                    "year": year,
                    "ca_any_author": True,
                    "is_retracted": index < retracted.get(year, 0),
                }
            )
    return records


def _d_works(by_year: dict[int, int], retracted: dict[int, int] | None = None) -> list[dict]:
    retracted = retracted or {}
    works: list[dict] = []
    for year, count in by_year.items():
        for index in range(count):
            works.append(
                {
                    "year": year,
                    "plastic_related": True,
                    "is_retracted": index < retracted.get(year, 0),
                }
            )
    return works


def _payload(
    *,
    a: dict[int, int],
    b: dict[int, int] | None = None,
    c: dict[int, int] | None = None,
    c_retracted: dict[int, int] | None = None,
    d: dict[int, int] | None = None,
    d_retracted: dict[int, int] | None = None,
    as_of: date = AS_OF,
) -> dict[str, Any]:
    """A built denominator payload from synthetic inputs and the committed config."""

    b = b if b is not None else {year: count // 2 for year, count in a.items()}
    entries = {
        "A": _entry(a),
        "A-article_review": _entry(a),
        "B": _entry(b),
        "B-article_review": _entry(b),
    }
    return build_series(
        load_series_config(CONFIG),
        corpus_records=_c_records(c or {}, c_retracted),
        published_works=_d_works(d or {}, d_retracted),
        denominator_entries=entries,
        as_of=as_of,
    )


def _a_counts(start: int = 2006, end: int = 2026) -> dict[int, int]:
    """A rows 2006-2026 (2026 is the partial year of AS_OF) with ten-per-cent growth."""

    return {year: round(1000 * 1.1 ** (year - start)) for year in _years(start, end)}


def test_metrics_use_complete_years_only():
    base = _a_counts()
    spiked = {**base, 2026: 10**9}
    first = build_metrics(_payload(a=base, c={2025: 2}))
    second = build_metrics(_payload(a=spiked, c={2025: 2}))

    assert first["window"]["end"] == 2025
    assert second["partial_years_excluded"] == [2026]
    assert second["series"]["A"] == first["series"]["A"]
    assert second["series"]["A"]["trend"]["n_years"] == 20
    assert all(row["year"] <= 2025 for row in second["series"]["A"]["years"])


def test_retractions_are_excluded_for_c_and_d_and_included_for_a_and_b():
    payload = _payload(
        a=_a_counts(),
        c={2024: 2, 2025: 3},
        c_retracted={2025: 1},
        d={2024: 4, 2025: 2},
        d_retracted={2025: 1},
    )
    metrics = build_metrics(payload)
    c_2025 = metrics["series"]["C"]["years"][-1]
    d_2025 = metrics["series"]["D"]["years"][-1]
    a_2025 = metrics["series"]["A"]["years"][-1]

    assert c_2025["year"] == 2025
    assert c_2025["count"] == 2 and c_2025["retracted"] == 1
    assert d_2025["count"] == 1 and d_2025["retracted"] == 1
    assert "excluded" in metrics["series"]["C"]["basis"]
    assert "excluded" in metrics["series"]["D"]["basis"]
    assert "cannot be excluded" in metrics["series"]["A"]["basis"]
    assert a_2025["count"] == _a_counts()[2025]
    assert a_2025["retracted"] is None
    # The share keeps the declared unit on both sides: C/A divides C including retracted records.
    c_over_a = metrics["shares"]["C/A"]["years"][-1]
    assert c_over_a["share"] == pytest.approx(3 / _a_counts()[2025], abs=1e-10)


def test_d_is_never_divided_and_only_allowed_pairs_get_shares():
    metrics = build_metrics(_payload(a=_a_counts(), c={2025: 2}, d={2025: 5}))

    assert set(metrics["shares"]) == {"B/A", "C/A", "B-article_review/A-article_review"}
    for share in metrics["shares"].values():
        assert "D" not in (share["numerator"], share["denominator"])
    assert metrics["series"]["D"]["beside_only"] is True
    assert metrics["series"]["D"]["trend"]["n_years"] == 1  # counted, but never in a ratio


def test_an_undeclared_ratio_pair_raises():
    payload = _payload(a=_a_counts(), c={2025: 2})
    tampered = copy.deepcopy(payload)
    tampered["ratio_pairs"] = [["A", "D"]]

    with pytest.raises(ValueError, match="no declared numerator"):
        build_metrics(tampered)


def test_share_trend_is_the_growth_of_the_numerator_relative_to_the_denominator():
    # A = 1000 * 3^k and C = 10 * 2^k over 2006-2013, so C/A = 0.01 * (2/3)^k.
    # CAGR(A) = 3 - 1 = 2, CAGR(C) = 2 - 1 = 1, and CAGR(C/A) = 2/3 - 1 = -1/3.
    years = _years(2006, 2014)
    a = {year: 1000 * 3 ** (year - 2006) for year in years}
    c = {year: 10 * 2 ** (year - 2006) for year in _years(2006, 2013)}
    metrics = build_metrics(_payload(a=a, c=c, as_of=date(2014, 6, 1)))

    assert metrics["window"]["end"] == 2013
    assert metrics["series"]["A"]["trend"]["cagr"] == pytest.approx(2.0, abs=1e-9)
    assert metrics["series"]["C"]["trend"]["cagr"] == pytest.approx(1.0, abs=1e-9)
    share = metrics["shares"]["C/A"]
    assert share["trend"]["cagr"] == pytest.approx(-1 / 3, abs=1e-9)
    assert share["years"][0]["share"] == pytest.approx(0.01, abs=1e-12)
    assert share["years"][0]["index"] == pytest.approx(1.0, abs=1e-12)


def test_zero_count_years_are_skipped_in_the_series_trend():
    # Exact doubling, so the fit on the 19 non-zero years is exact and the CAGR is 1.0.
    counts = {year: 1000 * 2 ** (year - 2006) for year in _years(2006, 2026)}
    counts[2010] = 0
    metrics = build_metrics(_payload(a=counts))

    trend = metrics["series"]["A"]["trend"]
    assert trend["zero_years_skipped"] == [2010]
    assert trend["n_years"] == 19
    assert trend["cagr"] == pytest.approx(1.0, abs=1e-9)
    index_2010 = [row["index"] for row in metrics["series"]["A"]["years"] if row["year"] == 2010]
    assert index_2010 == [0.0]


def test_index_is_relative_to_the_base_year_and_none_for_a_zero_base():
    counts = _a_counts()
    base_metrics = build_metrics(_payload(a=counts), base_year=2010)
    rows = {row["year"]: row for row in base_metrics["series"]["A"]["years"]}
    assert rows[2010]["index"] == pytest.approx(1.0, abs=1e-12)
    assert rows[2006]["index"] == pytest.approx(counts[2006] / counts[2010], abs=1e-9)

    counts[2010] = 0
    zero_base = build_metrics(_payload(a=counts), base_year=2010)
    assert {row["index"] for row in zero_base["series"]["A"]["years"]} == {None}


def test_window_start_is_capped_at_the_first_year_and_the_base_must_be_inside():
    payload = _payload(a=_a_counts())

    metrics = build_metrics(payload, window_start=1900)
    assert metrics["window"]["requested_start"] == 1900
    assert metrics["window"]["start"] == 2006
    assert metrics["window"]["base_year"] == 2006

    with pytest.raises(ValueError, match="outside the window"):
        build_metrics(payload, window_start=2010, base_year=2005)
    with pytest.raises(ValueError, match="no complete years"):
        build_metrics(payload, window_start=2026)


def test_metrics_options_default_and_read_the_config_block(tmp_path):
    assert load_metrics_options(CONFIG) == {"window_start": 2006, "base_year": None}

    config = tmp_path / "denominator_series.yml"
    config.write_text("metrics:\n  window_start: 2010\n  base_year: 2012\n", encoding="utf-8")
    assert load_metrics_options(config) == {"window_start": 2010, "base_year": 2012}

    config.write_text("metrics:\n  window_start: null\n", encoding="utf-8")
    assert load_metrics_options(config) == {"window_start": 2006, "base_year": None}

    config.write_text("metrics:\n  window_start: 2010.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a year"):
        load_metrics_options(config)
    config.write_text("metrics:\n  window: 2010\n", encoding="utf-8")
    with pytest.raises(ValueError, match="window_start and base_year only"):
        load_metrics_options(config)


def test_method_text_states_the_unit_window_exclusions_and_the_ci_caveat():
    metrics = build_metrics(_payload(a=_a_counts()))

    assert metrics["method"] == METHOD
    assert "Complete years only" in METHOD["window"]
    assert "retract" in METHOD["retractions"]
    assert (
        "CI reflects year-to-year scatter around a log-linear trend, not sampling error"
        in (METHOD["uncertainty"])
    )
    assert metrics["ci_level"] == 0.95


# --- the builder writes the block and --check sees it ----------------------------------------


def _load_script():
    spec = importlib.util.spec_from_file_location("build_denominator_series", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cache_file(path: Path, by_series: dict[str, dict[int, int]]) -> Path:
    config = load_query_config(QUERIES)
    entries = {}
    for series_id, by_year in by_series.items():
        filters = fetch_series_filters(config, series_id)
        digest = filter_digest(filters)
        entry = {
            "series_id": series_id,
            "query_version": config["version"],
            "filter_digest": digest,
            "filter": ",".join(filters),
            "fetched_at": "2026-11-22T10:00:00+00:00",
            "source": "OpenAlex group_by publication_year",
            "by_year": {str(year): count for year, count in by_year.items()},
            "stale": False,
            "stale_reason": None,
        }
        entries[cache_key(series_id, config["version"], digest)] = entry
    payload = {
        "schema_version": "denominator_series_cache.v1",
        "source": "OpenAlex group_by publication_year",
        "entries": entries,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_builder_writes_the_metrics_block_and_check_detects_a_change(tmp_path, monkeypatch):
    script = _load_script()
    counts = {year: round(1000 * 1.1 ** (year - 2006)) for year in _years(2006, 2026)}
    cache = _cache_file(
        tmp_path / "denominator_series_cache.json",
        {
            "A-all": counts,
            "A-article_review": counts,
            "B-all": {year: count // 2 for year, count in counts.items()},
            "B-article_review": {year: count // 2 for year, count in counts.items()},
        },
    )
    index = tmp_path / "index.json"
    works = tmp_path / "works.parquet"
    raw = tmp_path / "works_raw.parquet"
    index.write_text(json.dumps({"works": []}), encoding="utf-8")
    works.write_bytes(b"")
    raw.write_bytes(b"")
    monkeypatch.setattr(script, "CACHE", cache)
    monkeypatch.setattr(script, "INDEX", index)
    monkeypatch.setattr(script, "WORKS", works)
    monkeypatch.setattr(script, "RAW", raw)
    monkeypatch.setattr(script, "load_corpus_records", lambda *_: [])
    monkeypatch.setattr(script, "load_published_works", lambda *_: [])
    out = tmp_path / "out" / "denominator_series.json"
    args = ["--as-of", "2026-11-22", "--output", str(out)]

    assert script.main(args) == 0
    metrics = json.loads(out.read_text(encoding="utf-8"))["metrics"]
    assert metrics["window"] == {
        "requested_start": 2006,
        "start": 2006,
        "end": 2025,
        "base_year": 2006,
        "years": 20,
    }
    assert metrics["partial_years_excluded"] == [2026]
    # Counts are rounded to whole records, so the fit is close to, not exactly, 10 per cent.
    assert metrics["series"]["A"]["trend"]["cagr"] == pytest.approx(0.10, abs=2e-3)
    assert set(metrics["shares"]) == {"B/A", "C/A", "B-article_review/A-article_review"}
    assert script.main(["--check", *args]) == 0

    out.write_text(
        out.read_text(encoding="utf-8").replace('"count": 1000,', '"count": 1001,', 1),
        encoding="utf-8",
    )
    assert script.main(["--check", *args]) == 1


def test_committed_config_has_no_metrics_block_and_still_loads():
    payload = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert "metrics" not in payload
    assert load_series_config(CONFIG)["D"].beside_only is True
