import json
from pathlib import Path

from atlas.fulltext import LOCATOR_SCHEMA, _url_names_pmcid, coverage_report, locate_records

FIXTURE = Path(__file__).parent / "fixtures" / "s6_1_fulltext_records.json"


def _fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_locator_prefers_europe_pmc_xml_and_gates_by_license():
    payload = _fixture()
    rows = locate_records(payload["candidates"], payload["raw"])
    by_id = {row["work_id"]: row for row in rows}
    assert [row["source_type"] for row in rows] == [
        "xml",
        "pdf",
        "xml",
        "pdf",
        "pdf",
        "pdf",
        "none",
        "none",
    ]
    assert by_id["W9000000101"]["locator_url"] == (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8123456/fullTextXML"
    )
    assert by_id["W9000000101"]["license"] == "cc-by-4.0"
    assert by_id["W9000000101"]["license_provenance"] == (
        "OpenAlex locations[1].license; trusted repository path identifies PMC8123456"
    )
    assert by_id["W9000000101"]["processing_allowed"] is True
    assert by_id["W9000000101"]["storage_decision"] == "cache_only"
    assert by_id["W9000000102"]["locator_url"] == "https://example.org/102.pdf"
    assert by_id["W9000000102"]["attribution_url"] == "https://example.org/102"
    assert by_id["W9000000102"]["license_provenance"] == (
        "OpenAlex best_oa_location.license for selected pdf_url"
    )


def test_xml_never_inherits_unmatched_publisher_copy_license():
    payload = _fixture()
    rows = locate_records(payload["candidates"], payload["raw"])
    by_id = {row["work_id"]: row for row in rows}
    xml = by_id["W9000000103"]
    assert xml["source_type"] == "xml"
    assert xml["license"] == ""
    assert xml["license_status"] == "unknown"
    assert xml["license_provenance"] == ("unknown: no license evidence tied to PMC8123458 location")
    assert xml["processing_allowed"] is False
    assert xml["storage_decision"] == "review"


def test_pdf_requires_same_copy_license_and_blocks_restricted_license():
    payload = _fixture()
    rows = locate_records(payload["candidates"], payload["raw"])
    by_id = {row["work_id"]: row for row in rows}
    missing = by_id["W9000000104"]
    assert missing["source_type"] == "pdf"
    assert missing["license"] == ""
    assert missing["license_status"] == "unknown"
    assert missing["processing_allowed"] is False
    assert missing["license_provenance"] == (
        "unknown: best_oa_location license missing for selected pdf_url"
    )
    restricted = by_id["W9000000105"]
    assert restricted["source_type"] == "pdf"
    assert restricted["license_status"] == "restricted"
    assert restricted["processing_allowed"] is False
    assert restricted["storage_decision"] == "do_not_cache"


def test_locator_is_deterministic_and_reports_only_candidate_coverage():
    payload = _fixture()
    first = locate_records(payload["candidates"], payload["raw"])
    second = locate_records(reversed(payload["candidates"]), payload["raw"])
    assert first == second
    assert set(first[0]) == set(LOCATOR_SCHEMA.names)
    report = coverage_report(first, source="synthetic fixture")
    assert "candidate rows: 8" in report
    assert "| XML | 2 | 25.0% |" in report
    assert "| PDF | 4 | 50.0% |" in report
    assert "| None | 2 | 25.0% |" in report
    assert "| restricted | 1 |" in report
    assert "does not fetch article text" in report


def test_locator_rejects_unsafe_and_malformed_pmcid_urls():
    candidate = {"work_id": "W1", "is_oa": True}
    raw = {
        "W1": {
            "ids": {"pmcid": "../../private"},
            "open_access": {"is_oa": True},
            "best_oa_location": {"pdf_url": "https://127.0.0.1/private.pdf"},
        }
    }
    row = locate_records([candidate], raw)[0]
    assert row["source_type"] == "none"
    assert row["locator_url"] == ""
    assert row["processing_allowed"] is False


def test_pmc_license_url_requires_trusted_https_host_and_canonical_pmcid_path():
    cases = {
        "PMC8123456": False,
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC81234560/": False,
        "https://publisher.example/articles/PMC8123456/": False,
        "https://publisher.example/article?id=PMC8123456": False,
        "http://pmc.ncbi.nlm.nih.gov/articles/PMC8123456/": False,
        "https://pmc.ncbi.nlm.nih.gov/articles/PMC8123456/": True,
        "https://europepmc.org/articles/PMC8123456": True,
        "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8123456/fullTextXML": True,
    }
    assert {value: _url_names_pmcid(value, "PMC8123456") for value in cases} == cases


def test_openalex_url_form_pmcid_selects_xml_with_legacy_pmc_license():
    # OpenAlex reports ids.pmcid as a URL with bare digits (found on the real corpus,
    # 2026-11-12: all 321 PMCIDs were missed before this form was accepted).
    raw = {
        "W1": {
            "ids": {"pmcid": "https://www.ncbi.nlm.nih.gov/pmc/articles/221095"},
            "open_access": {"is_oa": True},
            "locations": [
                {
                    "landing_page_url": "https://www.ncbi.nlm.nih.gov/pmc/articles/221095",
                    "license": "cc-by",
                }
            ],
        }
    }
    [row] = locate_records([{"work_id": "W1", "is_oa": True}], raw)
    assert row["source_type"] == "xml"
    assert row["pmcid"] == "PMC221095"
    assert row["license"] == "cc-by"
    assert _url_names_pmcid("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC221095", "PMC221095")
    assert not _url_names_pmcid("https://www.ncbi.nlm.nih.gov/pmc/articles/999", "PMC221095")
