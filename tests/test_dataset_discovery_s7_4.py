from __future__ import annotations

from atlas.dataset_discovery import (
    canonical_doi,
    data_availability_candidates,
    datacite_candidates,
    datacite_query_candidates,
    extract_data_availability,
)


def test_datacite_query_candidates_are_deduplicated_and_do_not_claim_work_links() -> None:
    records = [
        {
            "id": "10.5281/Zenodo.123",
            "attributes": {
                "titles": [{"title": "California microplastic dataset"}],
                "types": {"resourceTypeGeneral": "Dataset"},
                "url": "https://example.org/data/123",
            },
        },
        {
            "id": "https://doi.org/10.5281/zenodo.123",
            "attributes": {"titles": [{"title": "Duplicate result"}]},
        },
    ]
    candidates = datacite_query_candidates(
        records,
        query_evidence={"query_1": "California AND microplastic"},
        retrieved_at="2026-11-09T12:00:00Z",
        record_provenance={
            "10.5281/zenodo.123": {
                "query_membership": ["query_1"],
                "metadata_request_urls": ["https://api.datacite.org/dois?query=x"],
                "sanitized_response_sha256": ["abc123"],
                "metadata_retrieved_at": ["2026-11-09T12:00:00Z"],
            }
        },
    )
    assert len(candidates) == 1
    assert candidates[0]["dataset_doi"] == "10.5281/zenodo.123"
    assert candidates[0]["source_work_id"] is None
    assert candidates[0]["candidate_status"] == "unreviewed"
    assert candidates[0]["query_evidence"] == {"query_1": "California AND microplastic"}
    assert candidates[0]["query_membership"] == ["query_1"]
    assert candidates[0]["sanitized_response_sha256"] == ["abc123"]


def test_relation_candidates_only_join_local_source_work_dois() -> None:
    records = [
        {
            "id": "10.5281/zenodo.456",
            "attributes": {
                "titles": [{"title": "Data"}],
                "types": {"resourceTypeGeneral": "Dataset"},
                "relatedIdentifiers": [
                    {
                        "relatedIdentifier": "https://doi.org/10.1000/PAPER",
                        "relatedIdentifierType": "DOI",
                        "relationType": "IsSupplementTo",
                    },
                    {
                        "relatedIdentifier": "10.1000/UNKNOWN",
                        "relatedIdentifierType": "DOI",
                        "relationType": "IsSupplementTo",
                    },
                    {
                        "relatedIdentifier": "10.5281/zenodo.456",
                        "relatedIdentifierType": "DOI",
                        "relationType": "IsSupplementTo",
                    },
                ],
            },
        }
    ]
    found = datacite_candidates(
        records,
        {"10.1000/paper": {"work_id": "W1", "title": "Paper"}},
        retrieved_at="2026-11-09T12:00:00Z",
    )
    assert len(found) == 1
    assert found[0]["source_work_id"] == "W1"
    assert found[0]["candidate_status"] == "candidate"


def test_jats_data_availability_extracts_dois_and_urls_from_bounded_evidence() -> None:
    xml = """<article><body><sec><title>Data Availability</title>
      <p>Data are at https://example.org/data and DOI: 10.5281/zenodo.123.</p>
    </sec></body></article>"""
    sections = extract_data_availability(xml, max_chars=300)
    assert len(sections) == 1
    assert sections[0]["doi_mentions"] == ["10.5281/zenodo.123"]
    assert sections[0]["url_mentions"] == ["https://example.org/data"]
    assert sections[0]["evidence_type"] == "data_availability"


def test_jats_candidates_exclude_article_doi_and_merge_dataset_doi_url_mentions() -> None:
    xml = """<article><body><sec><title>Data Availability</title>
      <p>This article DOI is 10.1000/ARTICLE. Dataset: DOI 10.5281/Zenodo.123;
      URL https://doi.org/10.5281/zenodo.123.</p>
    </sec></body></article>"""
    candidates = data_availability_candidates(
        xml,
        source_work_id="W1",
        source_url="https://example.org/article",
        source_article_doi="https://doi.org/10.1000/article",
        retrieved_at="2026-11-09T12:00:00Z",
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["candidate_doi"] == "10.5281/zenodo.123"
    assert candidate["candidate_type"] == "data_availability_identifier"
    assert candidate["source_work_id"] == "W1"
    assert candidate["doi_mentions"] == ["10.5281/zenodo.123"]
    assert candidate["url_mentions"] == ["https://doi.org/10.5281/zenodo.123"]
    assert candidate["candidate_status"] == "uncertain"
    assert candidate["evidence_type"] == "data_availability"


def test_canonical_doi_rejects_non_doi_and_normalizes_url() -> None:
    assert canonical_doi("https://doi.org/10.5281/Zenodo.12.") == "10.5281/zenodo.12"
    assert canonical_doi("https://example.org/data") is None
