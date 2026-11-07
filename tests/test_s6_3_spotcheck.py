from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from scripts.spotcheck_s6_3 import _search_candidates


def test_bounded_europe_pmc_pagination_advances_cursor_and_deduplicates():
    responses = {
        "*": {
            "resultList": {
                "result": [
                    {"pmcid": "PMC1", "doi": "10.3389/a.1"},
                    {"pmcid": "PMC2", "doi": "10.3389/b.2"},
                ]
            },
            "nextCursorMark": "cursor-2",
        },
        "cursor-2": {
            "resultList": {
                "result": [
                    {"pmcid": "PMC2", "doi": "10.3389/b.2"},
                    {"pmcid": "PMC3", "doi": "10.3389/c.3"},
                ]
            },
            "nextCursorMark": "cursor-3",
        },
    }

    def loader(url: str):
        cursor = parse_qs(urlsplit(url).query)["cursorMark"][0]
        return responses[cursor]

    rows, urls = _search_candidates(max_pages=2, json_loader=loader)
    assert [row["pmcid"] for row in rows] == ["PMC1", "PMC2", "PMC3"]
    assert [parse_qs(urlsplit(url).query)["cursorMark"][0] for url in urls] == [
        "*",
        "cursor-2",
    ]


def test_cursor_pagination_stops_when_server_repeats_cursor():
    def loader(url: str):
        cursor = parse_qs(urlsplit(url).query)["cursorMark"][0]
        return {
            "resultList": {"result": [{"pmcid": "PMC1", "doi": "10.3389/a.1"}]},
            "nextCursorMark": cursor,
        }

    rows, urls = _search_candidates(max_pages=4, json_loader=loader)
    assert len(rows) == 1
    assert len(urls) == 1
