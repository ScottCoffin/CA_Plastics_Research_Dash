"""Unit tests for work-to-dataset links and their export/render surfaces (S9.2). Offline only."""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build.export_site import export_site
from atlas.build.monitoring import build_monitoring_payload
from atlas.link.work_datasets import (
    EVIDENCE_DAS,
    EVIDENCE_DATACITE,
    WorkDatasetLink,
    combine_links,
    das_matches,
    datacite_transport,
    fetch_relation_records,
    relation_matches,
    work_index,
)

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "work_datasets_view_runtime.cjs"
INDEX_HTML = ROOT / "site" / "index.html"

PAPER_ONE = "10.1000/paper-one"
PAPER_TWO = "10.1000/paper-two"


def _work(openalex: str, doi: str, pmcid: str | None = None) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "id": f"https://openalex.org/{openalex}",
        "doi": f"https://doi.org/{doi}",
    }
    raw["title"] = f"Title {openalex}"
    if pmcid:
        raw["ids"] = {"pmcid": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}"}
    return {"raw_json": json.dumps(raw)}


def _index() -> dict[str, dict[str, Any]]:
    return work_index(
        [_work("W1", PAPER_ONE, "PMC111"), _work("W2", PAPER_TWO)],
    )


def _record(doi: str, resource: str, related: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "id": doi,
        "attributes": {
            "url": f"https://example.org/{doi}",
            "titles": [{"title": f"Dataset {doi}"}],
            "types": {"resourceTypeGeneral": resource},
            "relatedIdentifiers": [
                {"relatedIdentifier": rid, "relationType": rel, "relatedIdentifierType": "DOI"}
                for rid, rel in related
            ],
        },
    }


def test_relation_typing_links_only_typed_dataset_relations() -> None:
    records = [
        _record("10.5281/zenodo.1", "Dataset", [(PAPER_ONE, "IsCitedBy")]),
        _record("10.5281/zenodo.2", "Dataset", [(PAPER_TWO, "IsVersionOf")]),
        _record("10.5281/zenodo.3", "Text", [(PAPER_TWO, "IsSupplementTo")]),
        _record("10.5281/zenodo.4", "Dataset", [("10.9999/not-a-work", "IsCitedBy")]),
    ]
    links, review = relation_matches(records, _index())

    assert [
        (link.work_id, link.dataset_doi, link.relation_type, link.evidence_type, link.confidence)
        for link in links
    ] == [("W1", "10.5281/zenodo.1", "IsCitedBy", EVIDENCE_DATACITE, "high")]
    # Uncertain candidates are kept out of the links and listed for review only.
    assert sorted((r.work_id, r.dataset_doi) for r in review) == [
        ("W2", "10.5281/zenodo.2"),
        ("W2", "10.5281/zenodo.3"),
    ]
    assert all("not a typed dataset link" in r.reason for r in review)


def test_das_match_links_known_dataset_and_reviews_unknown_doi() -> None:
    xml = """<article><body><sec><title>Data Availability</title>
    <p>Data are at https://doi.org/10.5281/zenodo.1 and https://doi.org/10.9999/unknown.
    The article itself is 10.1000/paper-one.</p></sec></body></article>"""
    links, review = das_matches("W1", PAPER_ONE, [xml], {"10.5281/zenodo.1"})

    assert [(link.work_id, link.dataset_doi, link.evidence_type) for link in links] == [
        ("W1", "10.5281/zenodo.1", EVIDENCE_DAS)
    ]
    assert [(r.dataset_doi, r.evidence_type) for r in review] == [("10.9999/unknown", EVIDENCE_DAS)]


def test_combine_prefers_datacite_relation_for_the_same_work_and_dataset() -> None:
    das = WorkDatasetLink("W1", "10.5281/zenodo.1", "data-availability", EVIDENCE_DAS, "x", "high")
    typed = WorkDatasetLink("W1", "10.5281/zenodo.1", "IsCitedBy", EVIDENCE_DATACITE, "x", "high")
    assert combine_links([das, typed]) == [typed]


def test_datacite_transport_refuses_other_hosts() -> None:
    with pytest.raises(ValueError):
        datacite_transport("https://example.org/dois?query=x")


