"""California inference for authorships (ca_basis), author-anchored ingest, title artifact."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest

from atlas.ingest import openalex
from atlas.ingest.normalize import (
    is_placeholder_affiliation,
    matches_california_affiliation,
    normalize_records,
    title_key,
)

INSTITUTIONS = Path("data/processed/institutions.parquet")
CA_INST = "https://openalex.org/I84218800"  # UC Davis (registry)


@pytest.mark.parametrize(
    "text",
    [
        "University of California , , ,",
        "Department of Environmental Science, University of California, Riverside, CA 92521",
        "UC Santa Cruz, Santa Cruz",
        "Scripps Institution of Oceanography, La Jolla",
        "Some Lab, Oakland, CA, USA",
        "Southern California Coastal Water Research Project",
        "Stanford University",
    ],
)
def test_california_matcher_positives(text: str) -> None:
    assert matches_california_affiliation(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Universidad Autonoma de Baja California, Ensenada, Mexico",
        "California University of Pennsylvania, California, PA",
        "University of Toronto, Toronto, ON, Canada",
        "Oregon Water Institute, Portland, OR, USA",
        "Independent - affiliation not provided to SSRN",
        "CA Dept, Toronto",
    ],
)
def test_california_matcher_negatives(text: str) -> None:
    assert not matches_california_affiliation(text)


def test_placeholder_affiliations() -> None:
    assert is_placeholder_affiliation("")
    assert is_placeholder_affiliation("Independent - affiliation not provided to SSRN")
    assert not is_placeholder_affiliation("University of Toronto")


def _authorship(
    author: str, position: str, *, inst: str | None = None, raw: list[str] | None = None
):
    return {
        "author_position": position,
        "author": {"id": f"https://openalex.org/{author}", "display_name": author},
        "institutions": [{"id": inst, "display_name": "x"}] if inst else [],
        "raw_affiliation_strings": raw or [],
    }


def _work(wid: str, year: int, title: str, authorships: list[dict]) -> dict:
    return {
        "id": f"https://openalex.org/{wid}",
        "title": title,
        "publication_year": year,
        "publication_date": f"{year}-06-01",
        "type": "article",
        "authorships": authorships,
    }


def _normalize(tmp_path: Path, records: list[dict]):
    result = normalize_records(
        records,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "out",
        qc_path=tmp_path / "qc.md",
        source="test",
        suppressions_path=None,
        generated_at="test",
    )
    rows = pq.read_table(result.output_dir / "authorships.parquet").to_pylist()
    works = {
        r["work_id"]: r for r in pq.read_table(result.output_dir / "works.parquet").to_pylist()
    }
    authors = {
        r["author_id"]: r for r in pq.read_table(result.output_dir / "authors.parquet").to_pylist()
    }
    return result, rows, works, authors


def test_carry_forward_window_and_placeholders(tmp_path: Path) -> None:
    records = [
        _work(
            "W1",
            2020,
            "Registry anchored microplastics study alpha",
            [
                _authorship("A1", "first", inst=CA_INST),
            ],
        ),
        # within 2 years, no affiliation -> carried
        _work(
            "W2",
            2022,
            "Alpine microplastics conference paper beta",
            [
                _authorship("A1", "first"),
            ],
        ),
        # placeholder affiliation, within window -> carried
        _work(
            "W3",
            2021,
            "Placeholder preprint gamma on microplastics",
            [
                _authorship("A1", "last", raw=["Independent - affiliation not provided to SSRN"]),
            ],
        ),
        # 3 years away -> not carried
        _work(
            "W4",
            2023,
            "Too late microplastics paper delta here",
            [
                _authorship("A1", "first"),
            ],
        ),
        # real non-CA raw affiliation -> never carried
        _work(
            "W5",
            2021,
            "Toronto microplastics paper epsilon here",
            [
                _authorship("A1", "first", raw=["University of Toronto, Toronto"]),
            ],
        ),
        # unknown author with no CA authorship anywhere -> not carried
        _work(
            "W6",
            2021,
            "Unrelated microplastics paper zeta here",
            [
                _authorship("A2", "first"),
            ],
        ),
        # raw affiliation only
        _work(
            "W7",
            2010,
            "Raw affiliation microplastics paper eta",
            [
                _authorship("A3", "first", raw=["UC Riverside, Riverside, CA 92521"]),
            ],
        ),
    ]
    result, rows, works, authors = _normalize(tmp_path, records)
    basis = {r["work_id"]: r["ca_basis"] for r in rows}
    assert basis == {
        "W1": "registry",
        "W2": "author_carry_forward",
        "W3": "author_carry_forward",
        "W4": "",
        "W5": "",
        "W6": "",
        "W7": "raw_affiliation",
    }
    assert works["W2"]["ca_led"] is True and works["W2"]["ca_any_author"] is True
    assert works["W4"]["ca_any_author"] is False
    assert authors["A1"]["ca_works_count"] == 3
    assert authors["A3"]["ca_works_count"] == 1
    assert result.metrics["authorships_ca_carry_forward"] == 2
    assert result.metrics["authorships_ca_raw_affiliation"] == 1


def test_title_key_ignores_leading_title_artifact() -> None:
    clean = "Exploring Microplastic Distribution in Western North American Snow"
    assert title_key("Title " + clean) == title_key(clean)
    assert title_key("Title: " + clean) == title_key(clean)
    assert title_key("Titles of the world") == "titlesoftheworld"


def test_preprint_with_title_artifact_collapses_into_article(tmp_path: Path) -> None:
    clean = "Exploring Microplastic Distribution in Western North American Snow"
    article = _work("W10", 2024, clean, [_authorship("A1", "first", inst=CA_INST)])
    preprint = _work("W11", 2023, "Title " + clean, [_authorship("A1", "first", inst=CA_INST)])
    preprint["type"] = "preprint"
    _, _, works, _ = _normalize(tmp_path, [article, preprint])
    assert set(works) == {"W10"}
    assert works["W10"]["title"] == clean


# --- author-anchored ingest -------------------------------------------------------------


def test_anchored_keep_or_drop() -> None:
    anchors = ["A1"]
    no_inst = {"authorships": [_authorship("A1", "first")]}
    placeholder = {
        "authorships": [_authorship("A1", "first", raw=["Independent - affiliation not provided"])]
    }
    raw_ca = {
        "authorships": [
            _authorship(
                "A1",
                "first",
                inst="https://openalex.org/I1",
                raw=["University of California, Davis, CA"],
            )
        ]
    }
    toronto_inst = {
        "authorships": [_authorship("A1", "first", inst="https://openalex.org/I2", raw=["Toronto"])]
    }
    toronto_raw = {"authorships": [_authorship("A1", "first", raw=["University of Toronto"])]}
    other_author = {"authorships": [_authorship("A9", "first")]}
    assert openalex.keep_anchored_work(no_inst, anchors)
    assert openalex.keep_anchored_work(placeholder, anchors)
    assert openalex.keep_anchored_work(raw_ca, anchors)
    assert not openalex.keep_anchored_work(toronto_inst, anchors)
    assert not openalex.keep_anchored_work(toronto_raw, anchors)
    assert not openalex.keep_anchored_work(other_author, anchors)


def test_anchored_url_filter() -> None:
    from atlas.query import load_query_config

    config = load_query_config("config/queries.yml")
    url = openalex.build_works_url(config, [], author_ids=["A1", "A2"], start_date="1950-01-01")
    assert "authorships.author.id%3AA1%7CA2" in url
    assert "institutions.id" not in url
    with pytest.raises(ValueError):
        openalex.build_works_url(config, ["I1"], author_ids=["A1"])


def test_ingest_live_anchored_units_filter_results(monkeypatch, tmp_path: Path) -> None:
    urls: list[str] = []
    good = {
        "id": "https://openalex.org/W100",
        "publication_date": "2022-01-01",
        "publication_year": 2022,
        "updated_date": "2022-02-01",
        "authorships": [_authorship("A1", "first")],
    }
    bad = {
        "id": "https://openalex.org/W101",
        "publication_date": "2022-01-01",
        "publication_year": 2022,
        "updated_date": "2022-02-01",
        "authorships": [_authorship("A1", "first", raw=["University of Toronto"])],
    }

    def fake_request(url, *, logger, **_):
        urls.append(url)
        logger._request_metrics.append(
            {"credits_known": True, "credits": 10, "cost_known": True, "cost_usd": 0.001}
        )
        results = [good, bad] if "authorships.author.id" in url else []
        return {"results": results, "meta": {"next_cursor": None}}

    monkeypatch.setattr(openalex, "_request_json", fake_request)
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = openalex.OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "w.parquet",
        high_water_mark=tmp_path / "hw.json",
        usage_log=tmp_path / "usage.jsonl",
    )
    result = openalex.ingest_live(
        institution_ids=["I1"],
        paths=paths,
        start_year=1950,
        end_year=2027,
        anchor_author_ids=["https://openalex.org/A1"],
    )
    assert len(urls) == 2
    assert result["anchored_fetched"] == 2 and result["anchored_kept"] == 1
    ids = {r["openalex_id"] for r in pq.read_table(paths.output_parquet).to_pylist()}
    assert ids == {"W100"}


def test_ingest_live_without_anchors_makes_no_anchored_units(monkeypatch, tmp_path: Path) -> None:
    urls: list[str] = []

    def fake_request(url, *, logger, **_):
        urls.append(url)
        logger._request_metrics.append(
            {"credits_known": True, "credits": 10, "cost_known": True, "cost_usd": 0.001}
        )
        return {"results": [], "meta": {"next_cursor": None}}

    monkeypatch.setattr(openalex, "_request_json", fake_request)
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = openalex.OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "w.parquet",
        high_water_mark=tmp_path / "hw.json",
        usage_log=tmp_path / "usage.jsonl",
    )
    openalex.ingest_live(institution_ids=["I1"], paths=paths, start_year=2020, end_year=2020)
    assert len(urls) == 1 and "authorships.author.id" not in urls[0]


def test_raw_affiliation_url_and_keep_gate() -> None:
    from atlas.query import load_query_config

    config = load_query_config("config/queries.yml")
    url = openalex.build_works_url(config, [], raw_affiliation_term="California", per_page=1)
    assert "raw_affiliation_strings.search%3ACalifornia" in url
    assert "institutions.id" not in url
    good = {"authorships": [_authorship("A1", "first", raw=["Dept X, University of California"])]}
    bad = {"authorships": [_authorship("A1", "first", raw=["Universidad de Baja California"])]}
    assert openalex.keep_raw_affiliation_work(good)
    assert not openalex.keep_raw_affiliation_work(bad)


def test_ingest_live_raw_scope_and_burst_429_accounting(monkeypatch, tmp_path: Path) -> None:
    urls: list[str] = []
    good = {
        "id": "https://openalex.org/W200",
        "publication_date": "2022-01-01",
        "publication_year": 2022,
        "updated_date": "2022-02-01",
        "authorships": [_authorship("A1", "first", raw=["Moss Landing, CA 95039"])],
    }
    bad = {**good, "id": "https://openalex.org/W201"}
    bad["authorships"] = [_authorship("A1", "first", raw=["Universidad de Baja California"])]

    def fake_request(url, *, logger, **_):
        urls.append(url)
        if "raw_affiliation_strings.search" in url:
            # a rejected burst-limit attempt without credit headers, then the real page
            logger._request_metrics.append(
                {
                    "credits_known": False,
                    "credits": 0,
                    "cost_known": False,
                    "cost_usd": 0,
                    "status_code": 429,
                }
            )
        logger._request_metrics.append(
            {"credits_known": True, "credits": 10, "cost_known": True, "cost_usd": 0.001}
        )
        results = [good, bad] if "raw_affiliation_strings.search" in url else []
        return {"results": results, "meta": {"next_cursor": None}}

    monkeypatch.setattr(openalex, "_request_json", fake_request)
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = openalex.OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "w.parquet",
        high_water_mark=tmp_path / "hw.json",
        usage_log=tmp_path / "usage.jsonl",
    )
    result = openalex.ingest_live(
        institution_ids=["I1"],
        paths=paths,
        start_year=1950,
        end_year=2027,
        raw_affiliation_scope=True,
    )
    assert len(urls) == 2
    assert result["raw_affiliation_fetched"] == 2 and result["raw_affiliation_kept"] == 1
    assert result["credits"] == 30.0
    ids = {r["openalex_id"] for r in pq.read_table(paths.output_parquet).to_pylist()}
    assert ids == {"W200"}


def test_carry_forward_dropped_when_orcid_contradicts() -> None:
    """Owner CA-CARRY-ORCID (2026-11-12): a dated non-CA employment covering the year wins."""
    from collections import defaultdict

    from atlas.ingest.normalize import _apply_carry_forward

    works = [{"work_id": "W1", "year": 2014}, {"work_id": "W2", "year": 2016}]
    rows = [
        {
            "work_id": "W1",
            "author_id": "A1",
            "ca_basis": "registry",
            "institution_ids": ["I"],
            "raw_affiliation": "UC Davis",
        },
        {
            "work_id": "W2",
            "author_id": "A1",
            "ca_basis": "",
            "institution_ids": [],
            "raw_affiliation": "",
        },
    ]
    state: defaultdict[str, dict] = defaultdict(lambda: {"ca_works": set()})
    toronto = [{"org": "U Toronto", "start_year": 2016, "end_year": None}]
    dropped = _apply_carry_forward(rows, works, state, {"A1": (toronto, [[2010, 2013]])})
    assert dropped == 1 and rows[1]["ca_basis"] == ""
    rows[1]["ca_basis"] = ""
    assert _apply_carry_forward(rows, works, state, {}) == 0
    assert rows[1]["ca_basis"] == "author_carry_forward"
