"""Unit tests for work-to-grant evidence links (S9.1). Offline only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.link.work_grants import (
    Link,
    build_grant_index,
    combine_links,
    load_cached_ack_texts,
    match_acknowledgements,
    match_fixed_strings,
    match_openalex_awards,
    normalize_award_id,
    resolve_nih_core_nums,
    sample_links,
)

NSF_FUNDER = {
    "funder_id": "https://openalex.org/F4320306076",
    "funder_display_name": "National Science Foundation",
}
NIH_FUNDER = {
    "funder_id": "https://openalex.org/F4320337361",
    "funder_display_name": "National Institute of Environmental Health Sciences",
}

GRANT_ROWS = [
    {"grant_key": "g_nsf", "source": "nsf_awards", "source_award_id": "2128556"},
    {"grant_key": "g_nih", "source": "nih_reporter", "source_award_id": "111"},
    {"grant_key": "g_nih2", "source": "nih_reporter", "source_award_id": "222"},
    {"grant_key": "g_usa", "source": "usaspending", "source_award_id": "ASST_NON_X"},
]
SOURCE = {
    "g_nsf": "nsf_awards",
    "g_nih": "nih_reporter",
    "g_nih2": "nih_reporter",
    "g_usa": "usaspending",
}


@pytest.mark.parametrize(
    ("raw", "family", "key"),
    [
        ("1r01es036575-01a1", "nih", "R01ES036575"),
        ("1R01ES012345-01", "nih", "R01ES012345"),
        ("R01 ES 012345", "nih", "R01ES012345"),
        ("R01ES012345", "nih", "R01ES012345"),
        ("UL1TR001449", "nih", "UL1TR001449"),
        ("T32ES018827", "nih", "T32ES018827"),
        ("P30CA008748", "nih", "P30CA008748"),
        ("P01E035542", None, None),  # malformed institute code: left unlinked
        ("DMR-2128556", "nsf", "2128556"),
        ("2128556", "nsf", "2128556"),
        ("123456", None, None),
        ("315289/2021-0", None, None),
    ],
)
def test_normalize_award_id(raw: str, family: str | None, key: str | None) -> None:
    aid = normalize_award_id(raw)
    assert (aid.family, aid.key) == (family, key)
    assert aid.raw == raw


def test_grant_index_uses_source_specific_keys() -> None:
    index = build_grant_index(GRANT_ROWS)
    assert index[("nsf", "2128556")] == ["g_nsf"]
    assert index[("nih", "111")] == ["g_nih"]
    assert ("nih", "ASST_NON_X") not in index


def test_openalex_nsf_and_nih_match_with_high_confidence() -> None:
    index = build_grant_index(GRANT_ROWS)
    lookup = {"R01ES012345": ["111"]}
    awards = [
        {"funder_award_id": "DMR-2128556", **NSF_FUNDER},
        {"funder_award_id": "1r01es012345-01", **NIH_FUNDER},
    ]
    links, review = match_openalex_awards("W1", awards, index, lookup, SOURCE)
    assert review == []
    got = {
        (link.grant_key, link.evidence_type, link.evidence_value, link.confidence) for link in links
    }
    assert got == {
        ("g_nsf", "openalex-award", "DMR-2128556", "high"),
        ("g_nih", "openalex-award", "1r01es012345-01", "high"),
    }


def test_nih_core_without_lookup_gives_no_link() -> None:
    index = build_grant_index(GRANT_ROWS)
    awards = [{"funder_award_id": "R01ES099999", **NIH_FUNDER}]
    links, review = match_openalex_awards("W1", awards, index, {}, SOURCE)
    assert links == [] and review == []


def test_uncertain_family_mismatch_is_omitted_from_links() -> None:
    index = build_grant_index(GRANT_ROWS)
    awards = [
        {
            "funder_award_id": "2128556",
            "funder_id": "https://openalex.org/F1",
            "funder_display_name": "Some Foundation",
        }
    ]
    links, review = match_openalex_awards("W1", awards, index, {}, SOURCE)
    assert links == []
    assert len(review) == 1
    assert review[0].grant_key == "g_nsf"
    assert "nsf" in review[0].reason


def test_precedence_keeps_strongest_evidence_per_pair() -> None:
    weaker = Link("W1", "g_nsf", "nsf_awards", "fixed-string", "COAST", "high")
    stronger = Link("W1", "g_nsf", "nsf_awards", "openalex-award", "2128556", "high")
    other = Link("W1", "g_nih", "nih_reporter", "fixed-string", "COAST", "high")
    combined = combine_links([weaker, other, stronger])
    assert [(link.grant_key, link.evidence_type) for link in combined] == [
        ("g_nih", "fixed-string"),
        ("g_nsf", "openalex-award"),
    ]


def test_acknowledgement_match_finds_exact_ids_only() -> None:
    index = build_grant_index(GRANT_ROWS)
    lookup = {"R01ES012345": ["111"]}
    texts = [
        "This work was supported by NIH grant R01 ES 012345 and by NSF award 2128556.",
        "Ignore 9999999 and P01E035542 here.",
    ]
    links = match_acknowledgements("W1", texts, index, lookup, SOURCE)
    got = {(link.grant_key, link.evidence_type) for link in links}
    assert got == {("g_nih", "acknowledgement-match"), ("g_nsf", "acknowledgement-match")}


def test_fixed_string_requires_phrase_and_target() -> None:
    assert match_fixed_strings("W1", ["COAST program"], None, ["g_x"], SOURCE) == []
    assert match_fixed_strings("W1", ["no match"], "Required COAST line", ["g_x"], SOURCE) == []
    links = match_fixed_strings(
        "W1", ["Required   COAST line"], "required coast line", ["g_x"], {"g_x": "csu_coast"}
    )
    assert [(link.grant_key, link.evidence_type, link.grant_source) for link in links] == [
        ("g_x", "fixed-string", "csu_coast")
    ]


def test_sampling_is_deterministic_and_order_independent() -> None:
    links = [
        Link(f"W{i}", f"g{i % 7}", "nih_reporter", "openalex-award", "R01ES012345", "high")
        for i in range(80)
    ]
    first = sample_links(links, 50, seed=91)
    second = sample_links(list(reversed(links)), 50, seed=91)
    assert first == second
    assert len(first) == 50
    assert sample_links(links[:10], 50, seed=91) == sorted(
        links[:10], key=lambda link: (link.work_id, link.grant_key)
    )


class _FakeReporter:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages
        self.calls: list[dict] = []

    def __call__(self, body: dict) -> tuple[int, str]:
        self.calls.append(body)
        return 200, json.dumps(self.pages[len(self.calls) - 1])


def test_resolve_nih_core_nums_caches_and_respects_budget(tmp_path: Path) -> None:
    cache = tmp_path / "lookup.json"
    page = {
        "meta": {"total": 2},
        "results": [
            {"appl_id": 111, "project_num": "1R01ES012345-01A1"},
            {"appl_id": 333, "project_num": "R01ES099999"},  # other core: ignored
        ],
    }
    fake = _FakeReporter([page])
    sleeps: list[float] = []
    got = resolve_nih_core_nums(
        ["R01ES012345", "R01ES000001"],
        cache_path=cache,
        transport=fake,
        max_requests=5,
        sleep=sleeps.append,
    )
    assert got == {"R01ES012345": ["111"], "R01ES000001": []}
    assert fake.calls[0]["criteria"]["project_nums"] == ["R01ES000001", "R01ES012345"]
    assert sleeps == []  # a single request needs no throttle
    # Second run is served from cache with no request.
    again = _FakeReporter([])
    assert resolve_nih_core_nums(
        ["R01ES012345"], cache_path=cache, transport=again, max_requests=0
    ) == {"R01ES012345": ["111"]}
    assert again.calls == []


def test_resolve_nih_core_nums_leaves_batch_unresolved_when_budget_ends(tmp_path: Path) -> None:
    cache = tmp_path / "lookup.json"
    page = {
        "meta": {"total": 600},
        "results": [{"appl_id": i, "project_num": "R01ES012345"} for i in range(500)],
    }
    fake = _FakeReporter([page])
    sleeps: list[float] = []
    got = resolve_nih_core_nums(
        ["R01ES012345"], cache_path=cache, transport=fake, max_requests=1, sleep=sleeps.append
    )
    assert got == {}  # pagination incomplete, so nothing is cached
    assert not cache.exists()


def test_resolve_nih_core_nums_raises_on_http_error(tmp_path: Path) -> None:
    def failing(body: dict) -> tuple[int, str]:
        return 500, "{}"

    with pytest.raises(RuntimeError):
        resolve_nih_core_nums(
            ["R01ES012345"], cache_path=tmp_path / "x.json", transport=failing, max_requests=2
        )


def test_load_cached_ack_texts_reads_only_acknowledgement_sections(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(
        json.dumps(
            {
                "work_id": "W1",
                "result": {
                    "sections": {
                        "methods": [{"text": "not used"}],
                        "funding": [{"text": "NSF 2128556"}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assert load_cached_ack_texts(tmp_path) == {"W1": ["NSF 2128556"]}
    assert load_cached_ack_texts(tmp_path / "missing") == {}