def test_query_is_batched_paginated_budgeted_and_cached(tmp_path: Path) -> None:
    dois = [f"10.1000/paper-{i:02d}" for i in range(10)]
    cache = tmp_path / "cache.json"
    calls: list[str] = []
    sleeps: list[float] = []

    def transport(url: str) -> tuple[int, str]:
        calls.append(url)
        return 200, json.dumps({"data": [], "meta": {"totalPages": 1}})

    report = fetch_relation_records(
        dois, cache_path=cache, transport=transport, sleep=sleeps.append
    )
    assert report.requests == 2 and report.cached_batches == 0
    assert sleeps and all(s >= 1.1 for s in sleeps)
    assert calls[0].startswith("https://api.datacite.org/dois?")
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(calls[0]).query)["query"][0]
    assert query.startswith("relatedIdentifiers.relatedIdentifier:(")
    assert '"10.1000/paper-00" OR "10.1000/paper-01"' in query

    again = fetch_relation_records(dois, cache_path=cache, transport=transport)
    assert again.requests == 0 and again.cached_batches == 2
    assert len(calls) == 2

    budget_cache = tmp_path / "budget.json"
    cut = fetch_relation_records(
        dois, cache_path=budget_cache, transport=transport, max_requests=1, sleep=lambda _: None
    )
    assert cut.requests == 1 and cut.incomplete_batches == 1


def test_pagination_merges_pages_and_failures_are_not_cached(tmp_path: Path) -> None:
    cache = tmp_path / "cache.json"
    pages = {
        "1": {
            "data": [_record("10.5281/zenodo.1", "Dataset", [(PAPER_ONE, "IsCitedBy")])],
            "meta": {"totalPages": 2},
        },
        "2": {
            "data": [_record("10.5281/zenodo.2", "Dataset", [(PAPER_TWO, "IsCitedBy")])],
            "meta": {"totalPages": 2},
        },
    }

    def transport(url: str) -> tuple[int, str]:
        page = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["page[number]"][0]
        return 200, json.dumps(pages[page])

    report = fetch_relation_records(
        [PAPER_ONE], cache_path=cache, transport=transport, sleep=lambda _: None
    )
    assert report.requests == 2
    assert [r["id"] for r in report.records] == ["10.5281/zenodo.1", "10.5281/zenodo.2"]

    failing = tmp_path / "failing.json"
    failed = fetch_relation_records(
        [PAPER_ONE], cache_path=failing, transport=lambda url: (429, "{}"), sleep=lambda _: None
    )
    assert failed.failed_batches == 1 and failed.records == []
    assert not failing.exists()


def _parquet(path: Path, rows: list[dict[str, Any]]) -> Path:
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def _export_inputs(root: Path) -> dict[str, Path]:
    works = [
        {
            "work_id": "W1",
            "title": "One",
            "year": 2024,
            "type": "article",
            "doi": f"https://doi.org/{PAPER_ONE}",
            "ca_led": True,
            "ca_any_author": True,
            "cited_by_count": 3,
            "abstract": "a",
            "journal": "J",
            "is_oa": False,
            "openalex_topics": [],
            "institution_ids": [],
        },
        {
            "work_id": "W2",
            "title": "Two",
            "year": 2023,
            "type": "article",
            "doi": f"https://doi.org/{PAPER_TWO}",
            "ca_led": False,
            "ca_any_author": True,
            "cited_by_count": 1,
            "abstract": "b",
            "journal": "J",
            "is_oa": False,
            "openalex_topics": [],
            "institution_ids": [],
        },
    ]
    authors = [
        {
            "author_id": "A1",
            "name": "Ada",
            "orcid": None,
            "ca_works_count": 2,
            "first_year": 2023,
            "last_year": 2024,
            "domain_tags": [],
        }
    ]
    authorships = [
        {"work_id": "W1", "author_id": "A1", "institution_ids": ["I1"]},
        {"work_id": "W2", "author_id": "A1", "institution_ids": ["I1"]},
    ]
    institutions = [
        {
            "inst_id": "I1",
            "name": "Inst",
            "type": "university",
            "ca_flag": True,
            "lat": 38.0,
            "lon": -121.0,
        }
    ]
    return {
        "works_path": _parquet(root / "works.parquet", works),
        "authors_path": _parquet(root / "authors.parquet", authors),
        "authorships_path": _parquet(root / "authorships.parquet", authorships),
        "institutions_path": _parquet(root / "institutions.parquet", institutions),
    }


