"""Offline tests for scripts/bq1_3_recall_probes.py (BQ-1.3 recall probes).

No test calls the network. Live fetches are replaced by a fake fetcher that answers from synthetic
responses, and the offline rebuild reads the cache that the fake fetcher wrote.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "bq1_3_recall_probes", ROOT / "scripts" / "bq1_3_recall_probes.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look the module up by name while it loads, so it must be registered first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bq = _load_module()
ANCHORS = json.loads((ROOT / "tests" / "fixtures" / "theme_anchors.json").read_text("utf-8"))[
    "anchors"
]
# The fake OpenAlex "retrieves" every second anchor, so both hits and misses occur.
RETRIEVED = {a["openalex_id"] for i, a in enumerate(ANCHORS) if i % 2 == 0}


def _params(url: str) -> dict[str, str]:
    query = urllib.parse.urlsplit(url).query
    return {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}


def _fake_fetch(url: str) -> tuple[dict[str, Any], float, str]:
    """Synthetic OpenAlex answers keyed on the request filter. Counts are fixed."""

    filt = _params(url)["filter"]
    fetched_at = "2026-11-25T10:00:00+00:00"
    if "ids.openalex:" in filt:
        ids = filt.split("ids.openalex:")[1].split(",")[0].split("|")
        results = [{"id": f"https://openalex.org/{i}"} for i in ids if i in RETRIEVED]
        body = {"meta": {"count": len(results)}, "results": results}
        return body, 10.0, fetched_at
    counts = {
        ("primary_topic.id:T10753", False): 100,  # T10753 alone
        ("title_and_abstract", False): 40,  # v3.1 alone
        ("primary_topic.id:T10753", True): 30,  # intersection
    }
    has_topic = "primary_topic.id:T10753" in filt
    has_search = "title_and_abstract.search:" in filt
    if has_topic and has_search:
        count, credits = counts[("primary_topic.id:T10753", True)], 10.0
    elif has_topic:
        count, credits = counts[("primary_topic.id:T10753", False)], 1.0
    else:
        count, credits = counts[("title_and_abstract", False)], 10.0
    return (
        {"meta": {"count": count}, "results": [{"id": "https://openalex.org/W1"}]},
        credits,
        fetched_at,
    )


# ---------------------------------------------------------------- Wilson interval


@pytest.mark.parametrize(
    ("k", "n", "expected"),
    [
        (5, 50, (0.0435, 0.2136)),  # hand: centre 0.1285, half-width 0.0850
        (0, 10, (0.0, 0.2775)),  # upper = z^2 / (n + z^2)
        (10, 10, (0.7225, 1.0)),  # mirror image of k = 0
        (28, 50, (0.4231, 0.6884)),
    ],
)
def test_wilson_matches_hand_values(k: int, n: int, expected: tuple[float, float]) -> None:
    low, high = bq.wilson_interval(k, n)
    assert low == pytest.approx(expected[0], abs=1e-4)
    assert high == pytest.approx(expected[1], abs=1e-4)


def test_wilson_zero_n_and_bad_inputs() -> None:
    assert bq.wilson_interval(0, 0) == (None, None)
    with pytest.raises(ValueError):
        bq.wilson_interval(11, 10)
    with pytest.raises(ValueError):
        bq.wilson_interval(-1, 10)


# ---------------------------------------------------------------- inputs


def _language_file(tmp_path: Path, sets: list[dict[str, Any]]) -> Path:
    path = tmp_path / "language_probe.json"
    path.write_text(json.dumps({"term_sets": sets}), encoding="utf-8")
    return path


def _sets(count: int, sample_size: int = 50, in_v31: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "id": f"set-{i}",
            "languages": ["xx"],
            "count": 10,
            "sample_size": sample_size,
            "sample_in_v31": in_v31,
        }
        for i in range(count)
    ]


def test_language_rows_are_per_set_and_not_pooled(tmp_path: Path) -> None:
    sets = _sets(bq.EXPECTED_LANGUAGE_SETS)
    sets[0].update(sample_size=50, sample_in_v31=5)
    sets[1].update(sample_size=10, sample_in_v31=0)
    rows = bq.load_language_rows(_language_file(tmp_path, sets))
    assert len(rows) == bq.EXPECTED_LANGUAGE_SETS
    assert rows[0]["k"] == 5 and rows[0]["n"] == 50 and rows[0]["share"] == 0.1
    assert (rows[0]["wilson95_low"], rows[0]["wilson95_high"]) == pytest.approx(
        (0.0435, 0.2136), abs=1e-4
    )
    assert rows[1]["wilson95_low"] == 0.0 and rows[1]["wilson95_high"] == pytest.approx(
        0.2775, abs=1e-4
    )


def test_language_rows_reject_bad_counts(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        bq.load_language_rows(_language_file(tmp_path, _sets(3)))
    bad = _sets(bq.EXPECTED_LANGUAGE_SETS)
    bad[0].update(sample_size=5, sample_in_v31=6)
    with pytest.raises(ValueError):
        bq.load_language_rows(_language_file(tmp_path, bad))


def test_committed_anchor_fixture_has_42_anchors_and_known_themes() -> None:
    anchors = bq.load_anchors()
    assert len(anchors) == 42
    assert {a["theme"] for a in anchors} <= set(bq.LENS_GROUP_OF_THEME)


# ---------------------------------------------------------------- request text


def test_anchor_probe_url_combines_search_types_and_ids() -> None:
    config = bq.load_query_config(bq.CONFIG)
    url = bq.anchor_probe_url(config, ["W1", "W2"])
    filt = _params(url)["filter"]
    assert filt.startswith("title_and_abstract.search:")
    assert "ids.openalex:W1|W2" in filt
    for type_filter in bq.type_filters(config):
        assert type_filter in filt


def test_anchors_fit_in_one_probe_call_and_t10753_uses_primary_topic() -> None:
    config = bq.load_query_config(bq.CONFIG)
    calls = bq.planned_calls(config, ANCHORS)
    labels = [c.label for c in calls]
    assert labels == ["anchor_probe_1", "t10753_count", "v31_count", "v31_and_t10753_count"]
    assert "primary_topic.id:T10753" in _params(calls[1].url)["filter"]
    assert "title_and_abstract.search:" not in _params(calls[1].url)["filter"]
    assert _params(calls[2].url)["per-page"] == "1"
    assert "primary_topic.id:T10753" in _params(calls[3].url)["filter"]


def test_id_filter_refuses_more_than_fifty() -> None:
    with pytest.raises(ValueError):
        bq.id_filter([f"W{i}" for i in range(51)])


# ---------------------------------------------------------------- scoring


def test_anchor_scores_sum_to_overall_and_name_misses() -> None:
    records = {
        "anchor_probe_1": {
            "body": {
                "results": [
                    {"id": f"https://openalex.org/{a['openalex_id']}"}
                    for a in ANCHORS
                    if a["openalex_id"] in RETRIEVED
                ]
            }
        }
    }
    scored = bq.score_anchors(ANCHORS, records)
    assert scored["overall"]["n"] == 42
    assert scored["overall"]["k"] == len(RETRIEVED)
    assert sum(t["n"] for t in scored["per_theme"]) == 42
    assert sum(g["n"] for g in scored["per_lens_group"]) == 42
    assert len(scored["overall"]["misses"]) == 42 - len(RETRIEVED)
    for theme in scored["per_theme"]:
        assert theme["k"] + len(theme["misses"]) == theme["n"]


def test_t10753_shares_use_the_right_denominators() -> None:
    records = {
        "t10753_count": {"body": {"meta": {"count": 100}}},
        "v31_count": {"body": {"meta": {"count": 40}}},
        "v31_and_t10753_count": {"body": {"meta": {"count": 30}}},
    }
    out = bq.score_t10753(records)
    assert out["share_t10753_retrieved_by_v31"]["share"] == 0.3
    assert out["share_v31_in_t10753"]["share"] == 0.75
    assert out["count_intersection"] == 30


def test_t10753_rejects_inconsistent_counts() -> None:
    records = {
        "t10753_count": {"body": {"meta": {"count": 10}}},
        "v31_count": {"body": {"meta": {"count": 40}}},
        "v31_and_t10753_count": {"body": {"meta": {"count": 30}}},
    }
    with pytest.raises(bq.FetchError):
        bq.score_t10753(records)


# ---------------------------------------------------------------- cache, cap and offline


def test_credit_cap_stops_before_the_next_call(tmp_path: Path) -> None:
    calls = [bq.Call(f"c{i}", f"https://example.invalid/{i}") for i in range(4)]
    cache = bq.CallCache(
        tmp_path,
        offline=False,
        fetcher=lambda url: (
            {"meta": {"count": 1}, "results": [{"id": "x"}]},
            10.0,
            "2026-11-25T10:00:00+00:00",
        ),
    )
    with pytest.raises(bq.CreditCapError):
        bq.run_calls(calls, cache, cap=25.0)


def test_offline_refuses_to_fetch(tmp_path: Path) -> None:
    cache = bq.CallCache(tmp_path, offline=True, fetcher=_fake_fetch)
    with pytest.raises(bq.CacheMiss):
        bq.run_calls([bq.Call("c0", "https://example.invalid/0")], cache)


def test_end_to_end_offline_rebuild_is_byte_identical(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    live = bq.run_probe(offline=False, cache_dir=cache_dir, fetcher=_fake_fetch)
    out_a, out_b = tmp_path / "a.json", tmp_path / "b.json"
    bq.write_json(out_a, live)
    rebuilt = bq.run_probe(offline=True, cache_dir=cache_dir)
    bq.write_json(out_b, rebuilt)
    assert out_a.read_bytes() == out_b.read_bytes()
    assert live["schema_version"] == "bq13-v1"
    assert live["probe_label"] == "PROBE"
    assert live["cost"]["credits"] == pytest.approx(31.0)
    assert live["t10753_overlap"]["count_intersection"] == 30
    assert len(live["language_probe"]["term_sets"]) == bq.EXPECTED_LANGUAGE_SETS


def test_check_skips_without_cache(tmp_path: Path) -> None:
    assert bq.check_committed(tmp_path / "absent") == 0


def test_check_detects_a_stale_committed_file(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    payload = bq.run_probe(offline=False, cache_dir=cache_dir, fetcher=_fake_fetch)
    out = tmp_path / "bq1_3.json"
    bq.write_json(out, payload)
    assert bq.check_committed(cache_dir, out) == 0
    payload["t10753_overlap"]["count_intersection"] = 1
    bq.write_json(out, payload)
    assert bq.check_committed(cache_dir, out) == 1
