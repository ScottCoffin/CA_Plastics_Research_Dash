"""Offline tests for Wikidata and Commons photo metadata (no network)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import atlas.ingest.wikidata_photos as wp

ORCID_A = "0000-0002-1825-0097"
ORCID_B = "0000-0001-5109-3700"


def _sparql_payload() -> dict[str, Any]:
    def binding(orcid: str, qid: str, label: str, image: str | None = None) -> dict[str, Any]:
        row: dict[str, Any] = {
            "orcid": {"type": "literal", "value": orcid},
            "item": {"type": "uri", "value": f"http://www.wikidata.org/entity/{qid}"},
            "itemLabel": {"type": "literal", "value": label},
        }
        if image:
            row["image"] = {"type": "uri", "value": image}
        return row

    return {
        "head": {"vars": ["orcid", "item", "itemLabel", "image"]},
        "results": {
            "bindings": [
                binding(
                    ORCID_A,
                    "Q1",
                    "José Núñez",
                    "http://commons.wikimedia.org/wiki/Special:FilePath/Jos%C3%A9%20N%C3%BA%C3%B1ez.jpg",
                ),
                binding(
                    ORCID_A,
                    "Q1",
                    "José Núñez",
                    "http://commons.wikimedia.org/wiki/Special:FilePath/Jos%C3%A9%20N%C3%BA%C3%B1ez.jpg",
                ),
                binding(ORCID_B, "Q2", "Jane Smith"),
            ]
        },
    }


def _commons_payload() -> dict[str, Any]:
    return {
        "batchcomplete": "",
        "query": {
            "normalized": [
                {"from": "File:Jos%C3%A9_N%C3%BA%C3%B1ez.jpg", "to": "File:José Núñez.jpg"}
            ],
            "pages": {
                "101": {
                    "ns": 6,
                    "title": "File:José Núñez.jpg",
                    "imageinfo": [
                        {
                            "thumburl": "https://upload.wikimedia.org/thumb/240px-Jose.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Jose.jpg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "LicenseUrl": {
                                    "value": "https://creativecommons.org/licenses/by-sa/4.0"
                                },
                                "Artist": {
                                    "value": (
                                        '<a href="//commons.wikimedia.org/wiki/User:X">'
                                        "Jane <b>X</b></a>"
                                    )
                                },
                                "Credit": {"value": "<span>Own work</span>"},
                                "AttributionRequired": {"value": "true"},
                            },
                        }
                    ],
                },
                "-1": {"ns": 6, "title": "File:Gone.jpg", "missing": ""},
            },
        },
    }


# ORCID normalization and query building


def test_normalize_orcid_accepts_url_and_bare_forms() -> None:
    assert wp.normalize_orcid("https://orcid.org/0000-0002-1825-009x") == "0000-0002-1825-009X"
    assert wp.normalize_orcid(f" {ORCID_A} ") == ORCID_A
    assert wp.normalize_orcid("http://www.orcid.org/" + ORCID_B) == ORCID_B


def test_normalize_orcid_rejects_malformed_values() -> None:
    assert wp.normalize_orcid("") is None
    assert wp.normalize_orcid(None) is None
    assert wp.normalize_orcid("0000-0002-1825") is None
    assert wp.normalize_orcid("https://example.org/0000-0002-1825-0097") is None


def test_build_sparql_query_uses_values_and_optional_image() -> None:
    query = wp.build_sparql_query([ORCID_A, ORCID_B])
    assert f'VALUES ?orcid {{"{ORCID_A}" "{ORCID_B}"}}' in query
    assert "?item wdt:P496 ?orcid" in query
    assert "OPTIONAL { ?item wdt:P18 ?image }" in query


def test_build_sparql_query_rejects_non_orcid_input() -> None:
    with pytest.raises(ValueError):
        wp.build_sparql_query(['0000" } DROP'])


def test_batched_splits_into_chunks_of_at_most_size() -> None:
    chunks = wp.batched(list(range(450)), wp.SPARQL_BATCH_SIZE)
    assert [len(c) for c in chunks] == [200, 200, 50]
    assert wp.batched([], 50) == []
    with pytest.raises(ValueError):
        wp.batched([1], 0)


# Response parsing


def test_parse_sparql_groups_items_and_images_and_dedupes() -> None:
    parsed = wp.parse_sparql_response(_sparql_payload())
    assert set(parsed) == {ORCID_A, ORCID_B}
    assert parsed[ORCID_A] == [
        {
            "qid": "Q1",
            "label": "José Núñez",
            "images": ["José Núñez.jpg"],
        }
    ]
    assert parsed[ORCID_B] == [{"qid": "Q2", "label": "Jane Smith", "images": []}]


def test_choose_item_prefers_item_with_image() -> None:
    items = [
        {"qid": "Q1", "label": "A", "images": []},
        {"qid": "Q9", "label": "B", "images": ["x.jpg"]},
    ]
    assert wp.choose_item(items)["qid"] == "Q9"
    assert wp.choose_item([]) is None


def test_image_file_from_url_decodes_name() -> None:
    url = "http://commons.wikimedia.org/wiki/Special:FilePath/Jos%C3%A9%20N%C3%BA%C3%B1ez.jpg"
    assert wp.image_file_from_url(url) == "José Núñez.jpg"
    assert wp.image_file_from_url("https://example.org/a.jpg") is None
    assert wp.image_file_from_url(None) is None


def test_parse_commons_extracts_licence_credit_and_thumb() -> None:
    parsed = wp.parse_commons_response(_commons_payload())
    meta = parsed["José Núñez.jpg"]
    assert meta["license_short"] == "CC BY-SA 4.0"
    assert meta["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0"
    assert meta["artist"] == "Jane X"
    assert meta["credit"] == "Own work"
    assert meta["attribution_required"] is True
    assert meta["thumb_url"].endswith("240px-Jose.jpg")
    assert "Gone.jpg" not in parsed


def test_strip_html_removes_tags_and_decodes_entities() -> None:
    assert wp.strip_html('<a href="x">Jane <b>Doe</b></a> &amp; co') == "Jane Doe & co"
    assert wp.strip_html("  <span>\n Own   work </span> ") == "Own work"
    assert wp.strip_html("") is None
    assert wp.strip_html(None) is None


# Licence classifier


@pytest.mark.parametrize(
    ("short", "url", "expected"),
    [
        ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0", "CC BY-SA"),
        ("CC BY-SA 3.0", None, "CC BY-SA"),
        ("CC BY 2.0", "https://creativecommons.org/licenses/by/2.0", "CC BY"),
        ("CC0", "https://creativecommons.org/publicdomain/zero/1.0", "CC0"),
        ("CC0 1.0", None, "CC0"),
        ("Public domain", None, "PD"),
        ("PD-self", None, "PD"),
        ("All rights reserved", None, "other"),
        ("Fair use", None, "other"),
        ("CC BY-NC-SA 4.0", "https://creativecommons.org/licenses/by-nc-sa/4.0", "other"),
        ("CC BY-ND 4.0", None, "other"),
        (None, "https://creativecommons.org/licenses/by-sa/3.0", "CC BY-SA"),
        (None, None, "other"),
    ],
)
def test_classify_license(short: str | None, url: str | None, expected: str) -> None:
    assert wp.classify_license(short, url) == expected


def test_is_usable_requires_open_licence_name_match_and_thumb() -> None:
    assert wp.is_usable("CC BY-SA", True, "https://thumb")
    assert not wp.is_usable("CC BY-SA", False, "https://thumb")
    assert not wp.is_usable("CC BY-SA", True, None)
    assert not wp.is_usable("other", True, "https://thumb")


# Name matcher


@pytest.mark.parametrize(
    ("atlas", "label", "expected"),
    [
        ("Jose Nunez", "José Núñez", True),
        ("José Núñez", "Jose Nunez", True),
        ("Chayo Fuentes Chang", "Chayo Fuentes Chang", True),
        ("Chayo Fuentes Chang", "Chayo Chang", True),
        ("Søren Lund", "Soren LUND", True),
        ("Scott Coffin", "Scott Smith", False),
        ("Scott Coffin", "", False),
        ("Scott Coffin", None, False),
        ("Coffin, Scott", "Scott Coffin", True),
    ],
)
def test_name_match_folds_case_and_accents(atlas: str, label: str | None, expected: bool) -> None:
    assert wp.name_match(atlas, label) is expected


# End to end with fake responses (cache, offline replay)


def test_build_expert_rows_online_then_offline_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []

    def fake_sparql(query: str) -> dict[str, Any]:
        sent.append("sparql")
        return _sparql_payload()

    def fake_commons(names: Any) -> dict[str, Any]:
        sent.append("commons")
        return _commons_payload()

    monkeypatch.setattr(wp, "sparql_request", fake_sparql)
    monkeypatch.setattr(wp, "commons_request", fake_commons)
    authors = [
        {"author_id": "A1", "name": "José Núñez", "orcid": f"https://orcid.org/{ORCID_A}"},
        {"author_id": "A2", "name": "Jane Smith", "orcid": f"https://orcid.org/{ORCID_B}"},
        {"author_id": "A3", "name": "No Orcid", "orcid": ""},
    ]
    rows = wp.build_expert_rows(authors, tmp_path)
    assert sent == ["sparql", "commons"]
    assert [r["author_id"] for r in rows] == ["A1", "A2"]

    first, second = rows
    assert first["wikidata_qid"] == "Q1"
    assert first["name_match"] is True
    assert first["image_file"] == "José Núñez.jpg"
    assert first["usable"] is True
    assert first["license_short"] == "CC BY-SA 4.0"
    assert second["wikidata_qid"] == "Q2"
    assert second["image_file"] is None
    assert second["name_match"] is True
    assert second["usable"] is False
    assert second["fetched_at"]

    def no_network(*_args: Any) -> dict[str, Any]:
        raise AssertionError("offline rebuild must not call the network")

    monkeypatch.setattr(wp, "sparql_request", no_network)
    monkeypatch.setattr(wp, "commons_request", no_network)
    replay = wp.build_expert_rows(authors, tmp_path, offline=True)
    assert replay == rows


def test_offline_without_cache_raises(tmp_path: Path) -> None:
    authors = [{"author_id": "A1", "name": "X Y", "orcid": ORCID_A}]
    with pytest.raises(FileNotFoundError):
        wp.build_expert_rows(authors, tmp_path, offline=True)


def test_limit_caps_distinct_orcids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_sparql(query: str) -> dict[str, Any]:
        seen.append(query)
        return {"results": {"bindings": []}}

    monkeypatch.setattr(wp, "sparql_request", fake_sparql)
    authors = [
        {"author_id": "A1", "name": "X", "orcid": ORCID_A},
        {"author_id": "A2", "name": "Y", "orcid": ORCID_B},
        {"author_id": "A3", "name": "Z", "orcid": ORCID_A},
    ]
    rows = wp.build_expert_rows(authors, tmp_path, limit=1)
    assert len(seen) == 1
    assert [r["author_id"] for r in rows] == ["A1", "A3"]
    assert all(r["wikidata_qid"] is None and r["usable"] is False for r in rows)