def test_export_adds_datasets_only_to_linked_works(tmp_path: Path) -> None:
    inputs = _export_inputs(tmp_path)
    links = _parquet(
        tmp_path / "links.parquet",
        [
            {
                "work_id": "W1",
                "dataset_doi": "10.5281/zenodo.1",
                "relation_type": "IsCitedBy",
                "evidence_type": EVIDENCE_DATACITE,
                "evidence_value": "IsCitedBy",
                "confidence": "high",
            }
        ],
    )

    base_dir = tmp_path / "base"
    base_dir_again = tmp_path / "base-again"
    linked_dir = tmp_path / "linked"
    export_site(output_dir=base_dir, generated_at="test", **inputs)
    export_site(output_dir=base_dir_again, generated_at="test", **inputs)
    export_site(output_dir=linked_dir, generated_at="test", work_dataset_links_path=links, **inputs)

    base_detail = (base_dir / "authors" / "A1.json").read_bytes()
    assert base_detail == (base_dir_again / "authors" / "A1.json").read_bytes()
    assert b'"datasets"' not in base_detail
    assert (base_dir / "index.json").read_bytes() == (linked_dir / "index.json").read_bytes()

    base = json.loads(base_detail)
    linked = json.loads((linked_dir / "authors" / "A1.json").read_text(encoding="utf-8"))
    by_id = {w["work_id"]: w for w in linked["works"]}
    base_by_id = {w["work_id"]: w for w in base["works"]}
    assert by_id["W1"]["datasets"] == [
        {"doi": "10.5281/zenodo.1", "relation": "IsCitedBy", "evidence_type": EVIDENCE_DATACITE}
    ]
    assert by_id["W2"] == base_by_id["W2"]
    assert {k: v for k, v in by_id["W1"].items() if k != "datasets"} == base_by_id["W1"]


def _registry_entry(entry_id: str, url: str, provenance_url: str) -> dict[str, Any]:
    return {
        "id": entry_id,
        "seed_eligible": True,
        "name": entry_id,
        "steward": "s",
        "entity_type": "dataset",
        "status": "active",
        "region": "CA",
        "sample_matrix": ["water"],
        "plastic_classes": [],
        "access_tier": "open",
        "url": url,
        "access_method": "download",
        "format": ["csv"],
        "cadence": "annual",
        "license": "CC0",
        "provenance_type": "registry",
        "provenance_url": provenance_url,
        "provenance_note": "note",
        "last_checked": "2026-01-01",
    }


def test_monitoring_rows_gain_linked_works_only_on_doi_match() -> None:
    registry = {
        "datasets": [
            _registry_entry("linked", "https://doi.org/10.5281/zenodo.1", "https://example.org/p"),
            _registry_entry("plain", "https://example.org/d", "https://example.org/q"),
        ]
    }
    base = build_monitoring_payload(registry, generated_at="t")
    assert build_monitoring_payload(registry, generated_at="t", work_links=None) == base
    assert all("linked_works" not in row for row in base["datasets"])

    links = [
        {"work_id": "W1", "dataset_doi": "10.5281/zenodo.1", "evidence_type": EVIDENCE_DATACITE},
        {"work_id": "W2", "dataset_doi": "10.5281/zenodo.1", "evidence_type": EVIDENCE_DAS},
        {"work_id": "W9", "dataset_doi": "10.9999/elsewhere", "evidence_type": EVIDENCE_DATACITE},
    ]
    linked = build_monitoring_payload(registry, generated_at="t", work_links=links)
    rows = {row["id"]: row for row in linked["datasets"]}
    assert rows["linked"]["linked_works"] == [
        {"work_id": "W1", "evidence_type": EVIDENCE_DATACITE},
        {"work_id": "W2", "evidence_type": EVIDENCE_DAS},
    ]
    assert "linked_works" not in rows["plain"]
    assert {k: v for k, v in rows["linked"].items() if k != "linked_works"} == {
        k: v for k, v in {r["id"]: r for r in base["datasets"]}["linked"].items()
    }


def test_drawer_and_registry_call_the_dataset_render_helpers() -> None:
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert '<script id="work-dataset-view-helpers">' in text
    assert "${workDatasetView.datasetsHtml(work)}" in text
    assert "${workDatasetView.linkedWorksHtml(row)}" in text


def test_work_dataset_view_runtime_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/work_datasets_view_runtime.cjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)
