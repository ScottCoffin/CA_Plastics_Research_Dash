"""Expert career metrics: m-quotient, rising score, histograms, affiliations."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from atlas.build import expert_metrics as em

ROOT = Path(__file__).resolve().parents[1]


def _fetch_module():
    spec = importlib.util.spec_from_file_location(
        "fetch_author_metrics", ROOT / "scripts" / "fetch_author_metrics.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_robust_first_year_skips_isolated_early_work() -> None:
    fetch = _fetch_module()
    assert fetch.robust_first_year({1973: 1, 1982: 1, 1993: 1, 1995: 2, 1996: 18}) == 1993
    assert fetch.robust_first_year({2020: 1}) == 2020
    assert fetch.robust_first_year({}) is None


def test_works_by_year_and_plastic_tally() -> None:
    fetch = _fetch_module()
    body = {"group_by": [{"key": "2020", "count": 3}, {"key": "unknown", "count": 1}]}
    assert fetch.works_by_year(body) == {2020: 3}
    works = [
        {
            "authorships": [{"author": {"id": "https://openalex.org/A1"}}],
            "counts_by_year": [{"year": 2024, "cited_by_count": 5}],
        },
        {
            "authorships": [{"author": {"id": "A1"}}, {"author": {"id": "A2"}}],
            "counts_by_year": [
                {"year": 2024, "cited_by_count": 2},
                {"year": 2025, "cited_by_count": 1},
            ],
        },
    ]
    assert fetch.tally_plastic_by_year(works, {"A1", "A2"}) == {
        "A1": {2024: 7, 2025: 1},
        "A2": {2024: 2, 2025: 1},
    }


def _row(**kwargs: object) -> dict:
    return {
        key: json.dumps(value) if isinstance(value, list) else value
        for key, value in kwargs.items()
    }


def test_merge_sums_years_and_unions_affiliations() -> None:
    merged = em.merge_metric_rows(
        [
            _row(
                counts_by_year_json=[{"year": 2024, "cited_by_count": 3}],
                plastic_counts_by_year_json=[{"year": 2024, "cited_by_count": 1}],
                first_pub_year=2010,
                last_known_institutions_json=[
                    {"id": "I1", "name": "UC Davis", "country_code": "US"}
                ],
                affiliations_json=[{"id": "I1", "name": "UC Davis", "years": [2020]}],
            ),
            _row(
                counts_by_year_json=[{"year": 2024, "cited_by_count": 4}],
                first_pub_year=2008,
                affiliations_json=[{"id": "I1", "name": "UC Davis", "years": [2018]}],
            ),
        ]
    )
    assert merged["cites_by_year"] == {2024: 7}
    assert merged["plastic_by_year"] == {2024: 1}
    assert merged["first_pub_year"] == 2008
    assert merged["affiliations"][0]["years"] == [2018, 2020]


def test_citations_by_year_window_and_unknown_plastics() -> None:
    merged = {"cites_by_year": {2015: 9, 2025: 4}, "plastic_by_year": None, "first_pub_year": 2000}
    rows = em.citations_by_year(merged, 2026)
    assert [r["year"] for r in rows] == list(range(2017, 2027))
    assert rows[-2] == {"year": 2025, "all": 4, "plastic": None}
    young = em.citations_by_year(
        {"cites_by_year": {2025: 1}, "plastic_by_year": {}, "first_pub_year": 2024}, 2026
    )
    assert [r["year"] for r in young] == [2024, 2025, 2026]
    assert young[0]["plastic"] == 0
    assert em.citations_by_year({"cites_by_year": {}, "plastic_by_year": None}, 2026) == []


def test_m_quotient() -> None:
    assert em.m_quotient(20, 2006, 2026) == 1.0
    assert em.m_quotient(3, 2026, 2026) == 3.0
    assert em.m_quotient(None, 2006, 2026) is None
    assert em.m_quotient(5, None, 2026) is None


def test_rising_scores_use_field_share_slope() -> None:
    years = range(2021, 2026)
    plastic = {
        "riser": {y: 2 * (y - 2020) * 10 for y in years},  # 20, 40, ... 100
        "flat": {y: 100 for y in years},
        "tiny": {2025: 5},  # below the minimum, unscored
        "unknown": None,
    }
    scores = em.rising_scores(plastic, 2026)
    assert set(scores) == {"riser", "flat"}
    assert scores["riser"][0] > 0 > scores["flat"][0]
    assert scores["riser"][1] == 100 and scores["flat"][1] == 0


def test_primary_affiliations_prefers_openalex_then_recent() -> None:
    merged = {"last_known": [{"id": "I1", "name": "UC Davis", "country_code": "US"}]}
    assert em.primary_affiliations(merged, ["I9"], {})[0]["source"] == "openalex_last_known"
    fallback = em.primary_affiliations({"last_known": []}, ["I2", "I3", "I2"], {"I2": "UCLA"})
    assert fallback == [{"id": "I2", "name": "UCLA", "country_code": "", "source": "atlas_recent"}]
    assert em.primary_affiliations({}, [], {}) == []


@pytest.mark.parametrize("value", ["", "not json", "{}"])
def test_bad_json_is_empty(value: str) -> None:
    assert em.merge_metric_rows([{"counts_by_year_json": value}])["cites_by_year"] == {}


def test_affiliation_history_most_recent_first() -> None:
    merged = {
        "affiliations": [
            {"id": "I1", "name": "Old", "years": [2001]},
            {"id": "I2", "name": "New", "years": [2020, 2024]},
        ]
    }
    assert [row["name"] for row in em.affiliation_history(merged)] == ["New", "Old"]
