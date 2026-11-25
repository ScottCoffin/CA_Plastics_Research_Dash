"""Tests for the BQ-4.2 rising-share flag on synthetic inputs (no repository data)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import pytest

from atlas.analytics.rising_share import (
    NO_TREND,
    REASON_LOIO,
    REASON_LOIO_NOT_TESTABLE,
    REASON_VOLUME,
    cochran_armitage,
    complete_years,
    evaluate_tag,
    evaluate_tags,
    institutions_by_work,
    window_years,
)
from atlas.analytics.topic_series import CaWork

LAST_COMPLETE = 2025  # as-of 2026-11-25; 2026 is partial and must not count
TAG = "air"
TAXONOMY = {
    "domain_tags": [
        {"id": TAG, "seed_concepts": ["airborne"]},
        {"id": "exp", "experimental": True, "seed_concepts": []},
    ]
}


def _work(n: int, year: int | None, source: str | None, tag: str = TAG) -> CaWork:
    return CaWork(
        work_id=f"W{n:05d}",
        year=year,
        plastic_related=True,
        topic_sources={tag: source} if source else {},
    )


def _plan(
    totals: Mapping[int, int],
    tagged: Mapping[int, int],
    *,
    source: str = "rule",
    tag: str = TAG,
    start: int = 0,
) -> list[CaWork]:
    """``totals[y]`` plastic works in year y; the first ``tagged[y]`` of them carry the tag."""

    works: list[CaWork] = []
    n = start
    for year in sorted(totals):
        for i in range(totals[year]):
            n += 1
            works.append(_work(n, year, source if i < tagged.get(year, 0) else None, tag))
    return works


def _rising(*, window_tagged: int = 8, source: str = "rule") -> list[CaWork]:
    """20 plastic works a year, 1 tagged until 2022, then ``window_tagged`` tagged a year."""

    totals = {y: 20 for y in range(2010, 2026)}
    tagged = {y: (1 if y <= 2022 else window_tagged) for y in totals}
    return _plan(totals, tagged, source=source)


def _spread_institutions(works: Sequence[CaWork]) -> dict[str, frozenset[str]]:
    """Every tagged work has its own institution, so no single one carries the rise."""

    return {w.work_id: frozenset({f"I{w.work_id}"}) for w in works if w.topic_sources.get(TAG)}


def _one_institution(works: Sequence[CaWork]) -> dict[str, frozenset[str]]:
    """Tagged works from 2023 on all come from institution I1; earlier tagged works do not."""

    out: dict[str, frozenset[str]] = {}
    for w in works:
        if not w.topic_sources.get(TAG):
            continue
        out[w.work_id] = frozenset({"I1"} if w.year and w.year >= 2023 else {f"E{w.work_id}"})
    return out


def test_cochran_armitage_matches_hand_computed_value():
    # r = (10, 20, 30) of n = 100 at scores -1, 0, 1 (equivalent to 2020..2022 by shift invariance)
    # pbar = 0.2; T = -1*(10-20) + 0 + 1*(30-20) = 20; Var = 0.16 * 200 = 32; z = 20/sqrt(32)
    result = cochran_armitage([10, 20, 30], [100, 100, 100], [2020, 2021, 2022])
    assert result.z == pytest.approx(5 / math.sqrt(2))
    assert result.p == pytest.approx(math.erfc(2.5))
    assert result.p == pytest.approx(4.0695e-4, rel=1e-4)
    assert result.passes


def test_cochran_armitage_falling_share_does_not_pass_and_undefined_is_no_trend():
    falling = cochran_armitage([30, 20, 10], [100, 100, 100], [2020, 2021, 2022])
    assert falling.z < 0 and not falling.passes
    assert cochran_armitage([0, 0], [10, 10], [2020, 2021]) == NO_TREND
    assert cochran_armitage([5, 5], [10, 10], [2020, 2021]) == NO_TREND  # no variation
    assert cochran_armitage([1], [0], [2020]) == NO_TREND  # no works


def test_partial_year_is_excluded_from_the_series_and_the_window():
    assert complete_years(_rising(), LAST_COMPLETE)[-1] == 2025
    assert window_years(LAST_COMPLETE) == [2023, 2024, 2025]
    works = _rising() + [_work(9000 + i, 2026, TAG) for i in range(30)]  # partial year, all tagged
    record = evaluate_tag(works, TAG, last_complete=LAST_COMPLETE, institutions={})
    assert 2026 not in complete_years(works, LAST_COMPLETE)
    assert record["window_count"] == 24  # 2023-2025 only: 8 a year
    assert record["total_complete_years"] == 13 + 24


@pytest.mark.parametrize(("tagged_2025", "expect_volume_failure"), [(3, True), (4, False)])
def test_volume_rule_boundary_is_ten_works_in_the_last_three_complete_years(
    tagged_2025: int, expect_volume_failure: bool
):
    # window 2023-2025 holds 3 + 3 + tagged_2025 works: 9 fails the volume rule, 10 passes it
    totals = {y: 20 for y in range(2010, 2026)}
    tagged = {y: (1 if y <= 2022 else 3) for y in totals}
    tagged[2025] = tagged_2025
    works = _plan(totals, tagged)
    record = evaluate_tag(
        works, TAG, last_complete=LAST_COMPLETE, institutions=_spread_institutions(works)
    )
    assert record["window_count"] == 6 + tagged_2025
    assert (REASON_VOLUME in record["reasons_failed"]) is expect_volume_failure


def test_volume_rule_passes_at_exactly_ten_for_a_clear_rise():
    works = _plan(
        {y: 20 for y in range(2010, 2026)},
        {**{y: 1 for y in range(2010, 2023)}, 2023: 3, 2024: 3, 2025: 4},
    )
    record = evaluate_tag(
        works, TAG, last_complete=LAST_COMPLETE, institutions=_spread_institutions(works)
    )
    assert record["window_count"] == 10
    assert REASON_VOLUME not in record["reasons_failed"]  # volume passes; trend decides the rest


def test_tag_rising_only_because_of_one_institution_fails_leave_one_institution_out():
    works = _rising(window_tagged=8)
    record = evaluate_tag(
        works, TAG, last_complete=LAST_COMPLETE, institutions=_one_institution(works)
    )
    # the full series rises (so the trend and volume checks pass) ...
    assert record["trend"]["p"] < 0.05 and record["trend"]["slope_sign"] == "positive"
    assert record["window_count"] >= 10
    # ... but dropping I1 removes the rise, so leave-one-institution-out fails
    assert record["loio"]["pass"] is False
    assert record["loio"]["worst_institution"] == "I1"
    assert record["loio"]["worst_p"] > 0.05
    assert record["flag"] is False
    assert record["reasons_failed"] == [REASON_LOIO]


def test_rise_spread_over_many_institutions_passes_leave_one_institution_out():
    works = _rising(window_tagged=8)
    record = evaluate_tag(
        works, TAG, last_complete=LAST_COMPLETE, institutions=_spread_institutions(works)
    )
    assert record["loio"]["pass"] is True
    assert record["loio"]["institutions_tested"] == 24
    assert record["loio"]["worst_p"] < 0.05
    assert record["flag"] is True


def test_missing_institution_links_make_leave_one_institution_out_not_testable():
    works = _rising(window_tagged=8)
    record = evaluate_tag(works, TAG, last_complete=LAST_COMPLETE, institutions={})
    assert record["loio"]["pass"] is False
    assert record["loio"]["institutions_tested"] == 0
    assert record["reasons_failed"] == [REASON_LOIO_NOT_TESTABLE]
    assert record["flag"] is False


def test_empty_label_source_variant_is_not_testable_and_does_not_block():
    works = _rising(window_tagged=8, source="rule")  # owner and model sources are empty
    record = evaluate_tag(
        works, TAG, last_complete=LAST_COMPLETE, institutions=_spread_institutions(works)
    )
    assert record["sensitivity"] == {
        "all_sources": "pass",
        "owner_model_only": "not_testable",
        "rule_only": "pass",
    }
    assert record["flag"] is True


def test_a_non_empty_variant_that_fails_blocks_the_flag():
    # the rise comes from rule labels, but the owner-labelled works are flat: owner variant fails
    totals = {y: 20 for y in range(2010, 2026)}
    rule = _plan(totals, {y: (1 if y <= 2022 else 8) for y in totals}, source="rule")
    owner_only = _plan(
        {y: 5 for y in range(2010, 2026)},
        {y: 1 for y in range(2010, 2026)},
        source="owner",
        start=1000,
    )
    works = rule + owner_only
    record = evaluate_tag(works, TAG, last_complete=LAST_COMPLETE, institutions={})
    assert record["sensitivity"]["owner_model_only"] == "fail"
    assert "sensitivity:owner_model_only" in record["reasons_failed"]
    assert record["flag"] is False


def test_experimental_tags_are_never_flagged():
    works = _plan(
        {y: 20 for y in range(2010, 2026)},
        {y: (1 if y <= 2022 else 8) for y in range(2010, 2026)},
        tag="exp",
    )
    body = evaluate_tags(works, TAXONOMY, last_complete=LAST_COMPLETE, institutions={})
    assert [t["tag"] for t in body["tags"]] == [TAG]
    assert "exp" not in body["flagged"]
    assert body["tags_excluded"] == [{"tag": "exp", "reason": "experimental"}]


def test_institution_ids_are_compacted_from_openalex_urls():
    mapping = institutions_by_work(
        [
            ("https://openalex.org/W1", ["https://openalex.org/I9", "https://openalex.org/I9"]),
            ("https://openalex.org/W1", None),
        ]
    )
    assert mapping == {"W1": frozenset({"I9"})}
