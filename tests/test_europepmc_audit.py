from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from atlas.ingest import europepmc_audit as audit
from atlas.query import load_query_config


def test_normalize_doi() -> None:
    assert audit.normalize_doi("https://doi.org/10.1000/ABC.1") == "10.1000/abc.1"
    assert audit.normalize_doi("DOI:10.1/X") == "10.1/x"
    assert audit.normalize_doi(None) == ""


def test_missing_and_queryable() -> None:
    assert audit.missing_dois(["10.1/a", "10.1/b"], ["10.1/a"]) == ["10.1/b"]
    assert audit.is_queryable_doi("10.1/a")
    assert not audit.is_queryable_doi("10.1/a,b")
    assert not audit.is_queryable_doi("10.1/a|b")


def test_batches_cap_at_50() -> None:
    batches = audit.doi_batches([f"10.1/{i}" for i in range(120)])
    assert [len(b) for b in batches] == [50, 50, 20]
    with pytest.raises(ValueError):
        audit.doi_batches(["10.1/a"], size=51)


def test_query_strings() -> None:
    q = parse_qs(urlparse(audit.epmc_url(audit.EPMC_QUERY)).query)
    assert q["query"][0].startswith('AFF:"California"')
    assert q["cursorMark"] == ["*"]
    assert q["resultType"] == ["lite"]
    config = load_query_config()
    url = audit.build_doi_url(config, ["10.1/a", "10.1/b"])
    flt = parse_qs(urlparse(url).query)["filter"][0]
    assert flt.startswith("doi:https://doi.org/10.1/a|https://doi.org/10.1/b,")
    assert "title_and_abstract.search" in flt
    with pytest.raises(ValueError):
        audit.build_doi_url(config, [f"10.1/{i}" for i in range(51)])


def test_fetch_benchmark_pages_and_caches(tmp_path: Path) -> None:
    pages = {
        "*": {"nextCursorMark": "c2", "resultList": {"result": [{"doi": "10.1/A"}, {"id": "x"}]}},
        "c2": {
            "nextCursorMark": "c2",
            "resultList": {"result": [{"doi": "https://doi.org/10.1/b"}]},
        },
    }

    def fake(url: str) -> dict:
        return pages[parse_qs(urlparse(url).query)["cursorMark"][0]]

    records = audit.fetch_benchmark(fetcher=fake, cache_dir=tmp_path, sleep=lambda _s: None)
    assert len(records) == 3
    assert sorted(audit.benchmark_dois(records)) == ["10.1/a", "10.1/b"]
    assert len(list(tmp_path.glob("page_*.json"))) == 2


def test_report_shape() -> None:
    report = audit.build_report(
        query="q",
        date="2026-11-11",
        total=10,
        with_doi=8,
        in_corpus=4,
        in_corpus_ca=2,
        published=2,
        missing=4,
    )
    assert report["recall_in_corpus"] == 0.5
    assert report["recall_ca_in_corpus"] == 0.25
    assert {"query", "date", "total", "with_doi", "missing", "credits"} <= set(report)
