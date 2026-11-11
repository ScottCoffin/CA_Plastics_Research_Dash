"""Offline tests for the DataCite expert-ORCID ingest (S2.5d). No network calls."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.ingest import datacite_orcid as dc

ORCID_A = "0000-0001-0000-0001"
ORCID_B = "0000-0002-0000-0002"
DESCRIPTION_SECRET = "SECRET-DESCRIPTION-TEXT-DO-NOT-STORE"


@pytest.fixture(scope="module")
def query_config() -> dict:
    return dc.load_active_query_config()


def _item(
    doi: str,
    *,
    title: str = "Soil carbon dynamics in grassland restoration",
    orcid: str = ORCID_A,
    version_of: str | None = None,
    resource_type_general: str = "Text",
    resource_type: str = "Poster",
) -> dict:
    related = []
    if version_of:
        related.append(
            {
                "relatedIdentifier": version_of,
                "relatedIdentifierType": "DOI",
                "relationType": "IsVersionOf",
            }
        )
    return {
        "id": doi,
        "attributes": {
            "doi": doi,
            "titles": [{"title": title}],
            "descriptions": [{"description": DESCRIPTION_SECRET, "descriptionType": "Abstract"}],
            "publisher": {"name": "Zenodo"},
            "publicationYear": 2022,
            "types": {"resourceTypeGeneral": resource_type_general, "resourceType": resource_type},
            "relatedIdentifiers": related,
            "creators": [{"nameIdentifiers": [{"nameIdentifier": f"https://orcid.org/{orcid}"}]}],
        },
    }


class FakeTransport:
    """Serves canned responses keyed by URL and records every call."""

    def __init__(self, responses: dict[str, list]) -> None:
        self.responses = {url: list(values) for url, values in responses.items()}
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, bytes, str | None]:
        self.calls.append(url)
        status, body, retry_after = self.responses[url].pop(0)
        return status, body, retry_after


def _page(data: list, next_url: str | None = None) -> tuple[int, bytes, None]:
    links = {"next": next_url} if next_url else {}
    return 200, json.dumps({"data": data, "links": links}).encode("utf-8"), None


def _no_sleep(_seconds: float) -> None:
    return None


def _source(tmp_path: Path, transport: FakeTransport, **kwargs) -> dc.PageSource:
    return dc.PageSource(
        cache_dir=tmp_path / "cache",
        transport=transport,
        sleep=_no_sleep,
        clock=lambda: 1000.0,
        min_interval=0.0,
        **kwargs,
    )


# --------------------------------------------------------------------------- query building


def test_orcid_query_uses_creator_orcid_clauses_joined_by_or() -> None:
    query = dc.orcid_query([ORCID_A, ORCID_B])
    assert query == (
        '(creators.nameIdentifiers.nameIdentifier:"https://orcid.org/0000-0001-0000-0001"'
        ' OR creators.nameIdentifiers.nameIdentifier:"https://orcid.org/0000-0002-0000-0002")'
    )


def test_orcid_batches_never_exceed_25() -> None:
    orcids = [f"0000-0000-0000-{i:04d}" for i in range(60)]
    batches = dc.orcid_batches(orcids)
    assert [len(batch) for batch in batches] == [25, 25, 10]
    assert max(len(batch) for batch in batches) <= 25
    assert [o for batch in batches for o in batch] == orcids
    with pytest.raises(ValueError):
        dc.orcid_query(orcids[:26])


def test_request_url_encodes_query_and_page_size() -> None:
    url = dc.request_url(dc.orcid_query([ORCID_A]))
    parsed = urlparse(url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == dc.API_URL
    params = parse_qs(parsed.query)
    assert params["page[size]"] == ["1000"]
    assert params["query"] == [dc.orcid_query([ORCID_A])]


# --------------------------------------------------------------------------- paging and transport


def test_cursor_paging_follows_links_next(tmp_path: Path) -> None:
    first = dc.request_url(dc.orcid_query([ORCID_A]))
    second = f"{dc.API_URL}?page%5Bcursor%5D=abc"
    transport = FakeTransport(
        {
            first: [_page([_item("10.5281/zenodo.1")], next_url=second)],
            second: [_page([_item("10.5281/zenodo.2")])],
        }
    )
    source = _source(tmp_path, transport)
    items = dc.fetch_batch_items(source, [ORCID_A])
    assert [item["id"] for item in items] == ["10.5281/zenodo.1", "10.5281/zenodo.2"]
    assert transport.calls == [first, second]
    assert source.requests_used == 2


def test_cursor_link_outside_datacite_is_rejected(tmp_path: Path) -> None:
    first = dc.request_url(dc.orcid_query([ORCID_A]))
    transport = FakeTransport({first: [_page([_item("10.5281/z.1")], "https://evil.example/x")]})
    with pytest.raises(dc.DataCiteHTTPError):
        dc.fetch_batch_items(_source(tmp_path, transport), [ORCID_A])


def test_429_is_retried_with_retry_after_and_counts_each_attempt(tmp_path: Path) -> None:
    url = dc.request_url(dc.orcid_query([ORCID_A]))
    transport = FakeTransport({url: [(429, b"", "3"), _page([_item("10.5281/z.1")])]})
    sleeps: list[float] = []
    source = dc.PageSource(
        cache_dir=tmp_path / "cache",
        transport=transport,
        sleep=sleeps.append,
        clock=lambda: 1000.0,
        min_interval=0.0,
    )
    assert len(dc.fetch_batch_items(source, [ORCID_A])) == 1
    assert sleeps == [3.0]
    assert source.requests_used == 2


def test_budget_stops_before_exceeding_cap(tmp_path: Path) -> None:
    url = dc.request_url(dc.orcid_query([ORCID_A]))
    transport = FakeTransport({url: [_page([])]})
    source = _source(tmp_path, transport, max_requests=0)
    with pytest.raises(dc.RequestBudgetExhausted):
        dc.fetch_batch_items(source, [ORCID_A])
    assert transport.calls == []


def test_cache_hit_avoids_request_and_offline_miss_raises(tmp_path: Path) -> None:
    url = dc.request_url(dc.orcid_query([ORCID_A]))
    transport = FakeTransport({url: [_page([_item("10.5281/z.1")])]})
    dc.fetch_batch_items(_source(tmp_path, transport), [ORCID_A])
    assert dc.cache_path(tmp_path / "cache", url).exists()

    cached_transport = FakeTransport({})
    offline = _source(tmp_path, cached_transport, offline=True)
    assert len(dc.fetch_batch_items(offline, [ORCID_A])) == 1
    assert cached_transport.calls == []
    assert offline.cache_hits == 1

    with pytest.raises(dc.CacheMiss):
        dc.fetch_batch_items(_source(tmp_path, FakeTransport({}), offline=True), [ORCID_B])


def test_pacing_waits_between_requests(tmp_path: Path) -> None:
    url_a = dc.request_url(dc.orcid_query([ORCID_A]))
    url_b = dc.request_url(dc.orcid_query([ORCID_B]))
    transport = FakeTransport({url_a: [_page([])], url_b: [_page([])]})
    sleeps: list[float] = []
    now = [100.0]
    source = dc.PageSource(
        cache_dir=tmp_path / "cache",
        transport=transport,
        sleep=sleeps.append,
        clock=lambda: now[0],
        min_interval=0.25,
    )
    source.get_json(url_a)
    source.get_json(url_b)
    assert sleeps == [pytest.approx(0.25)]


# --------------------------------------------------------------------------- parsing


def test_parse_record_extracts_metadata_and_version_family(query_config: dict) -> None:
    item = _item("10.5281/ZENODO.7217432", version_of="10.5281/zenodo.7217431")
    record = dc.parse_record(item, query_config)
    assert record is not None
    assert record.doi == "10.5281/zenodo.7217432"
    assert record.resource_type_general == "Text"
    assert record.resource_type == "Poster"
    assert record.publisher == "Zenodo"
    assert record.year == 2022
    assert record.version_of == "10.5281/zenodo.7217431"
    assert record.creator_orcids == (ORCID_A,)


def test_record_has_no_description_field_and_parquet_does_not_store_it(
    tmp_path: Path, query_config: dict
) -> None:
    record = dc.parse_record(_item("10.5281/zenodo.9"), query_config)
    assert record is not None
    assert "description" not in {field.name for field in dataclasses.fields(record)}
    rows = dc.build_rows([record], {ORCID_A: ["A1"]}, set())
    output = tmp_path / "out.parquet"
    dc.write_rows(output, rows)
    table = pq.read_table(output)
    assert not [name for name in table.column_names if "descri" in name or "abstract" in name]
    assert DESCRIPTION_SECRET not in json.dumps(table.to_pylist())


def test_plastic_flag_uses_title_and_description_rules(query_config: dict) -> None:
    plastic = dc.parse_record(
        _item("10.5281/zenodo.1", title="Microplastics in San Francisco Bay sediments"),
        query_config,
    )
    unrelated = dc.parse_record(_item("10.5281/zenodo.2"), query_config)
    assert plastic is not None and plastic.plastic_related is True
    assert unrelated is not None and unrelated.plastic_related is False


def test_parse_record_skips_items_without_doi(query_config: dict) -> None:
    assert dc.parse_record({"id": "", "attributes": {"doi": "not-a-doi"}}, query_config) is None
    assert dc.parse_record({"id": "x"}, query_config) is None


# --------------------------------------------------------------------------- rows and families


def test_shared_orcid_maps_to_each_author_once_and_flags_corpus(query_config: dict) -> None:
    record = dc.parse_record(_item("10.5281/zenodo.5"), query_config)
    assert record is not None
    rows = dc.build_rows(
        [record, record],
        {ORCID_A: ["A1", "A2"]},
        {"10.5281/zenodo.5"},
    )
    assert [(row["author_id"], row["doi"]) for row in rows] == [
        ("A1", "10.5281/zenodo.5"),
        ("A2", "10.5281/zenodo.5"),
    ]
    assert all(row["in_corpus"] is True for row in rows)
    assert all(row["family_doi"] == "10.5281/zenodo.5" for row in rows)


def test_family_collapse_uses_concept_doi_and_counts_once(query_config: dict) -> None:
    concept = "10.5281/zenodo.100"
    version_one = dc.parse_record(
        _item("10.5281/zenodo.101", version_of=concept, title="Microplastics survey v1"),
        query_config,
    )
    version_two = dc.parse_record(
        _item("10.5281/zenodo.102", version_of=concept, title="Microplastics survey v2"),
        query_config,
    )
    assert version_one is not None and version_two is not None
    rows = dc.build_rows([version_one, version_two], {ORCID_A: ["A1"]}, set())
    assert all(row["is_version"] is True for row in rows)
    assert all(row["family_doi"] == concept for row in rows)
    summary = dc.summarize(
        rows,
        set(),
        experts_queried=1,
        batches=1,
        requests_used=1,
        cache_hits=0,
        items_returned=2,
        unparsed_items=0,
    )
    assert summary.unique_dois == 2
    assert summary.plastic_related_dois == 2
    assert summary.plastic_families == 1
    assert summary.plastic_not_in_corpus_families == 1
    assert summary.is_version_dois == 2
    assert summary.karapetrova_probe_found is False


def test_family_in_corpus_if_concept_doi_is_in_works(query_config: dict) -> None:
    concept = "10.5281/zenodo.200"
    record = dc.parse_record(
        _item("10.5281/zenodo.201", version_of=concept, title="Microplastics poster"),
        query_config,
    )
    assert record is not None
    rows = dc.build_rows([record], {ORCID_A: ["A1"]}, {concept})
    summary = dc.summarize(
        rows,
        {concept},
        experts_queried=1,
        batches=1,
        requests_used=1,
        cache_hits=0,
        items_returned=1,
        unparsed_items=0,
    )
    assert summary.plastic_families == 1
    assert summary.plastic_not_in_corpus_families == 0
    assert summary.plastic_not_in_corpus_dois == 1


# --------------------------------------------------------------------------- end to end


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    profiles = tmp_path / "orcid_profiles.parquet"
    pq.write_table(
        pa.table({"author_id": ["A1", "A2"], "orcid": [ORCID_A, ORCID_A]}),
        profiles,
    )
    works = tmp_path / "works.parquet"
    pq.write_table(pa.table({"doi": ["https://doi.org/10.5281/ZENODO.7"]}), works)
    return profiles, works


def test_run_expert_outputs_end_to_end_offline_matches_live(tmp_path: Path) -> None:
    profiles, works = _write_inputs(tmp_path)
    url = dc.request_url(dc.orcid_query([ORCID_A]))
    transport = FakeTransport(
        {
            url: [
                _page(
                    [
                        _item("10.5281/zenodo.7", title="Microplastics poster"),
                        _item("10.5281/zenodo.8"),
                    ]
                )
            ]
        }
    )
    output = tmp_path / "out.parquet"
    kwargs = dict(
        profiles_path=profiles,
        works_path=works,
        cache_dir=tmp_path / "cache",
        output_path=output,
        sleep=_no_sleep,
    )
    live = dc.run_expert_outputs(transport=transport, **kwargs)
    assert live.requests_used == 1
    assert live.rows == 4  # two DOIs, each mapped to two author_ids
    assert live.plastic_related_dois == 1
    assert live.plastic_not_in_corpus_dois == 0  # the only plastic DOI is in works
    assert live.unique_dois == 2
    rows = pq.read_table(output).to_pylist()
    assert {row["doi"] for row in rows} == {"10.5281/zenodo.7", "10.5281/zenodo.8"}
    assert all(row["in_corpus"] is True for row in rows if row["doi"].endswith(".7"))
    assert all(row["in_corpus"] is False for row in rows if row["doi"].endswith(".8"))

    offline = dc.run_expert_outputs(transport=FakeTransport({}), offline=True, **kwargs)
    assert offline.requests_used == 0
    assert offline.cache_hits == 1
    assert offline.rows == live.rows


def test_run_writes_nothing_when_budget_is_exhausted(tmp_path: Path) -> None:
    profiles, works = _write_inputs(tmp_path)
    output = tmp_path / "out.parquet"
    with pytest.raises(dc.RequestBudgetExhausted):
        dc.run_expert_outputs(
            profiles_path=profiles,
            works_path=works,
            cache_dir=tmp_path / "cache",
            output_path=output,
            max_requests=0,
            transport=FakeTransport({}),
            sleep=_no_sleep,
        )
    assert not output.exists()


def test_active_query_version_is_enforced(tmp_path: Path) -> None:
    config = tmp_path / "queries.yml"
    config.write_text("version: plastic-v0\ncore_terms: []\n", encoding="utf-8")
    with pytest.raises((ValueError, KeyError)):
        dc.load_active_query_config(config)
